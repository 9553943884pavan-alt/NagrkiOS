"""End-to-end account lifecycle against isolated SQLite and development mail sink."""
import base64
import hashlib
import hmac
import re
import struct
import time

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path/'accounts.db'))
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY_FILE', str(tmp_path/'totp.key'))
    with TestClient(app) as c:
        yield c


def csrf(c):
    return {'X-CSRF-Token':c.cookies.get('nagrikos_csrf','')}


def mailed_token():
    with connect() as db:
        body=db.execute('SELECT body FROM mail_outbox ORDER BY id DESC LIMIT 1').fetchone()['body']
    return re.search(r'[#?&](?:verify|reset|invite)=([^\s]+)',body).group(1)


def otp(secret, now=None):
    step=int(now or time.time())//30
    raw=base64.b32decode(secret+'='*((-len(secret))%8))
    digest=hmac.new(raw,struct.pack('>Q',step),hashlib.sha1).digest()
    offset=digest[-1]&15
    return f'{(int.from_bytes(digest[offset:offset+4],"big")&0x7fffffff)%1000000:06d}'


def test_citizen_signup_verification_recovery_and_enumeration(client):
    pwd='a long unique passphrase 90210'
    payload={'name':'New Citizen','email':' NEW@Example.com ','password':pwd}
    assert client.post('/api/auth/signup',json={**payload,'role':'admin','department':'General Administration'}).status_code==422
    signup=client.post('/api/auth/signup',json=payload)
    assert signup.status_code==202
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':pwd}).status_code==401
    with connect() as db:
        row=db.execute('SELECT role,department,email_canonical,email_verified_at,is_demo FROM users WHERE email_canonical=?',('new@example.com',)).fetchone()
        assert (row['role'],row['department'],row['email_canonical'],row['email_verified_at'])==('citizen',None,'new@example.com',None)
        assert row['is_demo']==1
        assert db.execute('SELECT COUNT(*) FROM users WHERE email_canonical=?',('new@example.com',)).fetchone()[0]==1
    verify=mailed_token()
    assert client.post('/api/auth/verify-email',json={'token':verify}).status_code==200
    assert client.post('/api/auth/verify-email',json={'token':verify}).status_code==400
    duplicate=client.post('/api/auth/signup',json=payload)
    assert duplicate.status_code==202 and duplicate.json()==signup.json()
    signed=client.post('/api/auth/login',json={'email':'new@example.com','password':pwd})
    assert signed.status_code==200 and signed.json()['user']['role']=='citizen'
    assert client.patch('/api/auth/me',headers=csrf(client),json={'role':'admin'}).status_code==405
    known=client.post('/api/auth/forgot-password',headers=csrf(client),json={'email':'new@example.com'})
    unknown=client.post('/api/auth/forgot-password',headers=csrf(client),json={'email':'unknown@example.com'})
    assert known.status_code==unknown.status_code==202 and known.json()==unknown.json()
    reset=mailed_token()
    with connect() as db:
        db.execute('UPDATE account_tokens SET expires_at=? WHERE token_hash=?',(int(time.time())-1,hashlib.sha256(reset.encode()).hexdigest()))
    assert client.post('/api/auth/reset-password',headers=csrf(client),json={'token':reset,'new_password':'another long unique phrase 123'}).status_code==400
    client.post('/api/auth/forgot-password',headers=csrf(client),json={'email':'new@example.com'})
    reset=mailed_token()
    changed=client.post('/api/auth/reset-password',headers=csrf(client),json={'token':reset,'new_password':'another long unique phrase 123'})
    assert changed.status_code==200,changed.text
    with connect() as db:
        notice=db.execute('SELECT recipient,subject,body FROM mail_outbox ORDER BY id DESC LIMIT 1').fetchone()
        assert notice['recipient']=='new@example.com' and 'password was changed' in notice['subject']
        assert reset not in notice['body']
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/reset-password',json={'token':reset,'new_password':'third long unique phrase 456'}).status_code==400
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':pwd}).status_code==401
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':'another long unique phrase 123'}).status_code==200


