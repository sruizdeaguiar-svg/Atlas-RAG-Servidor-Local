"""Isolated HTTP + HTTPS integration checks; never mutates production or existing engines."""
import os,sys,json,time,tempfile,subprocess,socket,threading,ssl,zipfile,io,hashlib,secrets
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1]
QA=Path(tempfile.mkdtemp(prefix='atlas-release-',dir=os.environ.get('ATLAS_QA_ROOT','/private/tmp')));STATE=QA/'state';STATE.mkdir();env={**os.environ,'RAG_STATE_DIR':str(STATE),'PYTHONDONTWRITEBYTECODE':'1'}
checks=[];payloads=[]
def check(name,value):
    assert value,name
    checks.append(name)
class Model(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'n_ctx':32768,'default_generation_settings':{'n_ctx':32768},'data':[{'id':'qa-one'},{'id':'qa-two'}]}).encode())
    def do_POST(self):
        p=json.loads(self.rfile.read(int(self.headers['Content-Length'])));payloads.append(p)
        text=json.dumps(p['messages'])
        answer=json.dumps({'method':'describe','columns':['x','y'],'explanation':'Fictitious QA data'}) if 'Translate the requested statistical analysis' in text else 'READY [1]'
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'choices':[{'message':{'content':answer}}]}).encode())
mock=ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=mock.serve_forever,daemon=True).start()
import httpx
config_code="from server.store import init;init();from server import network;network.configure(True)"
subprocess.run([sys.executable,'-B','-c',config_code],cwd=ROOT,env=env,check=True,capture_output=True)
cfg=json.loads((STATE/'network.json').read_text());cfg['port']=18766;(STATE/'network.json').write_text(json.dumps(cfg))
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
log=(QA/'server.log').open('w');proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'server/run.py'),'--port',str(port),'--owner','isolated-release-qa'],cwd=ROOT,env=env,stdout=log,stderr=log)
try:
    base=f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            if httpx.get(base+'/api/health',trust_env=False,timeout=.5).status_code==200:break
        except httpx.HTTPError: pass
        time.sleep(.1)
    client=httpx.Client(base_url=base,headers={'X-RAG':'1'},trust_env=False,timeout=60)
    def req(method,path,body=None):
        r=client.request(method,'/api'+path,json=body);r.raise_for_status();return r.json()
    check('Loopback health',req('GET','/health')['status']=='ok')
    credentials={'username':'release-admin','password':secrets.token_urlsafe(24)}
    r=client.post('/api/setup',json=credentials,headers={'X-Setup-Token':(STATE/'setup.token').read_text()});check('First admin with own setup token',r.status_code==200)
    check('Admin can inspect engine state without starting models',client.get('/api/engines').status_code==200)
    settings={'name':'llama','url':f'http://127.0.0.1:{mock.server_port}/v1','model':'qa-one','parameters':{'temperature':.35,'top_p':.8,'max_tokens':512,'context_length':8192}}
    req('POST','/providers',settings)
    req('POST','/providers',{**settings,'model':'qa-two','parameters':{'temperature':.7,'context_length':16384}})
    cfgs=req('GET','/providers')['llama'];check('Independent profiles persisted over HTTP',cfgs['profiles']['qa-one']['temperature']==.35 and cfgs['profiles']['qa-two']['context_length']==16384)
    probe=req('POST','/providers/test',{'name':'llama','model':'qa-one','inference':True})
    check('Real HTTP catalog and inference adapter',probe['models']==['qa-one','qa-two'] and probe['answer']=='READY [1]')
    check('Selected profile actually forwarded',payloads[-1]['temperature']==.35 and payloads[-1]['top_p']==.8 and payloads[-1]['max_tokens']==512)
    rejected=client.post('/api/providers/test',json={'name':'llama','model':'qa-one','inference':True,'parameters':{'context_length':65536}})
    check('Context above server capacity rejected',rejected.status_code==400)
    fixture_dir=tempfile.TemporaryDirectory(prefix='Atlas-Fictitious-QA-',dir=Path.home()/'Documents');docs=Path(fixture_dir.name);(docs/'fictitious.txt').write_text('FICTITIOUS RELEASE QA: the Atlas verification code is ALBATROS-427. No personal information.\n')
    (docs/'data.csv').write_text('x,y\n1,2\n2,4\n3,6\n4,8\n5,10\n')
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=595,height=842);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')});page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})});stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (FICTITIOUS PDF QA. Verification code ALBATROS-427. No personal data.) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
    with (docs/'fictitious.pdf').open('wb') as f:writer.write(f)
    from openpyxl import Workbook
    wb=Workbook();wb.active.append(['x','y']);wb.active.append([1,2]);wb.active.append([2,4]);wb.save(docs/'data.xlsx')
    browser=client.get('/api/folders',params={'path':str(docs)});check('Admin browses a Mac folder without typing its name',browser.status_code==200 and browser.json()['name']==docs.name and browser.json()['selectable'])
    check('Directory browser rejects system paths',client.get('/api/folders',params={'path':'/etc'}).status_code==400)
    cid=req('POST','/collections',{'name':'Fictitious release QA','path':str(docs),'embedding':'apple','language':'es'})['id'];req('POST',f'/collections/{cid}/index',{})
    for _ in range(120):
        files=req('GET',f'/collections/{cid}/files')
        if len(files)==4 and all(f['status']=='indexed' for f in files):break
        time.sleep(.2)
    check('CSV, Excel, PDF and text indexed',len(files)==4 and all(f['status']=='indexed' for f in files))
    result=req('POST','/search',{'query':'ALBATROS-427','collections':[cid],'mode':'hybrid'})
    check('Hybrid search returns document evidence',bool(result['results']))
    result=req('POST','/chat',{'query':'Código de verificación','collections':[cid],'provider':'llama','model':'qa-one'})
    check('RAG answer has sources',bool(result['sources']) and '[1]' in result['answer'])
    csv=next(f for f in files if f['path']=='data.csv');aid=req('POST','/analyses/prepare',{'file_id':csv['id'],'question':'Describe x and y','provider':'llama','model':'qa-one'})['id']
    result=req('POST',f'/analyses/{aid}/run',{})
    check('AI plan compiled and real sandboxed R completed',result['state']=='complete')
    archive=client.get(f'/api/analyses/{aid}/artifact/analysis.zip');z=zipfile.ZipFile(io.BytesIO(archive.content));check('Reproducible R export',{'analysis.R','input.csv','source.json','result.txt'}<=set(z.namelist()))
    tls=ssl.create_default_context(cafile=str(STATE/'lan-certificate.pem'));lan=f'https://{cfg["host"]}:{cfg["port"]}'
    mobile=httpx.Client(base_url=lan,verify=tls,trust_env=False,headers={'X-RAG':'1'},timeout=15)
    check('LAN HTTPS with certificate and hostname verification',mobile.get('/api/health').json()['status']=='ok')
    check('LAN protected without session',mobile.get('/api/collections').status_code==401)
    r=mobile.post('/api/login',json=credentials);check('LAN login uses secure HttpOnly cookie',r.status_code==200 and 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie'])
    check('LAN same collections and permissions',len(mobile.get('/api/collections').json())==1)
    check('LAN CSRF origin rejected',mobile.post('/api/search',json={'query':'x'},headers={'Origin':'https://evil.test'}).status_code==403)
    check('LAN unknown Host rejected',mobile.get('/api/health',headers={'Host':'evil.test'}).status_code==400)
    reader=req('POST','/users',{'username':'release-reader','password':credentials['password'],'role':'reader'})
    rc=httpx.Client(base_url=lan,verify=tls,trust_env=False,headers={'X-RAG':'1'});rc.post('/api/login',json={'username':'release-reader','password':credentials['password']})
    check('Engine control state is admin only',rc.get('/api/engines').status_code==403)
    check('Reader cannot stop engines',rc.post('/api/engines/action',json={'action':'stop'}).status_code==403)
    check('Directory browser is admin only',rc.get('/api/folders').status_code==403)
    check('LAN reader cannot see ungranted collections',rc.get('/api/collections').json()==[])
    check('LAN reader cannot fetch private file',rc.get(f'/api/files/{csv["id"]}/download').status_code==404)
    req('POST',f'/collections/{cid}/grants',{'user_id':reader['id'],'permission':'read'})
    check('LAN grant visible to reader',len(rc.get('/api/collections').json())==1)
    check('OAuth stays on the Mac',mobile.post('/api/oauth/start',json={}).status_code==400)
    tlsbad=ssl.create_default_context()
    try:httpx.get(lan+'/api/health',verify=tlsbad,trust_env=False,timeout=5);verified_untrusted=False
    except httpx.ConnectError:verified_untrusted=True
    check('Unpaired TLS trust fails closed',verified_untrusted)
finally:
    proc.terminate()
    try:proc.wait(12)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    mock.shutdown();log.close()
    if 'fixture_dir' in globals():fixture_dir.cleanup()
    for testport in [port,cfg['port']]:
        with socket.socket() as sock:check('Owned port released '+str(testport),sock.connect_ex(('127.0.0.1' if testport==port else cfg['host'],testport))!=0)
    (ROOT/'evidence/release-integration.json').write_text(json.dumps({'checks':checks,'count':len(checks),'qa_state':str(QA),'mock_local_inference':True,'real_R':True,'real_TLS':True,'production_modified':False},indent=2))
print(json.dumps({'passed':len(checks),'report':'evidence/release-integration.json'}))
