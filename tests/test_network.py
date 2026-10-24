import os,sys,ipaddress,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('RAG_STATE_DIR','/private/tmp/atlas-rag-boundary-state')
from server import network
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import pytest
@pytest.mark.parametrize('address',['127.0.0.1','0.0.0.0','8.8.8.8','169.254.1.1','::1','bad'])
def test_lan_rejects_public_or_loopback(address): assert not network.private_ipv4(address)
def test_tls_identity_persists_and_is_scoped(monkeypatch,tmp_path):
    monkeypatch.setattr(network,'STATE',tmp_path)
    monkeypatch.setattr(network,'SECRET_STATE',tmp_path)
    monkeypatch.setattr(network,'address',lambda:'192.168.1.20')
    first=network.configure(True);second=network.configure(True)
    assert first==second and first['url']=='https://192.168.1.20:8766'
    cert,key=network.paths();c=x509.load_pem_x509_certificate(cert.read_bytes())
    assert c.fingerprint(hashes.SHA256()).hex()==first['fingerprint']
    assert ipaddress.ip_address('192.168.1.20') in c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
    assert x509.oid.ExtendedKeyUsageOID.SERVER_AUTH in c.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert key.stat().st_mode&0o777==0o600
    assert network.allowed_host('192.168.1.20:8766')
    assert not network.allowed_host('evil.test:8766')
    network.configure(False)
    assert not network.allowed_host('192.168.1.20:8766')