def test_mfa_challenge_recovery_and_removal(client):
    signed=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    assert signed.status_code==200
    setup=client.post('/api/auth/mfa/setup',headers=csrf(client),json={'current_password':'demo123'})
    assert setup.status_code==200 and setup.json()['qr_svg'].startswith('data:image/svg+xml;base64,')
    secret=setup.json()['secret']
    assert client.post('/api/auth/mfa/enable',headers=csrf(client),json={'code':'000000'}).status_code==422
    enabled=client.post('/api/auth/mfa/enable',headers=csrf(client),json={'code':otp(secret)})
    assert enabled.status_code==200
    codes=enabled.json()['recovery_codes']
    with connect() as db:
        assert all(c not in str(tuple(r)) for c in codes for r in db.execute('SELECT code_hash FROM recovery_codes'))
    first=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    assert first.status_code==200 and first.json()['mfa_required'] and 'nagrikos_session' not in first.cookies
    challenge=first.json()['challenge']
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':'000000'}).status_code==401
    finished=client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':codes[0]})
    assert finished.status_code==200
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':codes[0]}).status_code==401
    again=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'}).json()
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':again['challenge'],'code':codes[0]}).status_code==401
    with connect() as db:
        db.execute('UPDATE auth_challenges SET expires_at=0 WHERE token_hash=?',(hashlib.sha256(again['challenge'].encode()).hexdigest(),))
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':again['challenge'],'code':codes[1]}).status_code==401
    assert client.post('/api/auth/mfa/disable',headers=csrf(client),json={'current_password':'bad','code':codes[1]}).status_code==403
    assert client.post('/api/auth/mfa/disable',headers=csrf(client),json={'current_password':'demo123','code':codes[1]}).status_code==200
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'}).json()['user']['role']=='citizen'


def test_public_config_fails_closed_and_demo_identity_is_blocked(client, monkeypatch):
    monkeypatch.setenv('NAGRIKOS_MODE','public')
    assert client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'}).status_code==401
    assert client.get('/api/auth/me').status_code==401
    from app.account import validate_config
    with pytest.raises(RuntimeError,match='COOKIE_SECURE'):
        validate_config()


def test_staff_invitation_is_admin_only_and_department_scoped(client):
    citizen=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    body={'name':'Invited Officer','email':'invited@example.com','role':'officer',
          'department':'Public Works Department','current_password':'demo123'}
    assert client.post('/api/auth/staff-invitations',headers=csrf(client),json=body).status_code==403
    admin=client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'})
    assert admin.status_code==200
    assert client.post('/api/auth/staff-invitations',headers=csrf(client),json={**body,'department':'Invented desk'}).status_code==422
    invited=client.post('/api/auth/staff-invitations',headers=csrf(client),json=body)
    assert invited.status_code==202,invited.text
    token=mailed_token()
    accepted=client.post('/api/auth/accept-invitation',headers=csrf(client),json={'token':token,'password':'officer unique phrase 123'})
    assert accepted.status_code==200,accepted.text
    assert client.post('/api/auth/accept-invitation',headers=csrf(client),json={'token':token,'password':'officer unique phrase 123'}).status_code==400
    officer=client.post('/api/auth/login',json={'email':'invited@example.com','password':'officer unique phrase 123'})
    assert officer.json()['user']['role']=='officer'
    assert officer.json()['user']['department']=='Public Works Department'


def test_public_mode_has_no_seed_and_breach_check_fails_closed(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from app.account import password_policy
    monkeypatch.setenv('NAGRIKOS_MODE','public')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'public.db'))
    monkeypatch.setenv('COOKIE_SECURE','true')
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('SMTP_HOST','smtp.example.com')
    monkeypatch.setenv('MAIL_FROM','security@example.com')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://nagrikos.example.com')
    monkeypatch.setenv('CORS_ORIGINS','https://nagrikos.example.com')
    with TestClient(app) as public:
        assert public.get('/api/auth/config').json()['demo_enabled'] is False
        assert 'demo_password' not in public.get('/api/auth/config').json()
        with connect() as db:
            assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
            from app.auth import hash_password
            db.execute('INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,created_at,is_demo) '
                       'VALUES (?,?,?,?,?,?,?,0)',
                       ('Operator','admin@demo.in','admin@demo.in',int(time.time()),
                        hash_password('unique operator phrase 123'),'admin','2026-11-14T00:00:00Z'))
    from app.db import initialize
    initialize()
    with connect() as db:
        assert db.execute('SELECT is_demo FROM users WHERE email_canonical=?',('admin@demo.in',)).fetchone()['is_demo']==0
    digest=hashlib.sha1(b'a long unique phrase 123').hexdigest().upper()
    class FakeRange:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,_):return (digest[5:]+':2\n').encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *_a,**_kw:FakeRange())
    with pytest.raises(Exception,match='data breach'):
        password_policy('a long unique phrase 123')
    def unavailable(*_a,**_kw):raise OSError('offline')
    monkeypatch.setattr('urllib.request.urlopen',unavailable)
    with pytest.raises(Exception,match='temporarily unavailable'):
        password_policy('a long unique phrase 123')


def test_mfa_setup_attempts_are_bounded(client):
    signed=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    assert signed.status_code==200
    for _ in range(5):
        assert client.post('/api/auth/mfa/setup',headers=csrf(client),json={'current_password':'wrong'}).status_code==403
    assert client.post('/api/auth/mfa/setup',headers=csrf(client),json={'current_password':'demo123'}).status_code==429


