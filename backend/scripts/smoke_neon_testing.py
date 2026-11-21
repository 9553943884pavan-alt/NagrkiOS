"""Rollback-only FastAPI smoke test for the pinned Neon testing branch.

Run only through the protected, manually dispatched GitHub environment. No
Alembic, attachment upload, external mail, or persistent application writes.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from scripts.check_testing_target import check_target


TABLES = frozenset({
    'users', 'complaints', 'history', 'notes', 'sessions', 'login_attempts',
    'attachments', 'account_tokens', 'auth_challenges', 'recovery_codes',
    'staff_invitations', 'mail_outbox',
})
REVISION = '20261114_01'


class SmokeFailure(RuntimeError):
    pass


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SmokeFailure(label)


def schema_and_counts(connection) -> dict[str, int]:
    """Read only: reject an unexpected schema before synthetic writes."""
    from sqlalchemy import inspect

    tables = set(inspect(connection).get_table_names(schema='public'))
    require(tables == TABLES | {'alembic_version'}, 'schema does not have the expected 12 tables')
    rows = connection.exec_driver_sql('SELECT version_num FROM alembic_version').fetchall()
    require(len(rows) == 1 and rows[0][0] == REVISION, 'unexpected Alembic revision')
    return {name: connection.exec_driver_sql(f'SELECT COUNT(*) FROM public.{name}').scalar_one()
            for name in sorted(TABLES)}


def temporary_commit_and_rollback(engine) -> None:
    """Exercise durable commit and rollback using only a session-local table."""
    name = 'smoke_' + uuid.uuid4().hex
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE TEMP TABLE {name} (value INTEGER) ON COMMIT PRESERVE ROWS')
        connection.exec_driver_sql(f'INSERT INTO {name} VALUES (1)')
        connection.commit()
        require(connection.exec_driver_sql(f'SELECT COUNT(*) FROM {name}').scalar_one() == 1,
                'temporary commit did not persist within session')
        connection.exec_driver_sql(f'INSERT INTO {name} VALUES (2)')
        connection.rollback()
        require(connection.exec_driver_sql(f'SELECT COUNT(*) FROM {name}').scalar_one() == 1,
                'temporary rollback did not restore committed row')
        connection.rollback()
    # PostgreSQL drops the temporary table on session close; no public table is created.


class RollbackOnlyAdapter:
    """Retain application SQL behavior while withholding every app-level commit."""

    def __init__(self, connection):
        from app.postgres import Connection

        self._delegate = Connection(connection)

    def execute(self, *args, **kwargs):
        return self._delegate.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._delegate.executemany(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def rollback_only_connect(connection):
    """Each API connection gets a savepoint within one outer transaction."""
    lock = threading.RLock()

    @contextmanager
    def connect():
        with lock:
            savepoint = connection.begin_nested()
            try:
                yield RollbackOnlyAdapter(connection)
            except BaseException:
                savepoint.rollback()
                raise
            else:
                savepoint.commit()

    return connect


def response(client, method: str, path: str, status: int, label: str, **kwargs):
    result = getattr(client, method)(path, **kwargs)
    require(result.status_code == status, label)
    return result


def exercise_api(connection, marker: str) -> None:
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
    # FastAPI configures CORS and its public routes at import time.
    with patch.dict(os.environ, {'NAGRIKOS_MODE': 'public', 'CORS_ORIGINS': 'https://smoke.invalid'}):
        from app import account, db, main

    mail = []
    def capture_mail(_db, recipient, subject, body):
        mail.append(body)

    class EmptyRange:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, _size):
            return b''

    def pwned_only(request, **_):
        require(request.full_url.startswith('https://api.pwnedpasswords.com/range/'),
                'unexpected external network request')
        return EmptyRange()

    connect = rollback_only_connect(connection)
    smoke_settings = {
        'NAGRIKOS_MODE': 'public', 'COOKIE_SECURE': 'true',
        'NAGRIKOS_TOTP_KEY': Fernet.generate_key().decode('ascii'),
        'NAGRIKOS_REQUIRE_POSTGRES': 'true', 'NAGRIKOS_REQUIRE_DURABLE_STORAGE': 'false',
        # Test-only placeholders; send_mail is patched below.
        'MAILJET_API_KEY': 'smoke-only-key', 'MAILJET_SECRET_KEY': 'smoke-only-secret',
        'MAIL_FROM': 'smoke@example.invalid', 'PUBLIC_BASE_URL': 'https://smoke.invalid',
        'CORS_ORIGINS': 'https://smoke.invalid',
        **{name: '' for name in (
            'OBJECT_STORAGE_ENDPOINT_URL', 'OBJECT_STORAGE_REGION',
            'OBJECT_STORAGE_ACCESS_KEY_ID', 'OBJECT_STORAGE_SECRET_ACCESS_KEY',
            'OBJECT_STORAGE_BUCKET')},
    }
    with tempfile.TemporaryDirectory(prefix='nagrikos-smoke-') as uploads, \
         patch.dict(os.environ, {**smoke_settings, 'UPLOAD_DIR': uploads}), \
         patch.object(db, 'connect', connect), patch.object(main, 'connect', connect), \
         patch.object(account, 'connect', connect), patch.object(main, 'UPLOAD_DIR', __import__('pathlib').Path(uploads)), \
         patch.object(account, 'send_mail', capture_mail), patch.object(account.urllib.request, 'urlopen', pwned_only):
        # auth.current_user imports db.connect dynamically, so it uses the same transaction.
        password = 'Smoke only long passphrase ' + marker
        email = f'citizen-{marker}@example.invalid'
        with TestClient(main.app, base_url='https://smoke.invalid') as citizen:
            response(citizen, 'get', '/api/health', 200, 'health route failed')
            response(citizen, 'post', '/api/auth/signup', 422, 'signup accepted privileged role',
                     json={'name':'Smoke Citizen', 'email':email, 'password':password, 'role':'admin'})
            response(citizen, 'post', '/api/auth/signup', 202, 'citizen signup failed',
                     json={'name':'Smoke Citizen', 'email':email, 'password':password})
            response(citizen, 'post', '/api/auth/login', 401, 'unverified login succeeded',
                     json={'email':email, 'password':password})
            require(len(mail) == 1, 'verification mail was not captured once')
            token_match = re.search(r'[#?&]verify=([^\s]+)', mail.pop())
            require(token_match is not None, 'verification token missing from test transport')
            response(citizen, 'post', '/api/auth/verify-email', 200, 'email verification failed',
                     json={'token':token_match.group(1), 'password':password})
            response(citizen, 'post', '/api/auth/login', 200, 'citizen login failed',
                     json={'email':email, 'password':password})
            require(response(citizen, 'get', '/api/auth/me', 200, 'session refresh failed').json()['role'] == 'citizen',
                    'session role mismatch')
            csrf = lambda client: {'X-CSRF-Token': client.cookies.get('nagrikos_csrf', '')}
            body = {'title':'Synthetic smoke case', 'description':'Synthetic smoke complaint for database testing only.',
                    'district':'Prayagraj', 'channel':'web'}
            created = response(citizen, 'post', '/api/complaints', 201, 'complaint creation failed',
                               headers=csrf(citizen), json=body).json()
            case_id = created['id']
            department = created['department']
            require(created['citizen_id'] is not None, 'complaint ownership missing')
            detail = response(citizen, 'get', f'/api/complaints/{case_id}', 200, 'citizen read failed').json()
            require(any(h['action'] == 'created' for h in detail['history']), 'creation history missing')
            require(response(citizen, 'get', '/api/complaints', 200, 'citizen list failed').json()['total'] == 1,
                    'citizen list count mismatch')
            response(citizen, 'patch', f'/api/complaints/{case_id}', 403, 'citizen changed case',
                     headers=csrf(citizen), json={'status':'in_progress'})
            response(citizen, 'post', f'/api/complaints/{case_id}/notes', 403, 'citizen added official note',
                     headers=csrf(citizen), json={'body':'Unauthorized'})

            from app.auth import hash_password
            from app.db import iso
            from datetime import datetime, timezone
            now = iso(datetime.now(timezone.utc))
            identities = {}
            for role, dept in [('other', None), ('officer', department),
                               ('outside', 'General Administration' if department != 'General Administration' else 'Public Works Department'),
                               ('admin', None)]:
                actual_role = 'citizen' if role == 'other' else 'officer' if role == 'outside' else role
                address = f'{role}-{marker}@example.invalid'
                identities[role] = (address, password)
                with connect() as tx:
                    tx.execute('INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,department,created_at,is_demo) '
                               'VALUES (?,?,?,?,?,?,?,?,0)',
                               (f'Smoke {role}', address, address, 1, hash_password(password), actual_role, dept, now))

            with TestClient(main.app, base_url='https://smoke.invalid') as other:
                response(other, 'post', '/api/auth/login', 200, 'second citizen login failed',
                         json={'email':identities['other'][0], 'password':password})
                response(other, 'get', f'/api/complaints/{case_id}', 404, 'other citizen read case')
                require(response(other, 'get', '/api/complaints', 200, 'other citizen list failed').json()['total'] == 0,
                        'other citizen saw case')
            with TestClient(main.app, base_url='https://smoke.invalid') as outside:
                response(outside, 'post', '/api/auth/login', 200, 'outside officer login failed',
                         json={'email':identities['outside'][0], 'password':password})
                response(outside, 'get', f'/api/complaints/{case_id}', 404, 'outside officer read case')
                response(outside, 'patch', f'/api/complaints/{case_id}', 404, 'outside officer changed case',
                         headers=csrf(outside), json={'status':'in_progress'})
            with TestClient(main.app, base_url='https://smoke.invalid') as officer:
                response(officer, 'post', '/api/auth/login', 200, 'officer login failed',
                         json={'email':identities['officer'][0], 'password':password})
                response(officer, 'post', '/api/complaints', 403, 'officer filed citizen case',
                         headers=csrf(officer), json=body)
                response(officer, 'patch', f'/api/complaints/{case_id}', 403, 'missing CSRF accepted',
                         json={'status':'in_progress'})
                updated = response(officer, 'patch', f'/api/complaints/{case_id}', 200, 'officer update failed',
                                   headers=csrf(officer), json={'status':'in_progress'}).json()
                require(updated['status'] == 'in_progress', 'status did not persist across API calls')
                response(officer, 'post', f'/api/complaints/{case_id}/notes', 201, 'officer note failed',
                         headers=csrf(officer), json={'body':'Synthetic review note', 'is_public':True})
                detail = response(officer, 'get', f'/api/complaints/{case_id}', 200, 'officer read failed').json()
                require(len(detail['notes']) == 1 and len(detail['history']) >= 3,
                        'note or change history missing')
            with TestClient(main.app, base_url='https://smoke.invalid') as admin:
                response(admin, 'post', '/api/auth/login', 200, 'admin login failed',
                         json={'email':identities['admin'][0], 'password':password})
                response(admin, 'get', f'/api/complaints/{case_id}', 200, 'admin read failed')
                require(response(admin, 'get', '/api/complaints', 200, 'admin list failed').json()['total'] == 1,
                        'admin list mismatch')
            response(citizen, 'post', '/api/auth/logout', 200, 'logout failed', headers=csrf(citizen))
            response(citizen, 'get', '/api/auth/me', 401, 'logged-out session remained valid')
        with TestClient(main.app, base_url='https://smoke.invalid') as anonymous:
            response(anonymous, 'get', f'/api/complaints/{case_id}', 401, 'anonymous case read succeeded')


def run_smoke(environ=None, engine_factory=None) -> None:
    """Guard before any connection; outer rollback runs even when API assertions fail."""
    env = os.environ if environ is None else environ
    require(env.get('SMOKE_APPROVAL') == 'RUN-TESTING-SMOKE', 'explicit smoke approval missing')
    check_target(env)
    if engine_factory is None:
        from app.postgres import engine_for
        from sqlalchemy import create_engine, pool

        def engine_factory(value):
            if value == env['DATABASE_URL']:
                return engine_for(value)
            # The application's engine_for deliberately rejects direct Neon
            # hosts. Read-only preflight and the TEMP-table check need direct.
            return create_engine(value.replace('postgresql://', 'postgresql+psycopg://', 1),
                                 connect_args={'connect_timeout': 5},
                                 poolclass=pool.NullPool, pool_pre_ping=True)
    direct = engine_factory(env['DIRECT_URL'])
    try:
        pooled = engine_factory(env['DATABASE_URL'])
    except Exception:
        direct.dispose()
        raise
    try:
        with direct.connect() as reader:
            before = schema_and_counts(reader)
            reader.rollback()
        temporary_commit_and_rollback(direct)
        marker = uuid.uuid4().hex
        with pooled.connect() as connection:
            outer = connection.begin()
            try:
                with patch.dict(os.environ, dict(env)):
                    exercise_api(connection, marker)
            finally:
                outer.rollback()
        with direct.connect() as reader:
            after = schema_and_counts(reader)
            require(after == before, 'application table counts changed after rollback')
            require(reader.exec_driver_sql('SELECT COUNT(*) FROM users WHERE email LIKE %s',
                                          (f'%-{marker}@example.invalid',)).scalar_one() == 0,
                    'synthetic identity remained after rollback')
            reader.rollback()
    finally:
        pooled.dispose()
        direct.dispose()


if __name__ == '__main__':
    try:
        run_smoke()
    except Exception as exc:
        # Do not print SQLAlchemy exception text: it can contain bound values.
        print(f'Testing smoke FAILED ({type(exc).__name__}); application transaction rolled back', file=sys.stderr)
        raise SystemExit(1) from None
    print('Testing smoke PASSED: schema, auth, complaint lifecycle, access controls, temporary commit/rollback, cleanup')
