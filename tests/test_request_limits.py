import pytest
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from server.security import RequestBodyLimit

@pytest.fixture
def client():
    app=FastAPI();app.add_middleware(RequestBodyLimit,json_limit=32,upload_limit=64)
    @app.post('/api/login')
    @app.post('/api/collections/{cid}/upload')
    async def body(request:Request):return {'size':len(await request.body())}
    return TestClient(app)

def test_chunked_body_is_bounded_before_parsing(client):
    assert client.post('/api/login',content=iter([b'x'*20,b'x'*20])).status_code==413

def test_declared_length_does_not_override_actual_limit(client):
    assert client.post('/api/login',content=b'x'*40,headers={'Content-Length':'1'}).status_code==413

def test_bounded_requests_replay_all_chunks(client):
    assert client.post('/api/login',content=iter([b'abc',b'def'])).json()=={'size':6}

def test_upload_has_a_separate_bounded_budget(client):
    assert client.post('/api/collections/1/upload',content=iter([b'x'*40])).json()=={'size':40}
    assert client.post('/api/collections/1/upload',content=iter([b'x'*65])).status_code==413
