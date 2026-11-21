"""Checks that do not require remote database credentials."""
import sqlite3
import runpy
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, select

from app import postgres
from app.account import validate_config
from app.db import initialize
from app.models import metadata, sessions, users
from scripts.migrate_sqlite_to_postgres import snapshot, upgrade_snapshot, source_rows
from scripts.migrate_sqlite_to_postgres import urls
from scripts.disable_demo_credentials import disable, DISABLED_HASH


def test_postgres_schema_matches_additive_sqlite_schema(tmp_path, monkeypatch):
    path = tmp_path / 'source.db'
    monkeypatch.setenv('DATABASE_PATH', str(path))
    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    initialize()
    with sqlite3.connect(path) as db:
        for table in metadata.sorted_tables:
            actual = {row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')}
            assert actual == set(table.c.keys()), table.name
            assert source_rows(db, table) == []
    revision = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / '20261114_01_initial.py'))
    statements = revision['SCHEMA_SQL']
    assert {statement.split('CREATE TABLE ', 1)[1].split(' ', 1)[0]
            for statement in statements if 'CREATE TABLE ' in statement} == set(metadata.tables)
    backup = snapshot(path)
    assert backup != path and backup.exists()
    upgrade_snapshot(backup)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_postgres_record_supports_existing_sqlite_access_patterns():
    engine = create_engine('sqlite:///:memory:')
    with engine.connect() as connection:
        result = postgres.Result(connection.exec_driver_sql('SELECT 7 AS id, 9 AS count'))
        row = result.fetchone()
        assert row[0] == 7
        assert row['id'] == 7
        assert dict(row) == {'id': 7, 'count': 9}
        assert result.fetchone() is None
    engine.dispose()


def test_postgres_urls_require_tls_and_public_mode(monkeypatch):
    url = 'postgresql://role:secret@ep-test-pooler.region.aws.neon.tech/app?sslmode=require'
    assert postgres._url(url).startswith('postgresql+psycopg://')
    with pytest.raises(RuntimeError, match='TLS'):
        postgres._url(url.replace('sslmode=require', 'sslmode=disable'))
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('NAGRIKOS_MODE', 'demo')
    with pytest.raises(RuntimeError, match='public mode'):
        validate_config()
    monkeypatch.setenv('DIRECT_URL', url.replace('-pooler.', '.'))
    direct, sslmode = urls()
    assert direct.startswith('postgresql+psycopg://') and sslmode == 'require'
    monkeypatch.setenv('DIRECT_URL', url)
    with pytest.raises(RuntimeError, match='same Neon branch'):
        urls()


def test_hosted_backend_refuses_missing_postgres_url(monkeypatch):
    monkeypatch.setenv('NAGRIKOS_REQUIRE_POSTGRES', 'true')
    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='requires DATABASE_URL'):
        validate_config()


def test_postgres_adapter_keeps_values_bound():
    class Capture:
        def exec_driver_sql(self, sql, params):
            self.sql, self.params = sql, params
            return self

        rowcount = 1

    capture = Capture()
    postgres.Connection(capture).execute('SELECT ? AS value', ("a'b",))
    assert capture.sql == 'SELECT %s AS value'
    assert capture.params == ("a'b",)


def test_demo_credentials_disabled_only_after_real_admin_exists():
    engine = create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(users), [
            {'id': 1, 'name': 'Demo', 'email': 'demo@example.org',
             'email_canonical': 'demo@example.org', 'password_hash': 'old-hash',
             'role': 'citizen', 'created_at': '2026-01-01T00:00:00Z', 'is_demo': 1,
             'mfa_secret': 'encrypted-value'},
        ])
        connection.execute(insert(sessions), {'token_hash': 'hash', 'user_id': 1,
            'csrf_hash': 'csrf', 'expires_at': 9999999999, 'created_at': 1, 'last_seen_at': 1})
        with pytest.raises(RuntimeError, match='non-demo administrator'):
            disable(connection)
        connection.execute(insert(users), {'id': 2, 'name': 'Admin',
            'email': 'admin@example.org', 'email_canonical': 'admin@example.org',
            'password_hash': 'admin-hash', 'role': 'admin',
            'created_at': '2026-01-01T00:00:00Z', 'is_demo': 0})
        assert disable(connection) == 1
        demo = connection.execute(select(users).where(users.c.id == 1)).one()._mapping
        admin = connection.execute(select(users).where(users.c.id == 2)).one()._mapping
        assert demo['password_hash'] == DISABLED_HASH and demo['mfa_secret'] is None
        assert admin['password_hash'] == 'admin-hash'
        assert connection.execute(select(sessions)).fetchall() == []
    engine.dispose()


