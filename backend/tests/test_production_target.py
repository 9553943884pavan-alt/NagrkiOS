"""Offline production migration safety checks with dummy credentials only."""
from __future__ import annotations

import os
import runpy
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_production_target import (
    PROJECT_ID, PRODUCTION_BRANCH_ID, PRODUCTION_DIRECT_HOST,
    TESTING_DIRECT_HOST, check_admin_target, check_backup, check_target, read_only_empty_preflight,
    verify_neon_branches,
)


BACKEND = Path(__file__).resolve().parents[1]
WORKFLOW = BACKEND.parent / '.github/workflows/migrate-neon-production.yml'


def dummy_env():
    direct = f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST}/dummy_db?sslmode=require'
    return {
        'NAGRIKOS_MIGRATION_TARGET': 'production',
        'NEON_PRODUCTION_PROJECT_ID': PROJECT_ID,
        'NEON_PRODUCTION_BRANCH_ID': PRODUCTION_BRANCH_ID,
        'CONFIRMED_PRODUCTION_BRANCH_ID': PRODUCTION_BRANCH_ID,
        'NEON_PRODUCTION_DIRECT_HOST': PRODUCTION_DIRECT_HOST,
        'NEON_TESTING_DIRECT_HOST': TESTING_DIRECT_HOST,
        'DIRECT_URL': direct,
        'DATABASE_URL': direct.replace(PRODUCTION_DIRECT_HOST,
                                      PRODUCTION_DIRECT_HOST.replace('.', '-pooler.', 1)),
        'NEON_PRODUCTION_BACKUP_BRANCH_ID': 'br-independent-backup-123',
        'CONFIRMED_PRODUCTION_BACKUP_BRANCH_ID': 'br-independent-backup-123',
        'NEON_API_KEY': 'dummy_api_key',
    }


def admin_env():
    env = dummy_env()
    env['DIRECT_URL'] = env['DIRECT_URL'].replace('dummy_role', 'neondb_owner').replace('/dummy_db', '/neondb')
    env['DATABASE_URL'] = env['DATABASE_URL'].replace('dummy_role', 'neondb_owner').replace('/dummy_db', '/neondb')
    return {**env, 'NAGRIKOS_ADMIN_TARGET': 'production'}


def test_admin_guard_is_offline_and_pins_both_production_endpoints():
    check_admin_target(admin_env())
    check_admin_target(admin_env(), require_direct=True)
    pooled_only = admin_env()
    pooled_only.pop('DIRECT_URL')
    check_admin_target(pooled_only)
    with pytest.raises(RuntimeError):
        check_admin_target(pooled_only, require_direct=True)


@pytest.mark.parametrize('name,value', [
    ('NAGRIKOS_ADMIN_TARGET', 'testing'),
    ('NEON_PRODUCTION_PROJECT_ID', 'cold-violet-69814991'),
    ('NEON_PRODUCTION_BRANCH_ID', 'br-hidden-smoke-a7qqswi1'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DIRECT_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST}/dummy_db?sslmode=require'),
    ('DIRECT_URL', f'postgresql://dummy_role:other_password@{PRODUCTION_DIRECT_HOST}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=disable'),
    ('DATABASE_URL', f'postgresql://neondb_owner:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/wrong_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://wrong_role:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/neondb?sslmode=require'),
])
def test_admin_guard_rejects_testing_mixed_or_insecure_targets(name, value):
    env = admin_env()
    env[name] = value
    with pytest.raises(RuntimeError):
        check_admin_target(env, require_direct=True)


def test_admin_write_entrypoints_guard_before_database(monkeypatch):
    from scripts import disable_demo_credentials, provision_admin

    monkeypatch.setenv('NAGRIKOS_MODE', 'public')
    monkeypatch.delenv('NAGRIKOS_ADMIN_TARGET', raising=False)
    monkeypatch.setattr(sys, 'argv', ['provision_admin.py', '--email', 'admin@example.org', '--name', 'Admin'])
    monkeypatch.setattr(provision_admin, 'initialize', lambda: pytest.fail('database opened before guard'))
    monkeypatch.setattr(disable_demo_credentials, 'urls', lambda: pytest.fail('database target parsed before guard'))
    with pytest.raises(RuntimeError, match='Admin target'):
        provision_admin.main()
    with pytest.raises(RuntimeError, match='Admin target'):
        disable_demo_credentials.main()


def test_remaining_admin_workflow_is_manual_protected_and_target_pinned():
    for name in ('disable-neon-demo.yml',):
        source = (BACKEND.parent / '.github/workflows' / name).read_text(encoding='utf-8')
        assert 'workflow_dispatch:' in source
        assert "if: github.ref == 'refs/heads/main'" in source
        assert 'environment: neon-admin' in source
        assert 'group: neon-production-admin' in source
        assert 'NAGRIKOS_ADMIN_TARGET: production' in source
        assert 'NEON_PRODUCTION_PROJECT_ID: winter-meadow-40329605' in source
        assert 'NEON_PRODUCTION_BRANCH_ID: br-super-glitter-a769u0u1' in source
        assert 'permissions:\n  contents: read' in source


