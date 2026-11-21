"""Mailjet HTTPS transport and account flows with a stubbed provider."""
import base64
import io
import json
import re
import time
import urllib.error

import pytest
from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, Request
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.account import EmailBody, MailDeliveryUnavailable, forgot_password, mail_ready, send_mail, validate_config
from app.db import connect
from app.main import app


class Reply:
    def __init__(self, body, status=200):
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
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'mailjet.db'))
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    monkeypatch.setenv('NAGRIKOS_TOTP_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('MAILJET_API_KEY', 'mailjet-public-test')
    monkeypatch.setenv('MAILJET_SECRET_KEY', 'mailjet-private-test')
    monkeypatch.setenv('MAIL_FROM', 'security@example.org')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://nagrikos.example.org')
    monkeypatch.setenv('CORS_ORIGINS', 'https://nagrikos.example.org')
    sent = []
    failure = {'value': None, 'attempts': 0}

    def urlopen(request, **kwargs):
        if request.full_url.startswith('https://api.pwnedpasswords.com/range/'):
            return Reply(b'')
        assert request.full_url == 'https://api.mailjet.com/v3.1/send'
        failure['attempts'] += 1
        assert request.get_method() == 'POST'
        assert request.get_header('Authorization') == ('Basic ' + base64.b64encode(
            b'mailjet-public-test:mailjet-private-test').decode())
        assert request.get_header('Content-type') == 'application/json'
        assert kwargs['timeout'] == 10 and kwargs['context'] is not None
        payload = json.loads(request.data)
        assert len(payload['Messages']) == 1
        message = payload['Messages'][0]
        assert message['From'] == {'Email': 'security@example.org'}
        assert message['To'] and len(message['To']) == 1
        if failure['value'] is not None:
            if isinstance(failure['value'], Exception):
                raise failure['value']
            if isinstance(failure['value'], Reply):
                return failure['value']
            return Reply(failure['value'])
        sent.append(message)
        return Reply(json.dumps({'Messages': [{'Status': 'success', 'To': [
            {'Email': message['To'][0]['Email'], 'MessageID': 123}]}]}).encode())

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    with TestClient(app, base_url='https://testserver') as client:
        yield client, sent, failure


def csrf(client):
    return {'X-CSRF-Token': client.cookies.get('nagrikos_csrf', '')}


def token(message, kind):
    return re.search(r'#' + kind + r'=([^\s]+)', message['TextPart']).group(1)


def test_mailjet_signup_verification_login_and_password_reset(public_mail):
    client, sent, _ = public_mail
    config = client.get('/api/auth/config').json()
    assert config['registration_available'] and config['recovery_available']
    assert not config['demo_enabled'] and 'demo_password' not in config
    signup = client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'CITIZEN@example.org',
                                                    'password': 'first unique passphrase 123'})
    assert signup.status_code == 202 and 'verify=' not in signup.text
    assert len(sent) == 1 and sent[0]['To'] == [{'Email': 'citizen@example.org'}]
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
    assert reset not in sent[2]['TextPart'] and 'password was changed' in sent[2]['Subject']
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/reset-password', json={'token': reset,
                       'new_password': 'third unique passphrase 789'}).status_code == 400
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                       'password': 'first unique passphrase 123'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'citizen@example.org',
                       'password': 'second unique passphrase 456'}).status_code == 200


def test_mailjet_public_config_requires_both_keys(public_mail, monkeypatch):
    assert mail_ready()
    validate_config()
    monkeypatch.setenv('MAILJET_API_KEY', 'bad\nheader')
    with pytest.raises(RuntimeError, match='MAILJET_API_KEY'):
        validate_config()
    monkeypatch.delenv('MAILJET_API_KEY')
    assert not mail_ready()
    with pytest.raises(RuntimeError, match='MAILJET_API_KEY'):
        validate_config()
    monkeypatch.setenv('MAILJET_API_KEY', 'mailjet-public-test')
    monkeypatch.delenv('MAILJET_SECRET_KEY')
    assert not mail_ready()
    with pytest.raises(RuntimeError, match='MAILJET_SECRET_KEY'):
        validate_config()


@pytest.mark.parametrize('failure', [
    urllib.error.HTTPError('https://api.mailjet.com/v3.1/send', 401, 'invalid credentials', None, io.BytesIO(b'{"message":"no"}')),
    urllib.error.HTTPError('https://api.mailjet.com/v3.1/send', 403, 'sender rejected', None, io.BytesIO(b'{"message":"no"}')),
    urllib.error.HTTPError('https://api.mailjet.com/v3.1/send', 429, 'rate limited', None, io.BytesIO(b'{"message":"no"}')),
    urllib.error.URLError('network unavailable'),
    TimeoutError('timed out'),
    Reply(b'{"Messages":[{"Status":"success","To":[{"Email":"failed@example.org","MessageID":123}]}]}', status=202),
    b'{}',
    b'{"Messages":[]}',
    b'{"Messages":[{"Status":"error","To":[{"Email":"failed@example.org","MessageID":123}]}]}',
    b'{"Messages":[{"Status":"success","To":[{"Email":"failed@example.org"}]}]}',
    b'{"Messages":[{"Status":"success","To":[{"Email":"wrong@example.org","MessageID":123}]}]}',
    b'{"Messages":[{"Status":"success","To":[{"Email":"failed@example.org","MessageID":true}]}]}',
    b'not-json',
])
def test_mailjet_failures_do_not_commit_signup_or_claim_delivery(public_mail, failure):
    client, sent, state = public_mail
    state['value'] = failure
    result = client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'failed@example.org',
                                                   'password': 'first unique passphrase 123'})
    assert result.status_code == 503
    assert result.json()['detail'] == 'Email delivery is unavailable. Try again later.'
    assert 'mailjet-private-test' not in result.text and len(sent) == 0
    with connect() as db:
        assert db.execute('SELECT 1 FROM users WHERE email_canonical=?', ('failed@example.org',)).fetchone() is None
        assert db.execute('SELECT 1 FROM account_tokens').fetchone() is None


