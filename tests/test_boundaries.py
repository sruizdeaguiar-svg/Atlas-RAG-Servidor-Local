"""Verify security boundaries using real Apple Seatbelt and real R, never user data."""
import os,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['RAG_STATE_DIR']='/private/tmp/atlas-rag-boundary-state'
from server.store import init,STATE
from server import analysis,providers,oauth
import pytest
init()

def execute(script):
    ident=uuid.uuid4().hex;work=STATE/'analyses'/ident;work.mkdir(parents=True)
    (work/'input.csv').write_text('x,y\n1,2\n2,4\n3,6\n')
    (work/'analysis.R').write_text(script)
    return analysis.run(ident)

def test_r_cannot_read_other_data():
    sentinel=Path('/private/tmp/atlas-outside-sentinel.txt');sentinel.write_text('FICTITIOUS OUTSIDE DATA')
    r=execute('print(readLines("'+str(sentinel)+'"))')
    assert r['state']=='failed' and ('Permission denied' in r['result'] or 'Operation not permitted' in r['result'])
    assert 'FICTITIOUS OUTSIDE DATA' not in r['result']

def test_r_cannot_write_outside():
    path=Path('/private/tmp/atlas-denied-output.txt');path.unlink(missing_ok=True)
    r=execute('writeLines("forbidden","'+str(path)+'")')
    assert r['state']=='failed' and not path.exists()

def test_r_cannot_connect_network():
    r=execute('readLines(url("http://127.0.0.1:1234/v1/models",open="r"))')
    assert r['state']=='failed' and 'cannot open' in r['result']

def test_r_vector_memory_limit():
    r=execute('x <- numeric(200000000); print(length(x))')
    assert r['state']=='failed' and ('memory' in r['result'].lower() or 'vector' in r['result'].lower())

def test_plan_column_injection_is_data():
    name='x");system("touch /private/tmp/pwn");#'
    code=analysis.compile_r(analysis.Plan(method='describe',columns=[name]),{'columns':[{'name':name,'type':'number'}]})
    assert '\\"' in code

def test_unknown_plan_variable_rejected():
    with pytest.raises(ValueError): analysis.compile_r(analysis.Plan(method='correlation',columns=['unknown','x']),{'columns':[{'name':'x','type':'number'}]})

def test_provider_ssrf_rejected():
    for url in ['http://example.com/v1','http://192.168.1.3/v1','http://127.0.0.1.evil.test/v1','http://127.0.0.1:1234/v1?token=secret','http://user:pass@127.0.0.1:1234/v1']:
        with pytest.raises(ValueError): providers.validate_url('llama',url)

def test_oauth_state_single_use_and_pkce():
    import urllib.parse
    url=oauth.begin(999,'http://127.0.0.1:8777');p=urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert p['client_id']==['dynamic_agent_client'] and p['code_challenge_method']==['S256']
    assert p['redirect_uri']==['http://127.0.0.1:8777/auth/callback']
    assert p['ext_agent_host_id'][0].startswith('urn:uuid:')
    with pytest.raises(ValueError): oauth.callback({'state':p['state'][0],'error':'access_denied'})
    with pytest.raises(ValueError): oauth.callback({'state':p['state'][0],'code':'unused'})

def test_source_change_during_snapshot_rejected(monkeypatch,tmp_path):
    import shutil
    source=tmp_path/'data.csv';source.write_text('x\n1\n')
    original=shutil.copyfile
    def changing_copy(src,dst):
        original(src,dst); Path(src).write_text('x\n999\n')
    monkeypatch.setattr(analysis.shutil,'copyfile',changing_copy)
    with pytest.raises(ValueError,match='Source changed'):
        analysis.prepare(1,{'id':1,'path':'data.csv'},{'id':1,'path':str(tmp_path)},analysis.Plan(),'')
