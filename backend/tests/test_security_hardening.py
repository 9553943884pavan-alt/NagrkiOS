"""Negative security checks against disposable demo accounts and storage."""

import base64
import hashlib
import hmac
import struct
import time

import pytest
from fastapi.testclient import TestClient

from app.auth import token_hash
from app.db import connect
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('NAGRIKOS_MODE', 'demo')
    for name in ('DATABASE_URL', 'DIRECT_URL', 'OBJECT_STORAGE_BUCKET',
                 'OBJECT_STORAGE_BACKEND', 'AWS_ENDPOINT_URL_S3', 'AWS_ACCESS_KEY_ID',
                 'AWS_SECRET_ACCESS_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'private' / 'db.sqlite3'))
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY_FILE', str(tmp_path / 'totp.key'))
    monkeypatch.setattr('app.main.UPLOAD_DIR', tmp_path / 'private' / 'uploads')
    monkeypatch.setenv('MAILJET_API_KEY', 'test-only-key')
    monkeypatch.setenv('MAILJET_SECRET_KEY', 'test-only-secret')
    monkeypatch.setenv('MAIL_FROM', 'security@example.org')
    monkeypatch.setattr('app.account.send_mail', lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client


def login(client, email):
    response = client.post('/api/auth/login', json={'email': email, 'password': 'demo123'})
    assert response.status_code == 200
    session = response.cookies['nagrikos_session']
    csrf = response.cookies['nagrikos_csrf']
    return {'Cookie': f'nagrikos_session={session}; nagrikos_csrf={csrf}',
            'X-CSRF-Token': csrf}, session


def otp(secret):
    counter = int(time.time()) // 30
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0f
    return f'{(int.from_bytes(digest[offset:offset + 4], "big") & 0x7fffffff) % 1000000:06d}'


def test_authenticated_mutation_rejects_missing_or_cross_session_csrf(client):
    first, _ = login(client, 'citizen@demo.in')
    second, _ = login(client, 'admin@demo.in')
    complaint = {'title': 'Broken street sewer pipe',
                 'description': 'The road has flooded for several days.',
                 'district': 'Prayagraj'}
    with connect() as db:
        before = db.execute('SELECT COUNT(*) FROM complaints').fetchone()[0]

    assert client.post('/api/complaints', headers={'Cookie': first['Cookie']},
                       json=complaint).status_code == 403
    assert client.post('/api/complaints', headers={
        'Cookie': first['Cookie'], 'X-CSRF-Token': second['X-CSRF-Token']},
        json=complaint).status_code == 403
    assert client.post('/api/complaints', headers={**first, 'Origin': 'https://attacker.example'},
                       json=complaint).status_code == 403

    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM complaints').fetchone()[0] == before


def test_role_downgrade_applies_to_existing_session(client):
    officer, _ = login(client, 'officer@demo.in')
    assert client.get('/api/officer/overview', headers=officer).status_code == 200
    with connect() as db:
        db.execute("UPDATE users SET role='citizen',department=NULL WHERE email_canonical=?",
                   ('officer@demo.in',))
    assert client.get('/api/officer/overview', headers=officer).status_code == 403
    assert client.get('/api/dashboard', headers=officer).status_code == 403


def test_idle_expiry_and_mfa_enrollment_revoke_old_sessions(client):
    old, old_session = login(client, 'citizen@demo.in')
    current, current_session = login(client, 'citizen@demo.in')
    assert client.get('/api/auth/me', headers=old).status_code == 200

    setup = client.post('/api/auth/mfa/setup', headers=current,
                        json={'current_password': 'demo123'})
    assert setup.status_code == 200
    enabled = client.post('/api/auth/mfa/enable', headers=current,
                          json={'code': otp(setup.json()['secret'])})
    assert enabled.status_code == 200
    assert client.get('/api/auth/me', headers=old).status_code == 401
    assert client.get('/api/auth/me', headers=current).status_code == 401
    assert client.get('/api/auth/me').status_code == 200

    with connect() as db:
        assert db.execute('SELECT 1 FROM sessions WHERE token_hash IN (?,?)',
                          (token_hash(old_session), token_hash(current_session))).fetchone() is None
        db.execute('UPDATE sessions SET last_seen_at=?', (int(time.time()) - 31 * 60,))
    assert client.get('/api/auth/me').status_code == 401