def test_mailjet_failed_recovery_and_reset_notification_roll_back(public_mail):
    client, sent, state = public_mail
    client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'citizen@example.org',
                                          'password': 'first unique passphrase 123'})
    client.post('/api/auth/verify-email', json={'token': token(sent[0], 'verify'),
                                                'password': 'first unique passphrase 123'})
    state['value'] = urllib.error.URLError('network unavailable')
    failed = client.post('/api/auth/forgot-password', json={'email': 'citizen@example.org'})
    unknown = client.post('/api/auth/forgot-password', json={'email': 'unknown@example.org'})
    assert failed.status_code == unknown.status_code == 202
    assert failed.json() == unknown.json()
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


def test_forgot_response_precedes_lookup_and_delivery(public_mail):
    client, sent, state = public_mail
    client.post('/api/auth/signup', json={'name': 'Citizen', 'email': 'citizen@example.org',
                                          'password': 'first unique passphrase 123'})
    client.post('/api/auth/verify-email', json={'token': token(sent[0], 'verify'),
                                               'password': 'first unique passphrase 123'})
    state['value'] = TimeoutError('provider stalled')
    tasks = BackgroundTasks()
    request = Request({'type': 'http', 'client': ('testclient', 123), 'method': 'POST',
                       'path': '/api/auth/forgot-password', 'headers': []})
    known = forgot_password(EmailBody(email='citizen@example.org'), request, tasks)
    unknown = forgot_password(EmailBody(email='unknown@example.org'), request, tasks)
    assert known == unknown
    assert len(tasks.tasks) == 2
    assert state['attempts'] == 1 and len(sent) == 1  # Signup only; no reset send in the response path.
    with connect() as db:
        assert db.execute("SELECT 1 FROM account_tokens WHERE purpose='reset'").fetchone() is None


@pytest.mark.parametrize(('status', 'body', 'reason'), [
    (401, {'ErrorCode': 'mj-0001', 'ErrorMessage': 'secret should stay private'}, 'suspended_key'),
    (401, {'ErrorCode': 'mj-0015'}, 'invalid_credentials'),
    (401, {'ErrorCode': 'unknown'}, 'authentication_rejected'),
    (403, {'Messages': [{'Status': 'error', 'Errors': [{'ErrorCode': 'send-0008'}]}]}, 'unauthorized_sender'),
    (429, {'ErrorCode': 'unknown'}, 'rate_limited'),
    (503, {'ErrorCode': 'unknown'}, 'provider_unavailable'),
])
def test_mailjet_http_error_classification_is_internal(public_mail, status, body, reason, caplog):
    _, sent, state = public_mail
    state['value'] = urllib.error.HTTPError('https://api.mailjet.com/v3.1/send', status,
                                            'provider error', None, io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(MailDeliveryUnavailable) as raised:
        send_mail(None, 'recipient@example.org', 'Subject', 'Body')
    assert raised.value.reason == reason
    assert raised.value.detail == 'Email delivery is unavailable. Try again later.'
    assert 'secret should stay private' not in str(raised.value)
    assert 'secret should stay private' not in caplog.text
    assert 'mailjet-private-test' not in caplog.text
    assert state['attempts'] == 1 and sent == []


def test_mailjet_per_message_error_and_ambiguous_timeout_never_retry(public_mail):
    _, sent, state = public_mail
    state['value'] = b'{"Messages":[{"Status":"error","Errors":[{"ErrorCode":"send-0008","StatusCode":403}]}]}'
    with pytest.raises(MailDeliveryUnavailable) as rejected:
        send_mail(None, 'recipient@example.org', 'Subject', 'Body')
    assert rejected.value.reason == 'unauthorized_sender'
    state['value'] = TimeoutError('may have been accepted upstream')
    with pytest.raises(MailDeliveryUnavailable) as timed_out:
        send_mail(None, 'recipient@example.org', 'Subject', 'Body')
    assert timed_out.value.reason == 'transport_failure'
    assert state['attempts'] == 2 and sent == []


def test_mailjet_per_message_rate_limit_is_classified(public_mail):
    _, _, state = public_mail
    state['value'] = b'{"Messages":[{"Status":"error","Errors":[{"StatusCode":429}]}]}'
    with pytest.raises(MailDeliveryUnavailable) as raised:
        send_mail(None, 'recipient@example.org', 'Subject', 'Body')
    assert raised.value.reason == 'rate_limited'
    assert state['attempts'] == 1


def test_mailjet_staff_invitation_and_failure(public_mail):
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
    assert len(sent) == 1 and sent[0]['To'] == [{'Email': 'officer@example.org'}]
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
    monkeypatch.delenv('MAILJET_API_KEY', raising=False)
    monkeypatch.delenv('MAILJET_SECRET_KEY', raising=False)
    monkeypatch.delenv('MAIL_FROM', raising=False)
    with TestClient(app) as client:
        config = client.get('/api/auth/config').json()
        assert not config['registration_available'] and not config['recovery_available']
        assert client.get('/api/auth/dev-mailbox').status_code == 404
        assert client.post('/api/auth/signup', json={'name': 'Citizen',
            'email': 'citizen@example.org', 'password': 'a unique passphrase 123'}).status_code == 503