def test_one_time_admin_workflow_and_secret_references_are_retired():
    workflow_dir = BACKEND.parent / '.github/workflows'
    assert not (workflow_dir / 'provision-admin.yml').exists()
    for path in workflow_dir.glob('*.yml'):
        source = path.read_text(encoding='utf-8')
        assert 'BOOTSTRAP_ADMIN_' not in source


def test_valid_production_pair_is_offline_only():
    result = check_target(dummy_env())
    assert result['project_id'] == PROJECT_ID
    assert result['branch_id'] == PRODUCTION_BRANCH_ID
    check_backup(dummy_env())


@pytest.mark.parametrize('missing', [
    'NAGRIKOS_MIGRATION_TARGET', 'NEON_PRODUCTION_PROJECT_ID',
    'NEON_PRODUCTION_BRANCH_ID', 'CONFIRMED_PRODUCTION_BRANCH_ID',
    'NEON_PRODUCTION_DIRECT_HOST', 'NEON_TESTING_DIRECT_HOST',
    'DIRECT_URL', 'DATABASE_URL',
])
def test_missing_production_configuration_fails_closed(missing):
    env = dummy_env()
    env.pop(missing)
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('name,value', [
    ('NAGRIKOS_MIGRATION_TARGET', 'testing'),
    ('NEON_PRODUCTION_PROJECT_ID', 'cold-violet-69814991'),
    ('NEON_PRODUCTION_BRANCH_ID', 'br-hidden-smoke-a7qqswi1'),
    ('CONFIRMED_PRODUCTION_BRANCH_ID', 'br-hidden-smoke-a7qqswi1'),
    ('NEON_PRODUCTION_DIRECT_HOST', TESTING_DIRECT_HOST),
    ('NEON_TESTING_DIRECT_HOST', PRODUCTION_DIRECT_HOST),
    ('DIRECT_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://other_role:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:other_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/other_db?sslmode=require'),
])
def test_mixed_or_nonproduction_target_is_rejected(name, value):
    env = dummy_env()
    env[name] = value
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('bad', [
    '', 'postgresql://',
    'postgresql://dummy_role@HOST/dummy_db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=disable',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require&sslmode=disable',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require&options=unsafe',
    'postgresql://dummy_role:dummy_password@HOST:bad/dummy_db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require#fragment',
])
def test_malformed_or_insecure_direct_url_is_rejected(bad):
    env = dummy_env()
    env['DIRECT_URL'] = bad.replace('HOST', PRODUCTION_DIRECT_HOST)
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('backup,confirmed', [
    ('', ''), ('br-independent-backup-123', ''),
    ('br-independent-backup-123', 'br-different'),
    ('br-super-glitter-a769u0u1', 'br-super-glitter-a769u0u1'),
    ('br-hidden-smoke-a7qqswi1', 'br-hidden-smoke-a7qqswi1'),
    ('br-damp-mode-a744dvau', 'br-damp-mode-a744dvau'),
    ('not-a-branch', 'not-a-branch'),
])
def test_backup_id_must_be_independent_and_secret_confirmed(backup, confirmed):
    env = dummy_env()
    env['NEON_PRODUCTION_BACKUP_BRANCH_ID'] = backup
    env['CONFIRMED_PRODUCTION_BACKUP_BRANCH_ID'] = confirmed
    with pytest.raises(RuntimeError):
        check_backup(env)


class FakeApiResponse:
    status = 200
    def __init__(self, branch): self.branch = branch
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, _limit):
        import json
        return json.dumps({'branch': self.branch}).encode()


@pytest.mark.parametrize('changed', [
    {}, {'backup_parent': 'br-hidden-smoke-a7qqswi1'},
    {'backup_state': 'creating'}, {'backup_project': 'cold-violet-69814991'},
    {'production_name': 'testing'}, {'production_state': 'creating'},
    {'backup_pending': 'deleting'},
])
def test_neon_api_independently_checks_backup_and_production(changed):
    production = {'id': PRODUCTION_BRANCH_ID, 'project_id': PROJECT_ID,
                  'name': changed.get('production_name', 'production'),
                  'current_state': changed.get('production_state', 'ready'),
                  'pending_state': None}
    backup = {'id': 'br-independent-backup-123',
              'project_id': changed.get('backup_project', PROJECT_ID),
              'parent_id': changed.get('backup_parent', PRODUCTION_BRANCH_ID),
              'current_state': changed.get('backup_state', 'ready'),
              'pending_state': changed.get('backup_pending')}
    calls = []
    def opener(request, timeout):
        assert timeout == 10 and request.get_method() == 'GET'
        assert request.get_header('Authorization') == 'Bearer dummy_api_key'
        calls.append(request.full_url)
        return FakeApiResponse(production if len(calls) == 1 else backup)
    if changed:
        with pytest.raises(RuntimeError):
            verify_neon_branches(dummy_env(), opener=opener)
    else:
        verify_neon_branches(dummy_env(), opener=opener)
    assert all(url.startswith(f'https://console.neon.tech/api/v2/projects/{PROJECT_ID}/branches/')
               for url in calls)


