import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('RAG_STATE_DIR','/private/tmp/atlas-storage-tests')
from server import store,providers,network

def test_database_and_secrets_can_live_on_separate_volumes(monkeypatch,tmp_path):
    data=tmp_path/'external-data';vault=tmp_path/'private-vault';data.mkdir()
    for mod in [store,providers,network]:
        monkeypatch.setattr(mod,'STATE',data)
        monkeypatch.setattr(mod,'SECRET_STATE',vault)
    monkeypatch.setattr(store,'DB',data/'rag.sqlite3')
    monkeypatch.setattr(network,'address',lambda:'192.168.1.20')
    store.init();providers.save_secret(1,'openai',{'key':'fictitious-only'})
    network.configure(True)
    assert (data/'rag.sqlite3').exists() and (data/'network.json').exists()
    assert (vault/'setup.token').exists() and (vault/'credential-1-openai.json').exists()
    assert network.paths()[1].parent==vault
    assert not (data/'lan-key.pem').exists() and not list(data.glob('credential-*'))
    assert (vault/'lan-key.pem').stat().st_mode&0o777==0o600
    assert providers.load_secret(1,'openai')=={'key':'fictitious-only'}

def test_separate_workspaces_do_not_share_user_credentials(monkeypatch,tmp_path):
    monkeypatch.setattr(providers,'SECRET_STATE',tmp_path/'workspace-a')
    providers.save_secret(1,'openai',{'key':'fictitious-a'})
    monkeypatch.setattr(providers,'SECRET_STATE',tmp_path/'workspace-b')
    assert providers.load_secret(1,'openai')=={}
    providers.save_secret(1,'openai',{'key':'fictitious-b'})
    monkeypatch.setattr(providers,'SECRET_STATE',tmp_path/'workspace-a')
    assert providers.load_secret(1,'openai')['key']=='fictitious-a'
