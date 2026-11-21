"""Explicit, one-attempt Mailjet diagnostic; never opens the application database."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

from dotenv import dotenv_values

from app.account import MailDeliveryUnavailable, canonical, send_mail
from scripts.check_production_target import PRODUCTION_DIRECT_HOST, TESTING_DIRECT_HOST


ENV_PATH = Path(__file__).resolve().parents[1] / '.env'
BASE = 'https://api.mailjet.com'
SUBJECT = 'NagrikOS — Mailjet Delivery Test'
BODY = 'This is an authorized transactional email delivery test for NagrikOS. No action is required.'


def emit(**fields):
    print(json.dumps(fields, separators=(',', ':'), sort_keys=True))


def config():
    values = dotenv_values(ENV_PATH)
    for name in ('MAILJET_API_KEY', 'MAILJET_SECRET_KEY', 'MAIL_FROM'):
        value = values.get(name)
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f'{name}_invalid')
    for name in ('MAILJET_API_KEY', 'MAILJET_SECRET_KEY'):
        value = values[name]
        if any(not 33 <= ord(char) <= 126 for char in value) or (name == 'MAILJET_API_KEY' and ':' in value):
            raise ValueError(f'{name}_invalid')
    sender = values['MAIL_FROM']
    try:
        canonical(sender)
    except Exception:
        raise ValueError('MAIL_FROM_invalid') from None
    if any(ord(char) < 33 or ord(char) > 126 for char in sender):
        raise ValueError('MAIL_FROM_invalid')
    return values


def neon_target(values):
    """Classify URL hosts locally; never connect to PostgreSQL or print URLs."""
    known = {
        PRODUCTION_DIRECT_HOST: 'sydney_production',
        TESTING_DIRECT_HOST: 'sydney_testing',
    }
    targets = []
    for name in ('DATABASE_URL', 'DIRECT_URL'):
        raw = values.get(name)
        if not raw:
            continue
        try:
            parsed = urlsplit(raw)
            host = parsed.hostname or ''
        except ValueError:
            raise ValueError('neon_target_invalid') from None
        if parsed.scheme not in ('postgresql', 'postgresql+psycopg') or not parsed.username or not parsed.password:
            raise ValueError('neon_target_invalid')
        direct = host.replace('-pooler.', '.', 1)
        if direct not in known or (name == 'DIRECT_URL' and direct != host):
            raise ValueError('neon_target_unrecognized')
        targets.append(known[direct])
    if not targets:
        return 'not_configured'
    if len(set(targets)) != 1:
        raise ValueError('neon_target_mismatch')
    return targets[0]


def auth_header(values):
    pair = (values['MAILJET_API_KEY'] + ':' + values['MAILJET_SECRET_KEY']).encode('ascii')
    return 'Basic ' + base64.b64encode(pair).decode('ascii')


def read_only(path, authorization):
    request = urllib.request.Request(BASE + path, headers={
        'Authorization': authorization, 'Accept': 'application/json'}, method='GET')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                return response.status, None
            raw = response.read(65_537)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (OSError, ValueError):
        return None, None
    if len(raw) > 65_536:
        return 200, None
    try:
        return 200, json.loads(raw)
    except (ValueError, UnicodeError):
        return 200, None


def preflight(values):
    target = neon_target(values)
    authorization = auth_header(values)
    profile_status, profile = read_only('/v3/REST/myprofile', authorization)
    if profile_status is None:
        raise ValueError('profile_network_unavailable')
    if profile_status != 200 or not isinstance(profile, dict):
        raise ValueError('profile_auth_failed')
    sender_path = '/v3/REST/sender/' + quote(values['MAIL_FROM'], safe='')
    sender_status, sender = read_only(sender_path, authorization)
    if sender_status is None:
        raise ValueError('sender_network_unavailable')
    data = sender.get('Data') if isinstance(sender, dict) else None
    sender_item = data[0] if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) else None
    if (sender_status != 200 or sender_item is None or
            sender_item.get('Email', '').casefold() != values['MAIL_FROM'].casefold() or
            str(sender_item.get('Status', '')).casefold() != 'active'):
        raise ValueError('sender_not_confirmed_active')
    key_status, key_document = read_only('/v3/REST/apikey', authorization)
    if key_status is None:
        raise ValueError('apikey_network_unavailable')
    if key_status != 200 or not isinstance(key_document, dict):
        raise ValueError('apikey_read_failed')
    keys = key_document.get('Data')
    match = next((item for item in keys if isinstance(item, dict) and
                  item.get('APIKey') == values['MAILJET_API_KEY']), None) if isinstance(keys, list) else None
    key_active = match.get('IsActive') if match else None
    if key_active is False or (isinstance(key_active, str) and key_active.casefold() == 'false'):
        raise ValueError('apikey_inactive')
    key_state = 'active' if key_active is True or (isinstance(key_active, str) and key_active.casefold() == 'true') else 'unverified'
    emit(phase='preflight', result='PASS', variables='valid', neon_target=target,
         profile_http=profile_status, sender_http=sender_status, sender_status='active',
         apikey_http=key_status, apikey_status=key_state,
         sending_permission='not_proven_by_read_only_api', sending_limit='not_exposed_by_checked_endpoints')
    return authorization


class CaptureResponse:
    def __init__(self, response, capture):
        self.response = response
        self.capture = capture
        self.status = response.status

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def read(self, size):
        raw = self.response.read(size)
        self.capture['body'] = raw
        return raw


def send_once(values):
    capture = {'attempts': 0, 'status': None, 'body': None}
    original = urllib.request.urlopen

    def single_post(request, **kwargs):
        if request.full_url != BASE + '/v3.1/send' or request.get_method() != 'POST':
            raise RuntimeError('unexpected_request')
        if capture['attempts']:
            raise RuntimeError('second_send_blocked')
        capture['attempts'] = 1
        try:
            response = original(request, **kwargs)
        except urllib.error.HTTPError as exc:
            capture['status'] = exc.code
            raise
        capture['status'] = response.status
        return CaptureResponse(response, capture)

    for name in ('MAILJET_API_KEY', 'MAILJET_SECRET_KEY', 'MAIL_FROM'):
        os.environ[name] = values[name]
    urllib.request.urlopen = single_post
    try:
        send_mail(None, values['MAIL_FROM'], SUBJECT, BODY)
    except MailDeliveryUnavailable as exc:
        emit(phase='send', attempts=capture['attempts'], http_status=capture['status'],
             result='REJECTED_OR_UNCONFIRMED', classification=exc.reason)
        return None
    except Exception:
        emit(phase='send', attempts=capture['attempts'], http_status=capture['status'],
             result='UNCONFIRMED', classification='unexpected_local_error')
        return None
    finally:
        urllib.request.urlopen = original
    try:
        document = json.loads(capture['body'])
        to = document['Messages'][0]['To'][0]
        message_id = to['MessageID']
        if (type(message_id) is not int or message_id <= 0 or
                to['Email'].casefold() != values['MAIL_FROM'].casefold()):
            raise ValueError()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        emit(phase='send', attempts=1, http_status=capture['status'], result='UNCONFIRMED',
             classification='invalid_response')
        return None
    emit(phase='send', attempts=1, http_status=capture['status'], result='ACCEPTED',
         classification='success', message_status='success', recipient_match=True, message_id=message_id)
    return message_id


def activity(message_id, authorization):
    status, document = read_only('/v3/REST/message/' + str(message_id), authorization)
    data = document.get('Data') if isinstance(document, dict) else None
    item = data[0] if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) else None
    message_status = item.get('Status') if item else None
    if not isinstance(message_status, str) or not re.fullmatch(r'[A-Za-z_-]{1,32}', message_status):
        message_status = 'unconfirmed'
    emit(phase='activity', http_status=status, message_status=message_status,
         message_id=message_id)
    history_status, history_document = read_only('/v3/REST/messagehistory/' + str(message_id), authorization)
    events = history_document.get('Data') if isinstance(history_document, dict) else None
    allowed = {'sent', 'delivered', 'opened', 'clicked', 'queued', 'bounce', 'blocked', 'deferred'}
    event_types = sorted({item['EventType'].casefold() for item in events
                          if isinstance(item, dict) and isinstance(item.get('EventType'), str) and
                          item['EventType'].casefold() in allowed}) if isinstance(events, list) else []
    emit(phase='history', http_status=history_status, message_id=message_id,
         event_types=event_types)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-only', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--send-once', action='store_true')
    mode.add_argument('--activity-id', type=int)
    args = parser.parse_args()
    try:
        values = config()
        if args.local_only:
            emit(phase='local_preflight', result='PASS', variables='valid',
                 neon_target=neon_target(values), database_connection='not_attempted')
            return 0
        authorization = preflight(values)
    except ValueError as exc:
        emit(phase='preflight', result='FAIL', classification=str(exc))
        return 1
    except Exception:
        emit(phase='preflight', result='FAIL', classification='unexpected_local_error')
        return 1
    if args.activity_id is not None:
        if args.activity_id <= 0:
            emit(phase='activity', result='FAIL', classification='invalid_message_id')
            return 1
        activity(args.activity_id, authorization)
        return 0
    if not args.send_once:
        return 0
    message_id = send_once(values)
    if message_id is None:
        return 2
    activity(message_id, authorization)
    return 0


if __name__ == '__main__':
    sys.exit(main())
