"""One owner-approved synthetic Sydney/Singapore storage integration test.

Run only after independently verifying the testing bucket is PRIVATE in Neon
Console. This script never reads production data or prints credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from PIL import Image

from scripts.check_live_storage_preflight import preflight
from scripts.check_testing_target import check_target

APPLICATION_TABLES = (
    'users', 'complaints', 'history', 'notes', 'sessions', 'login_attempts',
    'attachments', 'account_tokens', 'auth_challenges', 'recovery_codes',
    'staff_invitations', 'mail_outbox',
)


class ValidationFailure(RuntimeError):
    pass


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValidationFailure(label)


def object_absent(client, bucket: str, key: str) -> bool:
    result = client.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=1)
    return not any(item.get('Key') == key for item in result.get('Contents', []))


def anonymous_read_status(endpoint: str, bucket: str, key: str) -> int:
    request = urllib.request.Request(f'{endpoint}/{bucket}/{key}', method='GET')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            # Do not return or log any response body.
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def image_bytes() -> bytes:
    image = Image.new('RGB', (2, 2), (31, 97, 149))
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def csrf(client: TestClient) -> dict[str, str]:
    return {'X-CSRF-Token': client.cookies.get('nagrikos_csrf', '')}


def api_status(client: TestClient, method: str, path: str, expected: int, label: str, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    require(response.status_code == expected, label)
    return response


def run() -> dict[str, object]:
    env_path = Path(__file__).resolve().parents[1] / '.env'
    # The read-only preflight must succeed before any live write.
    preflight(env_path, live_read=True)
    values = {key: value for key, value in dotenv_values(env_path).items() if value is not None}
    check_target(values)
    test_env = {
        **{key: values[key] for key in (
            'DATABASE_URL', 'DIRECT_URL', 'AWS_ENDPOINT_URL_S3', 'AWS_REGION',
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')},
        'OBJECT_STORAGE_BACKEND': 'neon',
        'OBJECT_STORAGE_BUCKET': 'nagrikos-attachments',
        'NAGRIKOS_MODE': 'public',
        'COOKIE_SECURE': 'true',
        'NAGRIKOS_REQUIRE_POSTGRES': 'true',
        'NAGRIKOS_REQUIRE_DURABLE_STORAGE': 'true',
        'NAGRIKOS_TOTP_KEY': Fernet.generate_key().decode('ascii'),
        'PUBLIC_BASE_URL': 'https://smoke.invalid',
        'CORS_ORIGINS': 'https://smoke.invalid',
        'MAILJET_API_KEY': 'smoke-only-key',
        'MAILJET_SECRET_KEY': 'smoke-only-secret',
        'MAIL_FROM': 'smoke@example.invalid',
    }
    marker = secrets.token_hex(6)
    success_key = marker + secrets.token_hex(6) + '.png'
    failure_key = marker + secrets.token_hex(6) + '.png'
    # These keys are generated before the API call so a lost HTTP response
    # cannot make a test-owned object impossible to identify and clean up.
    emails = [f'storage-{marker}-{index}@example.invalid' for index in (1, 2)]
    password = 'Synthetic storage validation ' + marker
    created_users: list[int] = []
    created_keys = (success_key, failure_key)
    results: dict[str, object] = {'integrity': False, 'authorization': False,
                                  'private_read': False, 'db_failure_cleanup': False,
                                  'db_cleanup': False, 'object_cleanup': False}
    failure: Exception | None = None
    orphan_keys: list[str] = []
    with tempfile.TemporaryDirectory(prefix='nagrikos-live-storage-') as uploads:
        with patch.dict(os.environ, {**test_env, 'UPLOAD_DIR': uploads}, clear=True):
            from app import account, auth, db, main, object_storage

            object_storage.validate_config()
            store = object_storage._client()
            bucket = 'nagrikos-attachments'
            require(all(object_absent(store, bucket, key) for key in created_keys),
                    'A generated test key already exists; no write performed')
            with db.connect() as connection:
                require(all(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
                            for table in APPLICATION_TABLES),
                        'Testing database contains existing application rows; no write performed')
                require(all(connection.execute('SELECT 1 FROM users WHERE email_canonical=?',
                                               (email,)).fetchone() is None for email in emails),
                        'A generated test identity already exists; no write performed')

            # FastAPI configures CORS and public routes when imported above.
            class KeySource:
                def __init__(self, values):
                    self.values = iter(values)
                def token_hex(self, size):
                    return next(self.values)[:-4] if size == 12 else secrets.token_hex(size)
                def __getattr__(self, name):
                    return getattr(secrets, name)

            # Use cryptographically random predeclared keys, while keeping the
            # application's key format and upload path unchanged.
            key_source = KeySource(created_keys)
            from app.auth import hash_password
            try:
                with db.connect() as connection:
                    for index, email in enumerate(emails):
                        user_id = connection.execute(
                            'INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,created_at,is_demo) '
                            'VALUES (?,?,?,?,?,?,?,0) RETURNING id',
                            (f'Synthetic storage reviewer {index + 1}', email, email,
                             int(time.time()), hash_password(password), 'citizen',
                             time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))).fetchone()[0]
                        created_users.append(user_id)

                with patch.object(main, 'secrets', key_source), \
                     TestClient(main.app, base_url='https://smoke.invalid', raise_server_exceptions=False) as owner, \
                     TestClient(main.app, base_url='https://smoke.invalid', raise_server_exceptions=False) as other:
                    for client, email in ((owner, emails[0]), (other, emails[1])):
                        api_status(client, 'post', '/api/auth/login', 200, 'synthetic login failed',
                                   json={'email': email, 'password': password})
                    original = image_bytes()
                    uploaded = api_status(owner, 'post', '/api/attachments', 200, 'authenticated upload failed',
                                          headers=csrf(owner), files={'file': (f'synthetic-{marker}.png', original, 'image/png')})
                    key = uploaded.json().get('path')
                    require(key == success_key, 'upload returned an unexpected object key')
                    with db.connect() as connection:
                        row = connection.execute(
                            'SELECT uploaded_by,complaint_id FROM attachments WHERE filename=?',
                            (success_key,)).fetchone()
                    require(row is not None and row['uploaded_by'] == created_users[0]
                            and row['complaint_id'] is None, 'Sydney attachment metadata did not persist')
                    direct = object_storage.get(success_key)
                    authorized = api_status(owner, 'get', f'/api/attachments/{success_key}', 200,
                                            'authorized download failed').content
                    require(direct is not None and hashlib.sha256(direct).digest() ==
                            hashlib.sha256(authorized).digest(), 'SHA-256 integrity mismatch')
                    with Image.open(io.BytesIO(authorized)) as decoded:
                        require(decoded.size == (2, 2) and decoded.convert('RGB').getpixel((0, 0)) ==
                                (31, 97, 149), 'Downloaded image pixels changed')
                    results['integrity'] = True
                    results['sha256'] = hashlib.sha256(authorized).hexdigest()
                    api_status(other, 'get', f'/api/attachments/{success_key}', 404,
                               'other citizen accessed private attachment')
                    with TestClient(main.app, base_url='https://smoke.invalid') as anonymous:
                        api_status(anonymous, 'get', f'/api/attachments/{success_key}', 401,
                                   'anonymous access was allowed')
                    results['authorization'] = True
                    status = anonymous_read_status(values['AWS_ENDPOINT_URL_S3'], bucket, success_key)
                    require(status in (401, 403, 404), 'unauthenticated S3 read was allowed')
                    results['private_read'] = True
                    results['private_http_status'] = status

                    @contextmanager
                    def failed_metadata_insert():
                        raise RuntimeError('synthetic metadata failure')
                        yield

                    with patch.object(main, 'connect', failed_metadata_insert):
                        failed = owner.post('/api/attachments', headers=csrf(owner),
                                            files={'file': (f'synthetic-failure-{marker}.png', original, 'image/png')})
                    require(failed.status_code == 500, 'failure injection did not reach metadata stage')
                    require(object_absent(store, bucket, failure_key),
                            'failed metadata insert left its test object')
                    with db.connect() as connection:
                        require(connection.execute('SELECT 1 FROM attachments WHERE filename=?',
                                                   (failure_key,)).fetchone() is None,
                                'failed metadata insert left its test row')
                    results['db_failure_cleanup'] = True
            except Exception as exc:
                failure = exc
            finally:
                # Delete only known test rows and keys. User deletion cascades
                # the synthetic sessions; no other account is addressed.
                try:
                    with db.connect() as connection:
                        if len(created_users) == 2:
                            connection.execute('DELETE FROM attachments WHERE filename IN (?,?) AND uploaded_by IN (?,?)',
                                               (*created_keys, *created_users))
                        for user_id, email in zip(created_users, emails):
                            connection.execute('DELETE FROM users WHERE id=? AND email_canonical=?',
                                               (user_id, email))
                    with db.connect() as connection:
                        results['db_cleanup'] = all(
                            connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
                            for table in APPLICATION_TABLES)
                except Exception as exc:
                    if failure is None:
                        failure = exc
                for key in created_keys:
                    try:
                        # Never delete an object while its metadata row still
                        # exists: preserve recoverability across the projects.
                        with db.connect() as connection:
                            if connection.execute('SELECT 1 FROM attachments WHERE filename=?',
                                                  (key,)).fetchone() is not None:
                                orphan_keys.append(key)
                                continue
                        if not object_absent(store, bucket, key):
                            object_storage.delete(key)
                        if not object_absent(store, bucket, key):
                            orphan_keys.append(key)
                    except Exception:
                        orphan_keys.append(key)
                results['object_cleanup'] = not orphan_keys
                results['orphan_keys'] = orphan_keys
                if orphan_keys:
                    # Only predeclared test-owned random keys are printed.
                    print('test_objects_requiring_manual_review: ' + ','.join(orphan_keys), file=sys.stderr)
                try:
                    from scripts.audit_attachment_storage import audit
                    results['reconciliation'] = audit()
                except Exception:
                    results['reconciliation'] = None
            if failure is not None:
                raise ValidationFailure(f'live integration failed ({type(failure).__name__})')
            require(results['db_cleanup'] and results['object_cleanup'], 'test resource cleanup was incomplete')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-verified', action='store_true',
                        help='Use only after independent Neon Console confirmation of PRIVATE bucket access')
    args = parser.parse_args()
    if not args.private_verified:
        print('Live validation blocked: independent private-bucket confirmation required')
        raise SystemExit(2)
    try:
        result = run()
    except Exception as exc:
        print(f'Live validation: FAIL ({type(exc).__name__}); inspect test-specific cleanup', file=sys.stderr)
        raise SystemExit(1) from None
    for name in ('integrity', 'authorization', 'private_read', 'db_failure_cleanup',
                 'db_cleanup', 'object_cleanup'):
        print(f'{name}: {"PASS" if result[name] else "FAIL"}')
    print('sha256_match: PASS')
    print(f'unauthenticated_http_status: {result["private_http_status"]}')
    print(f'reconciliation: {result["reconciliation"]}')
