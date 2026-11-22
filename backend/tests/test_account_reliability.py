"""One-attempt mail failure checks with disposable accounts and a stub provider."""

import time
import urllib.request

import pytest
from app.auth import hash_password
from app.db import connect
from app.main import app
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


class _PasswordCheckReply:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return b''


@pytest.fixture
def timed_out_mail(tmp_path, monkeypatch):
    # Explicitly isolate the process from any local production configuration.
    for name in ('DATABASE_URL', 'DIRECT_URL', 'NAGRIKOS_REQUIRE_POSTGRES',
                 'NAGRIKOS_REQUIRE_DURABLE_STORAGE', 'OBJECT_STORAGE_BACKEND',
                 'OBJECT_STORAGE_BUCKET', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'accounts.db'))
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('MAILJET_API_KEY', 'test-public-key')
    monkeypatch.setenv('MAILJET_SECRET_KEY', 'test-private-key')
    monkeypatch.setenv('MAIL_FROM', 'sender@example.org')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://nagrikos.example.org')
    monkeypatch.setenv('CORS_ORIGINS', 'https://nagrikos.example.org')
    attempts = []

    def urlopen(request, **_kwargs):
        if request.full_url.startswith('https://api.pwnedpasswords.com/range/'):
            return _PasswordCheckReply()
        assert request.full_url == 'https://api.mailjet.com/v3.1/send'
        attempts.append(request)
        raise TimeoutError('outcome unknown')

    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    with TestClient(app, base_url='https://testserver') as client:
        yield client, attempts


def test_signup_ambiguous_mail_timeout_has_one_attempt_and_no_committed_link(timed_out_mail):
    client, attempts = timed_out_mail
    response = client.post('/api/auth/signup', json={
        'name': 'Citizen', 'email': 'citizen@example.org',
        'password': 'a unique passphrase 123',
    })
    assert response.status_code == 503
    assert len(attempts) == 1  # Never automatically retry an ambiguous provider outcome.
    with connect() as db:
        assert db.execute('SELECT 1 FROM users WHERE email_canonical=?',
                          ('citizen@example.org',)).fetchone() is None
        assert db.execute('SELECT 1 FROM account_tokens').fetchone() is None


def test_invitation_ambiguous_mail_timeout_has_one_attempt_and_no_committed_link(timed_out_mail):
    client, attempts = timed_out_mail
    with connect() as db:
        db.execute('INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,created_at,is_demo) '
                   'VALUES (?,?,?,?,?,?,?,?)',
                   ('Admin', 'admin@example.org', 'admin@example.org', int(time.time()),
                    hash_password('admin unique passphrase 123'), 'admin', '2026-01-01T00:00:00Z', 0))
    login = client.post('/api/auth/login', json={
        'email': 'admin@example.org', 'password': 'admin unique passphrase 123',
    })
    assert login.status_code == 200
    response = client.post('/api/auth/staff-invitations',
                           headers={'X-CSRF-Token': client.cookies.get('nagrikos_csrf', '')},
                           json={'name': 'Officer', 'email': 'officer@example.org', 'role': 'officer',
                                 'department': 'Public Works Department',
                                 'current_password': 'admin unique passphrase 123'})
    assert response.status_code == 503
    assert len(attempts) == 1
    with connect() as db:
        assert db.execute('SELECT 1 FROM staff_invitations WHERE email=?',
                          ('officer@example.org',)).fetchone() is None
