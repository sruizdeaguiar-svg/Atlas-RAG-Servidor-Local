import os,sys,json,socket,subprocess
from pathlib import Path
import pytest
from server import engines

@pytest.fixture
def manager(tmp_path,monkeypatch):
    modeldir=tmp_path/'models';modeldir.mkdir();(modeldir/'tiny.gguf').write_bytes(b'fictitious weights')
    monkeypatch.setattr(engines,'ROOT',tmp_path/'engines')
    cfg={'enabled':True,'roots':[str(modeldir)],'binaries':{n:sys.executable for n in engines.NAMES}}
    monkeypatch.setattr(engines,'config',lambda:cfg)
    monkeypatch.setattr(engines,'budget',lambda *a:0)
    monkeypatch.setattr(engines,'close_lmstudio_completely',lambda:None)
    monkeypatch.setattr(engines.providers,'config',lambda:{n:{'url':'http://127.0.0.1:1234/v1','model':''} for n in engines.NAMES})
    monkeypatch.setattr(engines,'set_setting',lambda *a:None)
    yield modeldir
    engines.stop_all()

def test_unknown_model_cannot_stop_current_engine(manager,monkeypatch):
    stopped=[];monkeypatch.setattr(engines,'stop_all',lambda:stopped.append(True))
    with pytest.raises(ValueError):engines.select('llama','outside-catalog')
    assert not stopped

def test_catalog_only_contains_installed_model_files(manager):
    (manager/'not-a-model.txt').write_text('not a model')
    result=engines.local_models('llama')
    assert len(result)==1 and result[0]['name']=='tiny.gguf'
    assert result[0]['api_model'].startswith('atlas-')
    with pytest.raises(ValueError):engines.local_models('other')

def test_pid_reuse_and_other_workspace_are_never_owned(manager):
    p=__import__('psutil').Process()
    assert engines.alive({'pid':p.pid,'created':p.create_time()+5}) is None
    assert engines.alive({'pid':p.pid,'created':p.create_time()}) is None

def test_switch_closes_previous_before_start(manager,monkeypatch):
    events=[]
    monkeypatch.setattr(engines,'stop_all',lambda:events.append('stop-complete'))
    monkeypatch.setattr(engines,'launch',lambda n,m,c:events.append('start') or {'api_model':m['api_model']})
    model=engines.local_models('llama')[0]
    engines.select('llama',model['id'])
    assert events==['stop-complete','start']

def test_memory_guard_rejects_oversize_before_launch(monkeypatch):
    monkeypatch.setattr(engines.psutil,'virtual_memory',lambda:type('Memory',(),{'available':4*1024**3})())
    with pytest.raises(ValueError):engines.budget({'size_bytes':8*1024**3},4096)

def test_status_handles_exit_during_process_inspection(manager,monkeypatch):
    import psutil
    class Exiting:
        def children(self,recursive=True):raise psutil.NoSuchProcess(123)
    with monkeypatch.context() as patch:
        patch.setattr(engines,'record',lambda:{'name':'llama','pid':123})
        patch.setattr(engines,'alive',lambda r:Exiting())
        patch.setattr(engines,'lmstudio_status',lambda:{'application_running':False})
        assert not engines.status()['running']


def test_stop_terminates_own_children_and_releases_port(manager):
    import psutil,time
    engines.ROOT.mkdir()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1'],cwd=engines.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    engines.CHILDREN[proc.pid]=proc
    engines.save({'name':'llama','pid':proc.pid,'created':psutil.Process(proc.pid).create_time(),'port':port})
    for _ in range(50):
        if engines.listening(port):break
        time.sleep(.02)
    assert engines.listening(port)
    engines.stop_all()
    assert proc.poll() is not None and not engines.listening(port) and not engines.record()

def test_stop_external_requires_same_reviewed_inventory(monkeypatch):
    stopped=[]
    monkeypatch.setattr(engines,'external_inventory',lambda:{'servers':[],'confirmation':'new-list'})
    monkeypatch.setattr(engines,'stop_all',lambda:stopped.append(True))
    with pytest.raises(ValueError):engines.stop_external('old-list')
    assert not stopped

def test_embedding_catalog_separates_chat_from_encoder(manager):
    (manager/'bge-small.gguf').write_bytes(b'encoder')
    assert [m['name'] for m in engines.local_models('llama','embedding')]==['bge-small.gguf']
    assert [m['name'] for m in engines.local_models('llama')]==['tiny.gguf']

def test_embedding_selection_preserves_chat_default(manager,monkeypatch):
    (manager/'bge-small.gguf').write_bytes(b'encoder')
    cfg={n:{'url':'http://127.0.0.1:1234/v1','model':'chat-default'} for n in engines.NAMES}
    monkeypatch.setattr(engines.providers,'config',lambda:cfg)
    events=[]
    monkeypatch.setattr(engines,'stop_all',lambda:events.append('stopped'))
    monkeypatch.setattr(engines,'launch',lambda n,m,c:events.append(m['type']) or {'api_model':m['api_model']})
    model=engines.local_models('llama','embedding')[0]
    engines.select('llama',model['id'])
    assert events==['stopped','embedding'] and cfg['llama']['model']=='chat-default'

def test_embedding_readiness_requires_real_vectors(monkeypatch):
    class Response:
        status_code=200
        def json(self):return {'data':[]}
    monkeypatch.setattr(engines.httpx,'post',lambda *a,**k:Response())
    with pytest.raises(ValueError,match='no vectors'):engines.verify_embedding(18880,'encoder')


def test_switch_away_from_lmstudio_closes_app_before_new_engine(manager,monkeypatch):
    events=[]
    monkeypatch.setattr(engines,'stop_all',lambda:events.append('stop-owned'))
    monkeypatch.setattr(engines,'close_lmstudio_completely',lambda:events.append('quit-lmstudio'))
    monkeypatch.setattr(engines,'launch',lambda n,m,c:events.append('launch-new') or {'api_model':m['api_model']})
    engines.select('llama',engines.local_models('llama')[0]['id'])
    assert events==['stop-owned','quit-lmstudio','launch-new']
