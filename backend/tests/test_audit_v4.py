"""Additional negative-path and stronger-authentication checks."""
import base64
import hashlib
import hmac
import io
import struct
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.db import connect
from app.auth import token_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'data'/'nagrikos.db'))
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY_FILE',str(tmp_path/'separate_key'/'totp.key'))
    monkeypatch.setattr('app.main.UPLOAD_DIR',tmp_path/'uploads')
    with TestClient(app) as c: yield c


def login(c,email='admin@demo.in',password='demo123',mfa_code=''):
    r=c.post('/api/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.text
    if mfa_code:
        assert r.json()['mfa_required'] is True
        r=c.post('/api/auth/mfa/challenge',headers={'X-CSRF-Token':c.cookies.get('nagrikos_csrf','')},json={'challenge':r.json()['challenge'],'code':mfa_code})
        assert r.status_code==200,r.text
    csrf=r.cookies['nagrikos_csrf']
    return {'Cookie':f'nagrikos_session={r.cookies["nagrikos_session"]}; nagrikos_csrf={csrf}', 'X-CSRF-Token':csrf}


def totp(secret,at):
    secret=base64.b32decode(secret+'='*((-len(secret))%8))
    msg=struct.pack('>Q',at//30)
    digest=hmac.new(secret,msg,hashlib.sha1).digest()
    off=digest[-1]&15
    return f'{(int.from_bytes(digest[off:off+4],"big") & 0x7fffffff)%1000000:06d}'


def test_argon2_and_legacy_scrypt_upgrade(client):
    import secrets
    from app.auth import verify_password
    from hashlib import scrypt
    with connect() as db:
        first=db.execute('SELECT password_hash FROM users WHERE id=1').fetchone()['password_hash']
        assert first.startswith('$argon2id$')
        salt=secrets.token_bytes(16)
        legacy='scrypt$16384$8$1$'+salt.hex()+'$'+scrypt(b'demo123',salt=salt,n=16384,r=8,p=1,dklen=32).hex()
        db.execute('UPDATE users SET password_hash=? WHERE id=1',(legacy,))
    login(client)
    with connect() as db:
        new=db.execute('SELECT password_hash FROM users WHERE id=1').fetchone()['password_hash']
    assert new.startswith('$argon2id$') and verify_password('demo123',new,1)[0]


def test_idle_timeout_and_password_change(client):
    admin=login(client)
    token=admin['Cookie'].split(';')[0].split('=',1)[1]
    with connect() as db:
        db.execute('UPDATE sessions SET last_seen_at=? WHERE token_hash=?',(int(time.time())-1900,token_hash(token)))
    assert client.get('/api/dashboard',headers=admin).status_code==401
    assert client.post('/api/admin/reset-demo',headers=admin,json={}).status_code==403
    admin=login(client)
    wrong=client.post('/api/auth/password',headers=admin,json={'current_password':'bad','new_password':'a-very-long-new-password'})
    assert wrong.status_code==403
    changed=client.post('/api/auth/password',headers=admin,json={'current_password':'demo123','new_password':'a-very-long-new-password'})
    assert changed.status_code==200
    assert client.get('/api/dashboard',headers=admin).status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'}).status_code==401
    login(client,password='a-very-long-new-password')


def test_mfa_enrollment_replay_and_disable(client,monkeypatch):
    admin=login(client)
    setup=client.post('/api/auth/mfa/setup',headers=admin,json={'current_password':'demo123'})
    assert setup.status_code==200,setup.text
    secret=setup.json()['secret']
    assert 'otpauth://totp/' in setup.json()['otpauth_uri']
    with connect() as db:
        row=db.execute('SELECT mfa_secret,mfa_pending FROM users WHERE id=1').fetchone()
    assert row['mfa_secret'] is None and secret not in row['mfa_pending']
    assert client.post('/api/auth/mfa/enable',headers=admin,json={'code':'000000'}).status_code==422
    now=int(time.time()); code=totp(secret,now)
    enabled=client.post('/api/auth/mfa/enable',headers=admin,json={'code':code})
    assert enabled.status_code==200
    assert len(enabled.json()['recovery_codes'])==10
    first=client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'})
    assert first.json()['mfa_required'] is True and 'nagrikos_session' not in first.cookies
    assert client.post('/api/auth/mfa/challenge',headers={'X-CSRF-Token':client.cookies.get('nagrikos_csrf','')},json={'challenge':first.json()['challenge'],'code':code}).status_code==401
    monkeypatch.setattr('app.main.time.time',lambda: now+35)
    code2=totp(secret,now+35)
    second=login(client,mfa_code=code2)
    replay=client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'}).json()
    assert client.post('/api/auth/mfa/challenge',headers={'X-CSRF-Token':client.cookies.get('nagrikos_csrf','')},json={'challenge':replay['challenge'],'code':code2}).status_code==401
    monkeypatch.setattr('app.main.time.time',lambda: now+66)
    code3=totp(secret,now+66)
    assert client.post('/api/auth/mfa/disable',headers=second,json={'current_password':'bad','code':code3}).status_code==403
    assert client.post('/api/auth/mfa/disable',headers=second,json={'current_password':'demo123','code':code3}).status_code==200
    assert client.get('/api/auth/me',headers=second).status_code==401
    login(client)


def test_citizen_overview_counts_and_admin_access(client):
    admin=login(client)
    citizen=login(client,'citizen@demo.in')
    assert client.get('/api/citizen/overview',headers=admin).status_code==403
    summary=client.get('/api/citizen/overview',headers=citizen).json()
    assert summary['total'] == summary['resolved'] + summary['active']
    assert len(summary['recent'])<=5
    assert all(c['citizen_id']==4 for c in summary['recent'])
    with connect() as db:
        counts=db.execute('SELECT COUNT(*) AS n FROM complaints WHERE citizen_id=4').fetchone()['n']
    assert counts==summary['total']


def test_photo_validation_removes_exif_and_visibility(client):
    citizen=login(client,'citizen@demo.in')
    image=Image.new('RGB',(10,10),'red'); exif=Image.Exif();exif[271]='Private camera make'
    out=io.BytesIO();image.save(out,format='JPEG',exif=exif)
    up=client.post('/api/attachments',headers=citizen,files={'file':('street.jpg',out.getvalue(),'image/jpeg')})
    assert up.status_code==200,up.text
    downloaded=client.get(up.json()['url'],headers=citizen)
    assert downloaded.status_code==200
    with Image.open(io.BytesIO(downloaded.content)) as clean:
        assert 271 not in clean.getexif()
    assert client.post('/api/attachments',headers=citizen,files={'file':('fake.jpg',b'\xff\xd8\xffinvalid','image/jpeg')}).status_code==400
    assert client.get('/api/users/officers',headers=citizen).status_code==403
    admin=login(client)
    officials=client.get('/api/users/officers',headers=admin).json()
    assert officials and not any('email' in o for o in officials)


def test_read_authentication_and_no_private_data_leak(client):
    assert client.get('/api/complaints').status_code==401
    assert client.get('/api/citizen/overview').status_code==401
    assert client.get('/api/auth/security').status_code==401
    assert client.get('/api/export/complaints.csv').status_code==401
    assert client.get('/api/attachments/0123456789abcdef01234567.jpg').status_code==401
    assert client.get('/api/health').json()=={'status':'ok'}
    res=client.get('/')
    assert 'content-security-policy' in res.headers


def test_mock_keyword_boundaries_and_persistence(client):
    from app.ai import analyze
    assert analyze('We have firewood next to a bridge')['priority'] != 'critical'
    assert analyze('The electric tape is peeling')['category'] == 'Electricity'
    assert analyze('The exposed live wire fell near children')['priority'] == 'critical'
    assert analyze('बिजली का तार टूटकर सड़क पर गिर गया है')['priority'] == 'critical'
    citizen=login(client,'citizen@demo.in')
    payload={'title':'Urgent exposed live wire near school',
             'description':'The exposed live wire is dangling over our road near children.',
             'district':'Prayagraj'}
    preview=client.post('/api/ai/analyze',headers=citizen,json=payload)
    assert preview.status_code==200
    created=client.post('/api/complaints',headers=citizen,json=payload)
    assert created.status_code==201
    for key in ['category','department','priority','estimated_hours','language']:
        assert created.json()[key]==preview.json()[key]
    assert created.json()['priority']=='critical'


def test_role_aware_routes_and_notes(client):
    admin=login(client)
    citizen=login(client,'citizen@demo.in')
    officer=login(client,'officer@demo.in')
    assert client.get('/api/dashboard',headers=citizen).status_code==403
    assert client.get('/api/officer/overview',headers=admin).status_code==403
    assert client.get('/api/export/complaints.csv',headers=citizen).status_code==403
    created=client.post('/api/complaints',headers=citizen,json={
      'title':'Broken bridge near school','description':'This road bridge requires repair after damage.',
      'district':'Lucknow'}).json()
    ticket=created['id']
    assert created['department']=='Public Works Department'
    assert client.post(f'/api/complaints/{ticket}/notes',headers=citizen,json={'body':'hello'}).status_code==403
    assert client.post(f'/api/complaints/{ticket}/notes',headers=officer,json={'body':'   '}).status_code==422
    assert client.post(f'/api/complaints/{ticket}/notes',headers=officer,json={'body':'Private office investigation','is_public':False}).status_code==201
    assert client.post(f'/api/complaints/{ticket}/notes',headers=officer,json={'body':'We have received your case','is_public':True}).status_code==201
    citizen_notes=client.get(f'/api/complaints/{ticket}',headers=citizen).json()['notes']
    assert len(citizen_notes)==1 and citizen_notes[0]['is_public']==1
    officer_notes=client.get(f'/api/complaints/{ticket}',headers=officer).json()['notes']
    assert len(officer_notes)==2
