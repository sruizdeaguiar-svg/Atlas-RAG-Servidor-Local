"""Opt-in TLS listener on one private LAN address, controlled only by the Mac app."""
import json, ipaddress, os, datetime, urllib.parse
from pathlib import Path
import psutil
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .store import STATE, SECRET_STATE

def private_ipv4(value):
    try:
        ip=ipaddress.ip_address(value)
        return ip.version==4 and ip.is_private and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast)
    except ValueError: return False

def address():
    interfaces=psutil.net_if_addrs(); active=psutil.net_if_stats()
    for name in sorted(interfaces,key=lambda n:(not n.startswith('en'),n)):
        if not name.startswith('en') or not active.get(name) or not active[name].isup: continue
        for item in interfaces[name]:
            if private_ipv4(item.address): return item.address
    raise ValueError('No active private Ethernet/Wi-Fi address. Connect the Mac to your local network.')

def config():
    try: return json.loads((STATE/'network.json').read_text())
    except (OSError,ValueError): return {'enabled':False}

def paths(): return STATE/'lan-certificate.pem',SECRET_STATE/'lan-key.pem'

def configure(enabled):
    value={'enabled':bool(enabled)}
    if enabled:
        SECRET_STATE.mkdir(parents=True,exist_ok=True); SECRET_STATE.chmod(0o700)
        host=address(); certpath,keypath=paths(); old=config(); recreate=True
        if certpath.exists() and keypath.exists():
            cert=x509.load_pem_x509_certificate(certpath.read_bytes())
            recreate=old.get('tls_version')!=2 or old.get('host')!=host or cert.not_valid_after_utc<datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)
        if recreate:
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048); now=datetime.datetime.now(datetime.timezone.utc)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Atlas RAG Local')])
            cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=True,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),critical=True).sign(key,hashes.SHA256()))
            for path,data in [(keypath,key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())),(certpath,cert.public_bytes(serialization.Encoding.PEM))]:
                fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as f:f.write(data)
                path.chmod(0o600)
        value.update(tls_version=2,host=host,port=8766,fingerprint=cert.fingerprint(hashes.SHA256()).hex())
    p=STATE/'network.json';temp=p.with_suffix('.tmp');temp.write_text(json.dumps(value));temp.chmod(0o600);os.replace(temp,p)
    return public(value)

def public(value=None):
    c=value or config()
    if not c.get('enabled'): return {'enabled':False}
    if not private_ipv4(c.get('host','')): raise ValueError('Invalid LAN configuration')
    url=f"https://{c['host']}:{int(c['port'])}"
    return {'enabled':True,'url':url,'fingerprint':c['fingerprint'],'pairing':'atlasrag://connect?'+urllib.parse.urlencode({'url':url,'pin':c['fingerprint']})}

def allowed_host(host):
    c=config()
    return bool(c.get('enabled') and private_ipv4(c.get('host','')) and host==f"{c['host']}:{c['port']}")