def test_admin_bootstrap_env_secret_is_one_time(tmp_path, monkeypatch, capsys):
    import sys
    from scripts import provision_admin
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'bootstrap.db'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.setenv('NAGRIKOS_BOOTSTRAP_ADMIN_PASSWORD', 'unique bootstrap phrase 123')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL', 'admin@example.org')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_NAME', 'Admin')
    # The production-target guard is tested separately; this test exercises
    # the one-time account creation behavior against a disposable SQLite DB.
    monkeypatch.setattr(provision_admin, 'check_admin_target', lambda: None)
    monkeypatch.setattr(provision_admin, 'password_policy', lambda password: None)
    monkeypatch.setattr(sys, 'argv', ['provision_admin.py'])
    provision_admin.main()
    with sqlite3.connect(tmp_path / 'bootstrap.db') as db:
        assert db.execute("SELECT count(*) FROM users WHERE role='admin' AND is_demo=0").fetchone()[0] == 1
    with pytest.raises(SystemExit):
        provision_admin.main()
    output = capsys.readouterr()
    assert 'unique bootstrap phrase 123' not in output.out + output.err


def test_actions_admin_bootstrap_fails_closed_without_password(monkeypatch):
    import sys
    from scripts import provision_admin

    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL', 'admin@example.org')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_NAME', 'Admin')
    monkeypatch.delenv('NAGRIKOS_BOOTSTRAP_ADMIN_PASSWORD', raising=False)
    monkeypatch.setattr(provision_admin, 'check_admin_target', lambda: None)
    monkeypatch.setattr(provision_admin, 'initialize', lambda: pytest.fail('database opened'))
    monkeypatch.setattr(provision_admin.getpass, 'getpass', lambda *_: pytest.fail('interactive prompt opened'))
    monkeypatch.setattr(sys, 'argv', ['provision_admin.py'])
    with pytest.raises(SystemExit):
        provision_admin.main()


def test_postgres_admin_bootstrap_locks_before_duplicate_check(monkeypatch):
    import contextlib
    import sys
    from scripts import provision_admin

    statements = []

    class Result:
        def fetchone(self):
            return None

    class Connection:
        def execute(self, sql, params=()):
            statements.append(sql)
            return Result()

    @contextlib.contextmanager
    def fake_connect():
        yield Connection()

    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.setenv('NAGRIKOS_BOOTSTRAP_ADMIN_PASSWORD', 'unique bootstrap phrase 123')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL', 'admin@example.org')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_NAME', 'Admin')
    monkeypatch.setattr(provision_admin, 'check_admin_target', lambda: None)
    monkeypatch.setattr(provision_admin, 'password_policy', lambda password: None)
    monkeypatch.setattr(provision_admin, 'initialize', lambda: None)
    monkeypatch.setattr(provision_admin, 'connect', fake_connect)
    monkeypatch.setattr(provision_admin.postgres, 'enabled', lambda: True)
    monkeypatch.setattr(provision_admin, 'hash_password', lambda password: 'test-hash')
    monkeypatch.setattr(sys, 'argv', ['provision_admin.py'])
    provision_admin.main()
    assert statements[0].startswith('SELECT pg_advisory_xact_lock(')
    assert 'FROM users WHERE role=' in statements[1]
    assert statements[-1].startswith('INSERT INTO users(')


def test_admin_cli_failure_hides_connection_details():
    import os
    import subprocess
    import sys
    from scripts.check_production_target import PROJECT_ID, PRODUCTION_BRANCH_ID

    marker = 'dummy_private_password_marker'
    env = {**os.environ,
           'NAGRIKOS_MODE': 'public',
           'NAGRIKOS_ADMIN_TARGET': 'production',
           'NEON_PRODUCTION_PROJECT_ID': PROJECT_ID,
           'NEON_PRODUCTION_BRANCH_ID': PRODUCTION_BRANCH_ID,
           'DATABASE_URL': f'postgresql://neondb_owner:{marker}@invalid.example/neondb?sslmode=require',
           'GITHUB_ACTIONS': 'true'}
    result = subprocess.run([sys.executable, 'scripts/provision_admin.py'],
                            cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert marker not in result.stdout + result.stderr
    assert 'Administrator provisioning FAILED' in result.stderr
