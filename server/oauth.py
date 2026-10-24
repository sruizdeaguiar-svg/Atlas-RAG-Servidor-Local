"""Official Sign in with ChatGPT public-client flow; no borrowed client IDs or credentials."""
import secrets, time, hashlib, base64, uuid, urllib.parse, threading
import httpx, jwt
from .store import setting, set_setting
from .providers import load_secret,save_secret
PENDING={}; LOCK=threading.Lock()
ISSUER='https://auth.openai.com'
def begin(uid,origin):
    host=setting('oauth_host')
    if not host: host='urn:uuid:'+str(uuid.uuid4()); set_setting('oauth_host',host)
    previous=load_secret(uid,'openai'); client=previous.get('client_id') if previous.get('kind')=='oauth' else None
    verifier=secrets.token_urlsafe(48); state=secrets.token_urlsafe(32); nonce=secrets.token_urlsafe(32)
    redirect=origin+'/auth/callback'
    with LOCK:
        for k,v in list(PENDING.items()):
            if v['expires']<time.time(): PENDING.pop(k,None)
        PENDING[state]={'uid':uid,'client':client,'verifier':verifier,'nonce':nonce,'redirect':redirect,'expires':time.time()+600,'subject':previous.get('subject') if client else None}
    params={'client_id':client or 'dynamic_agent_client','ext_agent_host_id':host,'response_type':'code','redirect_uri':redirect,'scope':'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct','resource':'https://api.openai.com/v1','state':state,'nonce':nonce,'code_challenge_method':'S256','code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
    if not client: params['agent_name_hint']='Atlas RAG Local'
    return ISSUER+'/api/accounts/authorize?'+urllib.parse.urlencode(params)
def callback(params):
    state=params.get('state','')
    with LOCK: attempt=PENDING.pop(state,None)
    if not attempt or attempt['expires']<time.time(): raise ValueError('OAuth state invalid or expired; reconnect from Settings')
    if params.get('error'): raise ValueError('Authorization declined or unavailable; no connection saved')
    client=params.get('client_id') or attempt['client']
    if not client or client=='dynamic_agent_client' or (attempt['client'] and client!=attempt['client']): raise ValueError('OAuth registration incomplete or mismatched client')
    code=params.get('code')
    if not code: raise ValueError('OAuth authorization code missing')
    with httpx.Client(timeout=25,trust_env=False) as http:
        r=http.post(ISSUER+'/api/accounts/oauth/token',data={'grant_type':'authorization_code','client_id':client,'code':code,'code_verifier':attempt['verifier'],'redirect_uri':attempt['redirect'],'resource':'https://api.openai.com/v1'})
        if r.status_code!=200: raise ValueError('OpenAI rejected token exchange; start a new authorization')
        tokens=r.json()
        if 'chatgpt.tokens.use.direct' not in tokens.get('scope','').split(): raise ValueError('ChatGPT plan inference permission was not granted')
        # JWKS location is the published OpenAI auth keyset, never supplied by callback or token.
        r=http.get(ISSUER+'/.well-known/jwks.json'); r.raise_for_status()
        keys=jwt.PyJWKSet.from_dict(r.json()); header=jwt.get_unverified_header(tokens['id_token'])
        key=next((k for k in keys.keys if k.key_id==header.get('kid')),None)
        if not key: raise ValueError('OpenAI signature key unavailable')
        identity=jwt.decode(tokens['id_token'],key.key,algorithms=['RS256'],audience=client,issuer=ISSUER,options={'require':['exp','sub','iss','aud','nonce']})
        if not secrets.compare_digest(identity['nonce'],attempt['nonce']): raise ValueError('OAuth nonce mismatch')
        if attempt['subject'] and identity['sub']!=attempt['subject']: raise ValueError('Different ChatGPT account returned; disconnect before switching accounts')
    record={**tokens,'kind':'oauth','client_id':client,'subject':identity['sub'],'email':identity.get('email',''),'expires_at':time.time()+tokens.get('expires_in',3600)}
    save_secret(attempt['uid'],'openai',record)
    return identity.get('email','')
