import json, ipaddress, urllib.parse, subprocess, os, time, threading
import httpx
from fastapi import HTTPException
from .store import setting, set_setting, STATE, SECRET_STATE
DEFAULTS={
 'llama':{'url':'http://127.0.0.1:8080/v1','model':''},
 'omlx':{'url':'http://127.0.0.1:8000/v1','model':''},
 'vllm':{'url':'http://127.0.0.1:8001/v1','model':''},
 'lmstudio':{'url':'http://127.0.0.1:1234/v1','model':''},
 'openai':{'url':'https://api.openai.com/v1','model':''}}
# Per-user secrets are protected files, never returned by configuration APIs.
def secret_path(uid, name): return SECRET_STATE / f'credential-{int(uid)}-{name}.json'
def save_secret(uid,name,value):
    SECRET_STATE.mkdir(parents=True,exist_ok=True);SECRET_STATE.chmod(0o700)
    p=secret_path(uid,name); tmp=p.with_suffix('.tmp')
    fd=os.open(tmp,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f: json.dump(value,f)
    os.replace(tmp,p); p.chmod(0o600)
def load_secret(uid,name):
    p=secret_path(uid,name)
    return json.loads(p.read_text()) if p.exists() else {}
def config(): return setting('providers',DEFAULTS)
def validate_url(name,url):
    p=urllib.parse.urlsplit(url)
    if p.username or p.password or p.query or p.fragment: raise ValueError('URL must not contain credentials, query or fragment')
    if name=='openai':
        if url.rstrip('/')!='https://api.openai.com/v1': raise ValueError('OpenAI URL must be official')
    else:
        try: local=ipaddress.ip_address(p.hostname).is_loopback
        except ValueError: local=False
        if not local or p.scheme!='http' or p.path.rstrip('/')!='/v1': raise ValueError('Local providers require a loopback HTTP /v1 endpoint')
    return url.rstrip('/')
def headers(uid,name):
    s=load_secret(uid,name)
    if name=='openai' and s.get('kind')=='oauth': s=oauth_token(uid)
    key=s.get('access_token') or s.get('key')
    return {'Authorization':'Bearer '+key} if key else {}
def catalog(uid,name,consent=False):
    if name not in DEFAULTS: raise ValueError('Unknown provider')
    if name=='openai' and not consent: raise ValueError('Explicit consent required for OpenAI network access')
    url=validate_url(name,config()[name]['url']); auth=headers(uid,name)
    try:
        r=httpx.get(url+'/models',headers=auth,timeout=12,trust_env=False)
        if r.status_code>=400: raise ValueError(f'{name}: HTTP {r.status_code}; check server and credential')
        raw=r.json(); out=[]
        for m in raw.get('data',raw.get('models',[])):
            if m.get('visibility','list')!='list': continue
            ident=m.get('id') or m.get('slug')
            if not ident: continue
            levels=m.get('supported_reasoning_levels',m.get('supported_reasoning_efforts',[]))
            out.append({'id':ident,'name':m.get('display_name') or ident,
                'reasoning_levels':[x.get('effort') if isinstance(x,dict) else x for x in levels],
                'default_reasoning':m.get('default_reasoning_level',m.get('default_reasoning_effort','')),
                'max_context':m.get('context_window') or m.get('max_context_length') or m.get('max_model_len'),
                'active_context':None,'loaded':None,'type':m.get('type','llm')})
        if name=='lmstudio':
            # Optional read-only native metadata. Never load/unload models here.
            try:
                meta=httpx.get(url[:-3]+'/api/v1/models',headers=auth,timeout=8,trust_env=False)
                if meta.status_code==200:
                    native=meta.json().get('models',[])
                    for item in out:
                        match=next((m for m in native if m.get('key')==item['id'] or any(i.get('id')==item['id'] for i in m.get('loaded_instances',[]))),None)
                        if match:
                            instances=match.get('loaded_instances',[])
                            active=next((i for i in instances if i.get('id')==item['id']),instances[0] if instances else {})
                            item.update(name=match.get('display_name',item['id']),loaded=bool(instances),type=match.get('type','llm'),max_context=match.get('max_context_length'),active_context=active.get('config',{}).get('context_length'),configuration=active.get('config',{}),quantization=match.get('quantization'),size_bytes=match.get('size_bytes'))
            except (httpx.HTTPError,ValueError): pass
        if name=='llama':
            try:
                r=httpx.get(url[:-3]+'/props',headers=auth,timeout=5,trust_env=False)
                if r.status_code==200:
                    props=r.json(); ctx=props.get('default_generation_settings',{}).get('n_ctx')
                    for item in out: item['active_context']=ctx
            except (httpx.HTTPError,ValueError): pass
        return out
    except httpx.HTTPError: raise ValueError(f'{name}: endpoint unavailable')
def embedding_models(uid,name):
    if name not in {'llama','omlx','vllm','lmstudio'}:
        raise ValueError('Select a local embedding provider')
    # Prefer explicit capability metadata; older compatible servers expose names only.
    def supports_embedding(item):
        kind=str(item.get('type','')).lower()
        ident=(item['id']+' '+item.get('name','')).lower()
        return kind in {'embedding','embeddings','text-embedding'} or any(x in ident for x in ['embed','bge-','minilm','e5-','gte-'])
    return [m for m in catalog(uid,name) if supports_embedding(m)]

def models(uid,name,consent=False): return [m['id'] for m in catalog(uid,name,consent)]

def validated_profile(value):
    allowed={'temperature','top_p','max_tokens','context_length','reasoning_effort'}
    if set(value)-allowed: raise ValueError('Unknown model parameter')
    out={'temperature':0.1,'top_p':1.0,'max_tokens':3072,'context_length':0,'reasoning_effort':''}
    out.update(value)
    for key,low,high in [('temperature',0,2),('top_p',0.01,1),('max_tokens',1,131072),('context_length',0,2000000)]:
        v=out[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not low<=v<=high: raise ValueError('Invalid '+key)
        if key in {'max_tokens','context_length'} and int(v)!=v: raise ValueError('Expected integer '+key)
    if out['context_length'] and out['context_length']<=out['max_tokens']: raise ValueError('Context must exceed maximum output tokens')
    if out['reasoning_effort'] not in {'','none','minimal','low','medium','high','xhigh','max','ultra'}: raise ValueError('Invalid reasoning effort')
    return out

def complete(uid,name,messages,model=None,consent=False,reasoning_effort=None,parameters=None):
    if name not in DEFAULTS: raise ValueError('Unknown provider')
    if name=='openai' and not consent: raise ValueError('Explicit consent required to send context to OpenAI')
    cfg=config()[name]; url=validate_url(name,cfg['url']); model=model or cfg['model']
    if not model: raise ValueError('Select a generation model in Settings')
    profile=validated_profile({**cfg.get('profiles',{}).get(model,{}),**(parameters or {})})
    effort=profile['reasoning_effort'] if reasoning_effort is None else reasoning_effort
    if name=='openai' and effort:
        entry=next((m for m in catalog(uid,name,consent) if m['id']==model),None)
        if not entry or effort not in entry['reasoning_levels']: raise ValueError('Reasoning level is not supported by the selected model')
    if name=='lmstudio':
        entry=next((m for m in catalog(uid,name) if m['id']==model),None)
        if entry and entry.get('loaded') is False: raise ValueError('Load this model in LM Studio first; Atlas will not change running engines automatically')
    context_limit=profile['context_length']
    if name!='openai' and not context_limit:
        # The engine's actual load context applies even without a saved profile.
        from . import engines
        active_engine=engines.record()
        if active_engine.get('name')==name and active_engine.get('api_model')==model and url==f'http://127.0.0.1:{engines.PORTS[name]}/v1':
            context_limit=active_engine.get('context',0)
    if name!='openai' and context_limit:

        entry=next((m for m in catalog(uid,name) if m['id']==model),None)
        if not entry: raise ValueError('Selected model is no longer available')
        active=entry.get('active_context') or entry.get('max_context')
        if active and context_limit>active: raise ValueError(f'Requested context exceeds server capacity ({active}); change the context in the engine before retrying')
        # UTF-8 bytes form a conservative upper token bound, plus chat-template reserve.
        budget=sum(len(m.get('content','').encode('utf-8'))+64 for m in messages)+profile['max_tokens']+256
        if budget>context_limit: raise ValueError(f'Input plus reserved output exceeds the Atlas context limit ({context_limit} tokens); increase the loaded context or reduce the selected results/variables. No results were silently truncated.')
    try:
        with httpx.Client(timeout=httpx.Timeout(600,connect=10),trust_env=False) as client:
            if name=='openai':
                answer=''; completed=False
                payload={'model':model,'input':[{**m,'role':'developer' if m['role']=='system' else m['role']} for m in messages],'store':False,'stream':True}
                if effort: payload['reasoning']={'effort':effort}
                with client.stream('POST',url+'/responses',headers=headers(uid,name),json=payload) as r:
                    if r.status_code>=400: raise ValueError(f'OpenAI HTTP {r.status_code}; check authorization and account limits')
                    for line in r.iter_lines():
                        if not line.startswith('data: '): continue
                        if line[6:]=='[DONE]': continue
                        e=json.loads(line[6:])
                        if e.get('type')=='response.output_text.delta': answer+=e.get('delta','')
                        if e.get('type')=='response.completed': completed=True
                        if e.get('type') in {'error','response.failed','response.incomplete'}: raise ValueError('OpenAI response failed or incomplete')
                if not completed: raise ValueError('OpenAI stream interrupted before completion')
                return answer
            r=client.post(url+'/chat/completions',headers=headers(uid,name),json={'model':model,'messages':messages,'max_tokens':profile['max_tokens'],'temperature':profile['temperature'],'top_p':profile['top_p'],'stream':False})
            if r.status_code>=400:
                # Classify the error without exposing a server response that may echo private prompts.
                detail=r.text[:8192].lower()
                if any(x in detail for x in ['context size','context length','context_length','context window','n_ctx','too many tokens','maximum context','context_length_exceeded']):
                    raise ValueError(f'{name}: el contexto cargado no admite estos resultados. Carga el modelo con 65536 tokens o reduce las variables; HTTP {r.status_code}. / Loaded context is too small for these results; load 65536 tokens or select fewer variables.')
                raise ValueError(f'{name}: HTTP {r.status_code}; el motor rechazó la petición. Revisa el modelo y su registro en Modelos e IA. / The engine rejected the request; check its model and log in Models & AI.')
            answer=r.json()['choices'][0]['message'].get('content') or ''
            if not answer.strip(): raise ValueError('Model returned no final answer; reduce context or choose another model')
            return answer
    except httpx.HTTPError: raise ValueError(f'{name}: request failed or timed out')

def embed(uid,name,model,texts):
    if name=='openai': raise ValueError('Cloud embeddings are disabled to keep indexing local')
    cfg=config()[name]; url=validate_url(name,cfg['url'])
    try:
        r=httpx.post(url+'/embeddings',headers=headers(uid,name),json={'model':model,'input':texts},timeout=90,trust_env=False)
        if r.status_code>=400: raise ValueError(f'Embedding HTTP {r.status_code}')
        data=sorted(r.json()['data'],key=lambda d:d['index']); vectors=[d['embedding'] for d in data]
        if len(vectors)!=len(texts) or not vectors: raise ValueError('Incomplete embeddings')
        return {'model':f'{name}:{url}:{model}:{len(vectors[0])}','vectors':vectors}
    except httpx.HTTPError: raise ValueError('Local embedding provider unavailable')

_refresh_lock=threading.Lock()
def oauth_token(uid):
    with _refresh_lock:
        s=load_secret(uid,'openai')
        if s.get('expires_at',0)>time.time()+60: return s
        if not s.get('refresh_token'): raise ValueError('Reconnect with ChatGPT')
        try:
            r=httpx.post('https://auth.openai.com/api/accounts/oauth/token',data={'grant_type':'refresh_token','client_id':s['client_id'],'refresh_token':s['refresh_token'],'resource':'https://api.openai.com/v1'},timeout=20,trust_env=False)
            if r.status_code!=200: raise ValueError('OpenAI session expired; reconnect')
            t=r.json(); s.update(t); s['expires_at']=time.time()+t.get('expires_in',3600)
            if 'chatgpt.tokens.use.direct' not in s.get('scope','').split(): raise ValueError('ChatGPT plan permission missing')
            save_secret(uid,'openai',s); return s
        except httpx.HTTPError: raise ValueError('OpenAI refresh unavailable')
