import sys,json,os
os.environ.setdefault("RAG_STATE_DIR","/private/tmp/atlas-rag-boundary-state")
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest,httpx
from server import providers
class Reply:
    status_code=200
    def __init__(self,body): self.body=body
    def json(self): return self.body
@pytest.mark.parametrize('name',['llama','omlx','vllm','lmstudio'])
def test_local_protocol_adapters(monkeypatch,name):
    cfg={k:dict(v) for k,v in providers.DEFAULTS.items()};cfg[name]['model']='fixture-model'
    monkeypatch.setattr(providers,'config',lambda:cfg)
    monkeypatch.setattr(providers,'headers',lambda uid,name:{})
    def get(url,**kw):
        if url!=cfg[name]['url']+'/models':
            raise httpx.ConnectError('Optional metadata unavailable')
        assert kw['trust_env'] is False
        return Reply({'data':[{'id':'fixture-model'}]})
    class Client:
        def __init__(self,**kw): assert kw['trust_env'] is False
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,**kw):
            assert url==cfg[name]['url']+'/chat/completions'
            assert kw['json']['model']=='fixture-model' and kw['json']['stream'] is False
            return Reply({'choices':[{'message':{'content':'fixture response'}}]})
    monkeypatch.setattr(providers.httpx,'get',get);monkeypatch.setattr(providers.httpx,'Client',Client)
    assert providers.models(1,name)==['fixture-model']
    assert providers.complete(1,name,[{'role':'user','content':'test'}])=='fixture response'

def test_profiles_bounds_and_context():
    for value in [{'temperature':-1},{'top_p':2},{'max_tokens':1.5},{'context_length':100,'max_tokens':200},{'reasoning_effort':'invented'},{'context_length':float('nan')}]:
        with pytest.raises(ValueError): providers.validated_profile(value)

def test_local_profile_payload_and_capacity(monkeypatch):
    cfg={k:dict(v) for k,v in providers.DEFAULTS.items()};cfg['lmstudio'].update(model='fixture',profiles={'fixture':{'temperature':0.65,'top_p':0.8,'max_tokens':128,'context_length':4096}})
    monkeypatch.setattr(providers,'config',lambda:cfg);monkeypatch.setattr(providers,'headers',lambda *a:{})
    monkeypatch.setattr(providers,'catalog',lambda *a:[{'id':'fixture','active_context':8192,'loaded':True}])
    class Client:
        def __init__(self,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def post(self,url,**kw):
            p=kw['json'];assert p['temperature']==0.65 and p['max_tokens']==128 and p['top_p']==0.8
            assert 'context_length' not in p # Not a Chat Completions parameter.
            return Reply({'choices':[{'message':{'content':'READY'}}]})
    monkeypatch.setattr(providers.httpx,'Client',Client)
    assert providers.complete(1,'lmstudio',[{'role':'user','content':'test'}])=='READY'
    with pytest.raises(ValueError,match='capacity'): providers.complete(1,'lmstudio',[],parameters={'context_length':16384})
    with pytest.raises(ValueError,match='exceeds the Atlas'): providers.complete(1,'lmstudio',[{'role':'user','content':'x'*5000}])

def test_openai_reasoning_payload(monkeypatch):
    cfg={k:dict(v) for k,v in providers.DEFAULTS.items()};cfg['openai']['model']='fixture'
    monkeypatch.setattr(providers,'config',lambda:cfg);monkeypatch.setattr(providers,'headers',lambda *a:{})
    monkeypatch.setattr(providers,'catalog',lambda *a:[{'id':'fixture','reasoning_levels':['low','high']}])
    class Stream:
        status_code=200
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def iter_lines(self): return ['data: '+json.dumps({'type':'response.output_text.delta','delta':'READY'}),'data: '+json.dumps({'type':'response.completed'})]
    class Client:
        def __init__(self,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def stream(self,method,url,**kw):
            assert kw['json']['reasoning']=={'effort':'high'}
            assert kw['json']['store'] is False and kw['json']['stream'] is True
            return Stream()
    monkeypatch.setattr(providers.httpx,'Client',Client)
    assert providers.complete(1,'openai',[],consent=True,reasoning_effort='high')=='READY'
    with pytest.raises(ValueError,match='not supported'): providers.complete(1,'openai',[],consent=True,reasoning_effort='ultra')
    with pytest.raises(ValueError,match='consent'): providers.complete(1,'openai',[])

def test_r_plan_passes_reasoning(monkeypatch):
    from server import analysis
    def complete(*a):
        assert a[-1]=='high'
        return '{"method":"describe","columns":["x"]}'
    monkeypatch.setattr(analysis,'complete',complete)
    assert analysis.ai_plan(1,'openai','fixture','Describe',{'columns':[]},True,'high').method=='describe'

def test_model_profile_persistence(tmp_path,monkeypatch):
    from server import app as api
    saved={'providers':{k:dict(v) for k,v in providers.DEFAULTS.items()}}
    monkeypatch.setattr(providers,'config',lambda:saved['providers'])
    monkeypatch.setattr(api,'set_setting',lambda key,value:saved.__setitem__(key,value))
    monkeypatch.setattr(api,'audit',lambda *a:None)
    u={'id':1}
    api.provider_save(api.ProviderInput(name='llama',url=providers.DEFAULTS['llama']['url'],model='first',parameters={'temperature':0.25,'context_length':8192}),u)
    api.provider_save(api.ProviderInput(name='llama',url=providers.DEFAULTS['llama']['url'],model='second',parameters={'temperature':0.8,'context_length':16384}),u)
    profiles=saved['providers']['llama']['profiles']
    assert profiles['first']['temperature']==0.25 and profiles['first']['context_length']==8192
    assert profiles['second']['temperature']==0.8 and profiles['second']['context_length']==16384
    api.provider_save(api.ProviderInput(name='llama',url='http://127.0.0.1:9080/v1',model='first'),u)
    assert not saved['providers']['llama']['profiles']

def test_real_catalog_metadata_and_hidden_models(monkeypatch):
    monkeypatch.setattr(providers,'config',lambda:providers.DEFAULTS)
    monkeypatch.setattr(providers,'headers',lambda *a:{})
    monkeypatch.setattr(providers.httpx,'get',lambda *a,**k:Reply({'models':[{'slug':'visible','display_name':'Visible','context_window':500000,'supported_reasoning_levels':[{'effort':'low'},{'effort':'high'}],'default_reasoning_level':'low'},{'slug':'hidden','visibility':'hide'}]}))
    data=providers.catalog(1,'openai',True)
    assert len(data)==1 and data[0]['reasoning_levels']==['low','high'] and data[0]['max_context']==500000
