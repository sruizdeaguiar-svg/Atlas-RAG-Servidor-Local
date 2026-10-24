"""Start/stop an isolated fictitious mobile QA workspace; never production."""
import os,sys,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
STATE=Path('/private/tmp/atlas-mobile-qa');os.environ['RAG_STATE_DIR']=str(STATE);os.environ['RAG_PORT']='18865'
from server.store import init,db,rows,password_hash
from server import network
from scripts import control
if len(sys.argv)>1 and sys.argv[1]=='stop':
    r=control.stop();print(json.dumps({'running':r['running'],'rss':r['rss']}));sys.exit()
init()
with db() as c:
    if not rows('SELECT id FROM users WHERE username=?',('mobile-qa',)):
        c.execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',('mobile-qa',password_hash('Atlas-Fictitious-Only-2026'),'admin'))
network.configure(True);cfg=network.config();cfg['port']=18767;(STATE/'network.json').write_text(json.dumps(cfg))
r=control.start()
import httpx
client=httpx.Client(base_url=r['url'],headers={'X-RAG':'1'},trust_env=False,timeout=45)
client.post('/api/login',json={'username':'mobile-qa','password':'Atlas-Fictitious-Only-2026'}).raise_for_status()
cols=client.get('/api/collections').json()
if not cols:
    docs=STATE.parent/'atlas-mobile-fixtures';docs.mkdir(exist_ok=True)
    (docs/'bienvenida.txt').write_text('DATOS FICTICIOS. Atlas conecta el iPhone con el servidor del Mac. Código de prueba ALBATROS-427.\n')
    (docs/'datos.csv').write_text('x,y\n1,2\n2,4\n3,6\n4,8\n')
    c=client.post('/api/collections',json={'name':'Biblioteca de prueba móvil','path':str(docs),'embedding':'apple'});c.raise_for_status();cid=c.json()['id']
    client.post(f'/api/collections/{cid}/index',json={}).raise_for_status()
    for _ in range(100):
        files=client.get(f'/api/collections/{cid}/files').json()
        if len(files)==2 and all(f['status']=='indexed' for f in files):break
        time.sleep(.2)
record={'state':str(STATE),'url':r['url'],'network':network.public(),'pid':r['pid']}
(ROOT/'evidence/mobile-qa.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
