"""Update restart must respect current access rather than stale job ownership."""
from server import app as api
from fastapi import HTTPException

def test_resume_requires_current_collection_write_access(monkeypatch):
    calls=[]
    monkeypatch.setattr(api,'setting',lambda *args:[{'collection_id':1,'user_id':2},{'collection_id':3,'user_id':4}])
    monkeypatch.setattr(api,'set_setting',lambda *args:calls.append(('clear',args)))
    monkeypatch.setattr(api,'rows',lambda sql,args:[{'id':args[0],'username':'fictitious','role':'editor'}])
    def permission(cid,user,write):
        if cid==1:raise HTTPException(403)
        assert write
    monkeypatch.setattr(api,'collection',permission)
    monkeypatch.setattr(api.indexing,'start',lambda cid,uid:calls.append(('start',cid,uid)))
    monkeypatch.setattr(api,'audit',lambda *args:None)
    api.resume_update_indexing()
    assert calls==[('clear',('resume_after_update',[])),('start',3,4)]
