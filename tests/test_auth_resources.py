"""Authentication work and failure tracking have finite resource budgets."""
from collections import OrderedDict
from types import SimpleNamespace
import pytest
from fastapi import HTTPException,Response
from server import app as api

def test_login_refuses_when_password_workers_are_busy(monkeypatch):
    class Busy:
        def acquire(self,blocking=False):return False
    monkeypatch.setattr(api,'AUTH_WORKERS',Busy())
    monkeypatch.setattr(api,'login_checked',lambda *args:pytest.fail('Must not hash when busy'))
    with pytest.raises(HTTPException) as result:
        api.login(api.Credentials(username='fictitious',password='Fictitious-only-2026'),None,Response())
    assert result.value.status_code==429

def test_failure_maps_are_bounded_and_ip_limit_applies(monkeypatch):
    monkeypatch.setattr(api,'FAILURES',OrderedDict((str(i),[api.time.time()]) for i in range(4096)))
    monkeypatch.setattr(api,'IP_FAILURES',OrderedDict((str(i),[api.time.time()]) for i in range(512)))
    monkeypatch.setattr(api,'rows',lambda *args:[])
    request=SimpleNamespace(client=SimpleNamespace(host='fictitious-test-client'))
    credentials=api.Credentials(username='fictitious-new',password='Fictitious-only-2026')
    with pytest.raises(HTTPException) as result:api.login_checked(credentials,request,Response())
    assert result.value.status_code==401 and len(api.FAILURES)==4096 and len(api.IP_FAILURES)==512
    api.IP_FAILURES[request.client.host]=[api.time.time()]*60
    with pytest.raises(HTTPException) as result:api.login_checked(credentials,request,Response())
    assert result.value.status_code==429
