"""OIDC validation with ephemeral signing keys and fictitious tokens; no account access."""
import os,sys,json,time,urllib.parse
from pathlib import Path
os.environ.setdefault('RAG_STATE_DIR','/private/tmp/atlas-rag-oauth-tests')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest,jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from server import oauth

@pytest.mark.parametrize('case',['valid','wrong_nonce','wrong_audience','expired','wrong_issuer','missing_permission','returning_client_mismatch'])
def test_oidc_validation(monkeypatch,case):
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    client='oaiapp_fictitious_test_client'
    monkeypatch.setattr(oauth,'setting',lambda *args:'urn:uuid:11111111-1111-4111-8111-111111111111')
    monkeypatch.setattr(oauth,'load_secret',lambda *args: {'kind':'oauth','client_id':client,'subject':'qa-subject'} if case=='returning_client_mismatch' else {})
    saved=[];monkeypatch.setattr(oauth,'save_secret',lambda *args:saved.append(args))
    url=oauth.begin(999,'http://127.0.0.1:8777')
    state=urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['state'][0]
    attempt=oauth.PENDING[state]
    claims={'sub':'qa-subject','iss':'https://auth.openai.com','aud':client,'exp':time.time()+300,'nonce':attempt['nonce']}
    if case=='wrong_nonce':claims['nonce']='invalid'
    if case=='wrong_audience':claims['aud']='wrong-client'
    if case=='expired':claims['exp']=time.time()-3600
    if case=='wrong_issuer':claims['iss']='https://untrusted.example'
    token=jwt.encode(claims,private,algorithm='RS256',headers={'kid':'qa-key'})
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()));jwk['kid']='qa-key'
    class Reply:
        status_code=200
        def __init__(self,data):self.data=data
        def json(self):return self.data
        def raise_for_status(self):pass
    class Client:
        def __init__(self,**kwargs):assert kwargs['trust_env'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            assert url=='https://auth.openai.com/api/accounts/oauth/token'
            assert kwargs['data']['client_id']==client
            assert kwargs['data']['redirect_uri']==attempt['redirect']
            assert kwargs['data']['code_verifier']==attempt['verifier']
            return Reply({'id_token':token,'access_token':'fictitious-access-token','refresh_token':'fictitious-refresh-token','scope':'openid profile email' if case=='missing_permission' else 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct','expires_in':3600})
        def get(self,url):
            assert url=='https://auth.openai.com/.well-known/jwks.json'
            return Reply({'keys':[jwk]})
    monkeypatch.setattr(oauth.httpx,'Client',Client)
    params={'state':state,'code':'fictitious-authorization-code','client_id':'different-client' if case=='returning_client_mismatch' else client}
    if case=='valid':
        oauth.callback(params)
        assert len(saved)==1 and saved[0][2]['subject']=='qa-subject'
        assert saved[0][2]['client_id']==client
    else:
        with pytest.raises((ValueError,jwt.InvalidTokenError)):oauth.callback(params)
        assert not saved
    assert state not in oauth.PENDING
