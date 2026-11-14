"""Brevo HTTPS transport and account flows with a stubbed provider."""
import io
import json
import re
import time
import urllib.error

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.account import mail_ready, validate_config
from app.db import connect
from app.main import app


class Reply:
    def __init__(self, body, status=201):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.body


@pytest.fixture
def public_mail(tmp_path, monkeypatch):
    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'brevo.db'))
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('BREVO_API_KEY', 'xkeysib-test-only')
    monkeypatch.setenv('MAIL_FROM', 'security@example.org')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://nagrikos.example.org')
    monkeypatch.setenv('CORS_ORIGINS', 'https://nagrikos.example.org')
    sent = []
    failure = {'value': None}

    def urlopen(request, **kwargs):
        if request.full_url.startswith('https://api.pwnedpasswords.com/range/'):
            return Reply(b'')
        assert request.full_url == 'https://api.brevo.com/v3/smtp/email'
        assert request.get_method() == 'POST'
        assert request.get_header('Api-key') == 'xkeysib-test-only'
        assert request.get_header('Content-type') == 'application/json'
        assert kwargs['timeout'] == 10 and kwargs['context'] is not None
        payload = json.loads(request.data)
        assert payload['sender'] == {'email': 'security@example.org'}
        assert payload['to'] and len(payload['to']) == 1
        if failure['value'] is not None:
            if isinstance(failure['value'], Exception):
                raise failure['value']
            if isinstance(failure['value'], Reply):
                return failure['value']
            return Reply(failure['value'])
        sent.append(payload)
        return Reply(b'{"messageId":"<test-123@relay.example.org>"}')

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    with TestClient(app, base_url='https://testserver') as client:
        yield client, sent, failure


def csrf(client):
    return {'X-CSRF-Token': client.cookies.get('nagrikos_csrf', '')}


def token(message, kind):
    return re.search(r'#' + kind + r'=([^\s]+)', message['textContent']).group(1)


def test_brevo_signup_verification_login_and_password_reset(public_mail):
    client, sent, _ = public_mail
    config = client.get('/api/auth/config').json()
    assert config['registration_available'] and config['recovery_available']
    assert not config['demo_enabled'] and 'demo_password' not in config
    signup = client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'CITIZEN@example.org',
                                                    'password': 'first unique passphrase 123'})
    assert signup.status_code == 202 and 'verify=' not in signup.text
    assert len(sent) == 1 and sent[0]['to'] == [{'email': 'citizen@example.org'}]
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                                                'password': 'first unique passphrase 123'}).status_code == 401
    verify = token(sent[0], 'verify')
    assert client.post('/api/auth/verify-email', json={'token': verify,
                         'password': 'first unique passphrase 123'}).status_code == 200
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                                                'password': 'first unique passphrase 123'}).status_code == 200
    forgot = client.post('/api/auth/forgot-password', headers=csrf(client),
                         json={'email': 'citizen@example.org'})
    unknown = client.post('/api/auth/forgot-password', headers=csrf(client),
                          json={'email': 'unknown@example.org'})
    assert forgot.status_code == unknown.status_code == 202 and forgot.json() == unknown.json()
    assert len(sent) == 2 and 'reset=' not in forgot.text
    reset = token(sent[1], 'reset')
    changed = client.post('/api/auth/reset-password', headers=csrf(client),
                          json={'token': reset, 'new_password': 'second unique passphrase 456'})
    assert changed.status_code == 200 and len(sent) == 3
    assert reset not in sent[2]['textContent'] and 'password was changed' in sent[2]['subject']
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/reset-password', json={'token': reset,
                       'new_password': 'third unique passphrase 789'}).status_code == 400
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                       'password': 'first unique passphrase 123'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                       'password': 'second unique passphrase 456'}).status_code == 200


def test_brevo_public_config_requires_key(public_mail, monkeypatch):
    assert mail_ready()
    validate_config()
    monkeypatch.setenv('BREVO_API_KEY', 'bad\nheader')
    with pytest.raises(RuntimeError, match='BREVO_API_KEY'):
        validate_config()
    monkeypatch.delenv('BREVO_API_KEY')
    assert not mail_ready()
    with pytest.raises(RuntimeError, match='BREVO_API_KEY'):
        validate_config()