def test_neon_api_missing_key_fails_before_network():
    env = dummy_env()
    env.pop('NEON_API_KEY')
    with pytest.raises(RuntimeError):
        verify_neon_branches(env, opener=lambda *_: pytest.fail('unexpected network call'))


def test_guard_module_entrypoint_runs_offline_with_dummy_urls():
    result = subprocess.run(
        [sys.executable, '-m', 'scripts.check_production_target', '--require-backup'],
        cwd=BACKEND, env={**os.environ, **dummy_env()},
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert 'preflight PASSED' in result.stdout
    assert 'dummy_password' not in result.stdout + result.stderr


class FakeResult:
    def __init__(self, value): self.value = value
    def scalar_one(self): return self.value


class FakeConnection:
    def __init__(self, version, tables):
        self.version = version
        self.tables = tables
        self.statements = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def exec_driver_sql(self, statement):
        self.statements.append(statement)
        if statement == 'SHOW server_version_num':
            return FakeResult(self.version)
        if 'FROM pg_class' in statement:
            return FakeResult(self.tables)
        return FakeResult(None)
    def rollback(self): self.statements.append('ROLLBACK')


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.disposed = False
    def connect(self): return self.connection
    def dispose(self): self.disposed = True


@pytest.mark.parametrize('version,tables,passes', [
    ('180007', 0, True), ('170012', 0, False), ('180007', 1, False),
])
def test_read_only_empty_preflight_checks_version_and_occupancy(version, tables, passes):
    connection = FakeConnection(version, tables)
    engine = FakeEngine(connection)
    with patch('sqlalchemy.create_engine', return_value=engine):
        if passes:
            read_only_empty_preflight(dummy_env())
        else:
            with pytest.raises(RuntimeError):
                read_only_empty_preflight(dummy_env())
    assert connection.statements[0] == 'SET TRANSACTION READ ONLY'
    assert engine.disposed


def test_obsolete_initial_production_migration_workflow_is_excluded():
    assert not WORKFLOW.exists()
    migration_env = (BACKEND / 'migrations' / 'env.py').read_text(encoding='utf-8')
    assert "migration_target == 'testing'" in migration_env
    assert "migration_target == 'production'" in migration_env
    assert migration_env.index('check_production_target()') < migration_env.index('create_engine(')


def test_post_migration_verifier_accepts_expected_schema_without_network():
    from sqlalchemy import UniqueConstraint
    from app.models import metadata
    from scripts.verify_production_schema import verify

    class Results:
        def __init__(self, value): self.value = value
        def fetchall(self): return [(self.value,)]
        def scalar_one(self): return self.value

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def exec_driver_sql(self, sql):
            return Results('20261114_01' if 'version_num' in sql else 0)
        def rollback(self): pass

    class Inspector:
        def get_table_names(self, **_): return list(metadata.tables) + ['alembic_version']
        def get_columns(self, name): return [{'name': col.name} for col in metadata.tables[name].columns]
        def get_foreign_keys(self, name):
            return [{'constrained_columns': [element.parent.name for element in constraint.elements]}
                    for constraint in metadata.tables[name].foreign_key_constraints]
        def get_indexes(self, name): return [{'name': item.name} for item in metadata.tables[name].indexes]
        def get_unique_constraints(self, name):
            return [{'column_names': [column.name for column in constraint.columns]}
                    for constraint in metadata.tables[name].constraints
                    if isinstance(constraint, UniqueConstraint)]
        def get_pk_constraint(self, name):
            return {'constrained_columns': [col.name for col in metadata.tables[name].primary_key.columns]}

    engine = FakeEngine(Connection())
    with patch('scripts.verify_production_schema.inspect', return_value=Inspector()):
        result = verify(dummy_env(), engine_factory=lambda _url: engine)
    assert result == {'tables': 12, 'foreign_keys': 13, 'explicit_indexes': 10}
    assert engine.disposed


def test_frozen_initial_revision_matches_current_model_shape_offline():
    from app.models import metadata

    revision = runpy.run_path(str(BACKEND / 'migrations/versions/20261114_01_initial.py'))
    assert revision['revision'] == '20261114_01' and revision['down_revision'] is None
    database = sqlite3.connect(':memory:')
    try:
        for statement in revision['SCHEMA_SQL']:
            database.execute(statement)
        tables = {row[0] for row in database.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert tables == set(metadata.tables)
        for name, table in metadata.tables.items():
            columns = {row[1] for row in database.execute(f'PRAGMA table_info({name})')}
            assert columns == set(table.columns.keys())
            foreign_keys = list(database.execute(f'PRAGMA foreign_key_list({name})'))
            assert len(foreign_keys) == len(table.foreign_keys)
            indexes = {row[1] for row in database.execute(f'PRAGMA index_list({name})')}
            assert {index.name for index in table.indexes} <= indexes
    finally:
        database.close()