def test_refresh_restores_cookie_session_and_logout_revokes_it(client):
    signed=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    assert signed.status_code==200
    csrf_token=signed.cookies['nagrikos_csrf']
    cookies=f'nagrikos_session={signed.cookies["nagrikos_session"]}; nagrikos_csrf={csrf_token}'
    with TestClient(app) as refreshed:
        assert refreshed.get('/api/auth/me',headers={'Cookie':cookies}).json()['role']=='citizen'
        assert refreshed.post('/api/auth/logout',headers={'Cookie':cookies,'X-CSRF-Token':csrf_token},json={}).status_code==200
    assert client.get('/api/auth/me',headers={'Cookie':cookies}).status_code==401


def test_unverified_signup_stays_unverified_on_restart(client):
    from app.db import initialize
    assert client.post('/api/auth/signup',json={'name':'Pending Person','email':'pending@example.com',
                                               'password':'unique pending phrase 123'}).status_code==202
    with connect() as db:
        db.execute("DELETE FROM account_tokens WHERE purpose='verify'")
    initialize()
    with connect() as db:
        row=db.execute('SELECT email_verified_at FROM users WHERE email_canonical=?',('pending@example.com',)).fetchone()
    assert row['email_verified_at'] is None
    assert client.post('/api/auth/login',json={'email':'pending@example.com','password':'unique pending phrase 123'}).status_code==401


def test_missing_mode_fails_startup(tmp_path, monkeypatch):
    monkeypatch.delenv('NAGRIKOS_MODE',raising=False)
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'never-created.db'))
    with pytest.raises(RuntimeError,match='NAGRIKOS_MODE'):
        with TestClient(app):
            pass
    assert not (tmp_path/'never-created.db').exists()


def test_expired_and_replayed_totp_and_challenge_attempt_limit(client):
    assert client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'}).status_code==200
    setup=client.post('/api/auth/mfa/setup',headers=csrf(client),json={'current_password':'demo123'}).json()
    now=int(time.time())
    current=otp(setup['secret'],now)
    assert client.post('/api/auth/mfa/enable',headers=csrf(client),json={'code':current}).status_code==200
    challenge=client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'}).json()['challenge']
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':current}).status_code==401
    stale=otp(setup['secret'],now-120)
    assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':stale}).status_code==401
    for _ in range(3):
        assert client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':'000000'}).status_code==401
    expired=client.post('/api/auth/mfa/challenge',headers=csrf(client),json={'challenge':challenge,'code':'000000'})
    assert expired.status_code==401 and 'expired' in expired.json()['detail'].lower()
    assert client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'}).status_code==429


def test_public_smtp_transport_and_no_link_in_response(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv('NAGRIKOS_MODE','public')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'public-mail.db'))
    monkeypatch.setenv('COOKIE_SECURE','true')
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('SMTP_HOST','smtp.example.com')
    monkeypatch.setenv('MAIL_FROM','security@example.com')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://nagrikos.example.com')
    monkeypatch.setenv('CORS_ORIGINS','https://nagrikos.example.com')
    messages=[]
    class FakeSMTP:
        def __init__(self,host,port,timeout):
            assert (host,port,timeout)==('smtp.example.com',587,10)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,context):assert context is not None
        def send_message(self,message):messages.append(message)
    class EmptyRange:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,_):return b''
    monkeypatch.setattr('smtplib.SMTP',FakeSMTP)
    monkeypatch.setattr('urllib.request.urlopen',lambda *_a,**_kw:EmptyRange())
    with TestClient(app) as public:
        response=public.post('/api/auth/signup',json={'name':'Public Citizen','email':'PUBLIC@example.com',
                                                      'password':'unique public phrase 123'})
        assert response.status_code==202
        assert 'verify=' not in response.text and 'PUBLIC@example.com' not in response.text
        assert len(messages)==1 and messages[0]['To']=='public@example.com'
        with connect() as db:
            assert db.execute('SELECT is_demo FROM users WHERE email_canonical=?',('public@example.com',)).fetchone()['is_demo']==0
        token=re.search(r'#verify=([^\s]+)',messages[0].get_content()).group(1)
        assert public.post('/api/auth/verify-email',json={'token':token}).status_code==200
        signed=public.post('/api/auth/login',json={'email':'public@example.com','password':'unique public phrase 123'})
        assert signed.status_code==200
        assert 'secure' in signed.headers['set-cookie'].lower()
        assert 'httponly' in signed.headers['set-cookie'].lower()
        class FailingSMTP(FakeSMTP):
            def send_message(self,_message):raise OSError('mail service down')
        monkeypatch.setattr('smtplib.SMTP',FailingSMTP)
        failed=public.post('/api/auth/signup',json={'name':'Second Citizen','email':'second@example.com',
                                                    'password':'another unique phrase 123'})
        assert failed.status_code==503 and 'unavailable' in failed.json()['detail'].lower()
        with connect() as db:
            assert db.execute('SELECT 1 FROM users WHERE email_canonical=?',('second@example.com',)).fetchone() is None