@pytest.mark.parametrize('failure', [
    urllib.error.HTTPError('https://api.brevo.com/v3/smtp/email', 401, 'invalid credentials', None, io.BytesIO(b'{"message":"no"}')),
    urllib.error.HTTPError('https://api.brevo.com/v3/smtp/email', 429, 'rate limited', None, io.BytesIO(b'{"message":"no"}')),
    urllib.error.URLError('network unavailable'),
    TimeoutError('timed out'),
    Reply(b'{"messageId":"<test-123@relay.example.org>"}', status=200),
    b'{}',
    b'{"messageId":""}',
    b'{"messageId":"invalid"}',
    b'not-json',
])
def test_brevo_failures_do_not_commit_signup_or_claim_delivery(public_mail, failure):
    client, sent, state = public_mail
    state['value'] = failure
    result = client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'failed@example.org',
                                                   'password': 'first unique passphrase 123'})
    assert result.status_code == 503
    assert result.json()['detail'] == 'Email delivery is unavailable. Try again later.'
    assert 'xkeysib-test-only' not in result.text and len(sent) == 0
    with connect() as db:
        assert db.execute('SELECT 1 FROM users WHERE email_canonical=?', ('failed@example.org',)).fetchone() is None
        assert db.execute('SELECT 1 FROM account_tokens').fetchone() is None


def test_brevo_failed_recovery_and_reset_notification_roll_back(public_mail):
    client, sent, state = public_mail
    client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'citizen@example.org',
                                          'password': 'first unique passphrase 123'})
    client.post('/api/auth/verify-email', json={'token': token(sent[0], 'verify'),
                                                'password': 'first unique passphrase 123'})
    state['value'] = urllib.error.URLError('network unavailable')
    failed = client.post('/api/auth/forgot-password', json={'email': 'citizen@example.org'})
    assert failed.status_code == 503 and 'sent' not in failed.text.lower()
    with connect() as db:
        assert db.execute("SELECT 1 FROM account_tokens WHERE purpose='reset'").fetchone() is None
    state['value'] = None
    assert client.post('/api/auth/forgot-password', json={'email': 'citizen@example.org'}).status_code == 202
    reset = token(sent[1], 'reset')
    state['value'] = urllib.error.URLError('network unavailable')
    failed_reset = client.post('/api/auth/reset-password', json={'token': reset,
                              'new_password': 'second unique passphrase 456'})
    assert failed_reset.status_code == 503
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                       'password': 'first unique passphrase 123'}).status_code == 200


def test_brevo_staff_invitation_and_failure(public_mail):
    client, sent, state = public_mail
    with connect() as db:
        db.execute('INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,created_at,is_demo) '
                   'VALUES (?,?,?,?,?,?,?,?)', ('Admin', 'admin@example.org', 'admin@example.org',
                   int(time.time()), hash_password('admin unique passphrase 123'), 'admin',
                   '2026-01-01T00:00:00Z', 0))
    assert client.post('/api/auth/login', json={'email': 'admin@example.org',
                       'password': 'admin unique passphrase 123'}).status_code == 200
    body = {'name': 'Officer', 'email': 'officer@example.org', 'role': 'officer',
            'department': 'Public Works Department', 'current_password': 'admin unique passphrase 123'}
    invited = client.post('/api/auth/staff-invitations', headers=csrf(client), json=body)
    assert invited.status_code == 202 and 'invite=' not in invited.text
    assert len(sent) == 1 and sent[0]['to'] == [{'email': 'officer@example.org'}]
    invite = token(sent[0], 'invite')
    assert client.post('/api/auth/accept-invitation', headers=csrf(client),
                       json={'token': invite, 'password': 'officer unique passphrase 123'}).status_code == 200
    state['value'] = urllib.error.URLError('network unavailable')
    failed = client.post('/api/auth/staff-invitations', headers=csrf(client),
                         json={**body, 'email': 'second@example.org'})
    assert failed.status_code == 503
    with connect() as db:
        assert db.execute('SELECT 1 FROM staff_invitations WHERE email=?', ('second@example.org',)).fetchone() is None


def test_demo_has_no_runtime_mailbox_or_fake_delivery(tmp_path, monkeypatch):
    monkeypatch.setenv('NAGRIKOS_MODE', 'demo')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'demo.db'))
    monkeypatch.delenv('BREVO_API_KEY', raising=False)
    monkeypatch.delenv('MAIL_FROM', raising=False)
    with TestClient(app) as client:
        config = client.get('/api/auth/config').json()
        assert not config['registration_available'] and not config['recovery_available']
        assert client.get('/api/auth/dev-mailbox').status_code == 404
        assert client.post('/api/auth/signup', json={'name': 'Citizen',
            'email': 'citizen@example.org', 'password': 'a unique passphrase 123'}).status_code == 503
