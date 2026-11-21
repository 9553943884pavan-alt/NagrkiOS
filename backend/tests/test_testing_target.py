"""Offline Neon migration safety checks with dummy credentials only."""
from __future__ import annotations

import os
import runpy
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.models import metadata
from scripts.check_testing_target import (
    BACKUP_BRANCH_ID, PRODUCTION_DIRECT_HOST, TESTING_BRANCH_ID,
    TESTING_DIRECT_HOST, check_backup, check_target,
)


BACKEND = Path(__file__).resolve().parents[1]
WORKFLOW = BACKEND.parent / '.github' / 'workflows' / 'migrate-neon.yml'
SECRETS = {'DIRECT_URL', 'DATABASE_URL', 'NEON_TESTING_DIRECT_HOST',
           'NEON_PRODUCTION_DIRECT_HOST', 'NEON_TESTING_BRANCH_ID'}


def urls():
    return {
        'NEON_TESTING_BRANCH_ID': TESTING_BRANCH_ID,
        'NEON_TESTING_DIRECT_HOST': TESTING_DIRECT_HOST,
        'NEON_PRODUCTION_DIRECT_HOST': PRODUCTION_DIRECT_HOST,
        'DIRECT_URL': f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST}/dummy_db?sslmode=require',
        'DATABASE_URL': f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require',
        'NEON_BACKUP_BRANCH_ID': BACKUP_BRANCH_ID,
    }


def test_verified_testing_pair_passes_without_network():
    result = check_target(urls())
    assert result == {'direct_host': TESTING_DIRECT_HOST,
                      'pooled_host': TESTING_DIRECT_HOST.replace('.', '-pooler.', 1),
                      'database': 'dummy_db'}
    check_backup(urls())


@pytest.mark.parametrize('missing', sorted(SECRETS))
def test_missing_environment_secret_fails_closed(missing):
    env = urls()
    env.pop(missing)
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('field,value', [
    ('NEON_TESTING_BRANCH_ID', 'br-super-glitter-a769u0u1'),
    ('NEON_TESTING_BRANCH_ID', 'br-wrong-branch'),
    ('NEON_TESTING_DIRECT_HOST', PRODUCTION_DIRECT_HOST),
    ('NEON_PRODUCTION_DIRECT_HOST', TESTING_DIRECT_HOST),
    ('DIRECT_URL', f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DIRECT_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://other_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:other_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy_db?sslmode=require'),
    ('DATABASE_URL', f'postgresql://dummy_role:dummy_password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/other_db?sslmode=require'),
])
def test_wrong_branch_or_pair_is_rejected(field, value):
    env = urls()
    env[field] = value
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('bad_url', [
    '', 'postgresql://', 'postgresql://dummy_role@HOST/dummy_db?sslmode=require',
    'postgresql://:dummy_password@HOST/dummy_db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/dummy/db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=disable',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require&sslmode=disable',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require&options=unsafe',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require#fragment',
    'postgresql://dummy_role:dummy_password@HOST:bad/dummy_db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST:6432/dummy_db?sslmode=require',
    'http://dummy_role:dummy_password@HOST/dummy_db?sslmode=require',
])
def test_malformed_direct_url_is_rejected(bad_url):
    env = urls()
    env['DIRECT_URL'] = bad_url.replace('HOST', TESTING_DIRECT_HOST)
    with pytest.raises(RuntimeError):
        check_target(env)


@pytest.mark.parametrize('bad_url', [
    '', 'postgresql://dummy_role@HOST/dummy_db?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/?sslmode=require',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=disable',
    'postgresql://dummy_role:dummy_password@HOST/dummy_db?sslmode=require&sslmode=require',
])
def test_malformed_pooled_url_is_rejected(bad_url):
    env = urls()
    env['DATABASE_URL'] = bad_url.replace('HOST', TESTING_DIRECT_HOST.replace('.', '-pooler.', 1))
    with pytest.raises(RuntimeError):
        check_target(env)


def test_backup_identifier_is_required_for_workflow_guard():
    env = urls()
    env.pop('NEON_BACKUP_BRANCH_ID')
    with pytest.raises(RuntimeError):
        check_backup(env)
    env['NEON_BACKUP_BRANCH_ID'] = 'br-wrong-backup'
    with pytest.raises(RuntimeError):
        check_backup(env)


def test_cli_guard_accepts_dummy_urls_and_rejects_bad_branch():
    env = urls()
    result = subprocess.run([sys.executable, 'scripts/check_testing_target.py', '--require-backup'],
                            cwd=BACKEND, env={**os.environ, **env}, capture_output=True, text=True)
    assert result.returncode == 0
    env['NEON_TESTING_BRANCH_ID'] = 'br-wrong-branch'
    result = subprocess.run([sys.executable, 'scripts/check_testing_target.py', '--require-backup'],
                            cwd=BACKEND, env={**os.environ, **env}, capture_output=True, text=True)
    assert result.returncode != 0


def test_workflow_secret_names_environment_and_guard_order():
    source = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: neon-schema' in source
    assert "if: github.ref == 'refs/heads/main'" in source
    assert 'shell: bash' in source
    assert 'backup_branch_id:' in source and 'required: true' in source
    for name in SECRETS:
        assert '${{ secrets.' + name + ' }}' in source
    run = source.split('        run: |', 1)[1]
    assert run.index('set -euo pipefail') < run.index('python scripts/check_testing_target.py --require-backup')
    assert run.index('python scripts/check_testing_target.py --require-backup') < run.index('alembic upgrade head')
    assert 'CONFIRMED_TESTING_BRANCH_ID' in run


@pytest.mark.skipif(os.name == 'nt', reason='Exercise the Bash workflow on Linux CI or WSL')
def test_workflow_shell_never_reaches_alembic_when_guard_fails(tmp_path):
    source = WORKFLOW.read_text(encoding='utf-8')
    shell_script = textwrap.dedent(source.split('        run: |', 1)[1])
    fake_alembic = tmp_path / 'alembic'
    fake_alembic.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MIGRATION_MARKER"\n',
                            encoding='utf-8')
    fake_alembic.chmod(0o700)
    marker = tmp_path / 'alembic-called'
    cases = [
        ({}, True),
        ({'NEON_TESTING_BRANCH_ID': 'br-wrong-branch'}, False),
        ({'CONFIRMED_TESTING_BRANCH_ID': 'br-wrong-branch'}, False),
        ({'DIRECT_URL': f'postgresql://dummy_role:dummy_password@{PRODUCTION_DIRECT_HOST}/dummy_db?sslmode=require'}, False),
        ({'DIRECT_URL': f'postgresql://dummy_role@{TESTING_DIRECT_HOST}/dummy_db?sslmode=require'}, False),
        ({'NEON_BACKUP_BRANCH_ID': 'br-wrong-backup'}, False),
        ({'NEON_BACKUP_BRANCH_ID': ''}, False),
    ]
    for overrides, should_reach_alembic in cases:
        marker.unlink(missing_ok=True)
        env = {**os.environ, **urls(),
               'CONFIRMED_TESTING_BRANCH_ID': TESTING_BRANCH_ID,
               'MIGRATION_MARKER': str(marker),
               'PATH': str(tmp_path) + os.pathsep + os.environ.get('PATH', '')}
        env.update(overrides)
        result = subprocess.run(['bash', '-c', shell_script], cwd=BACKEND,
                                env=env, capture_output=True, text=True)
        assert (result.returncode == 0) == should_reach_alembic
        assert marker.exists() == should_reach_alembic
        if should_reach_alembic:
            assert marker.read_text(encoding='utf-8').splitlines() == ['upgrade head', 'current']


def test_initial_alembic_revision_and_twelve_tables_match_models():
    revisions = list((BACKEND / 'migrations' / 'versions').glob('*.py'))
    assert len(revisions) == 1
    revision = runpy.run_path(str(revisions[0]))
    assert revision['revision'] == '20261114_01'
    assert revision['down_revision'] is None
    tables = {statement.split('CREATE TABLE ', 1)[1].split(' ', 1)[0]
              for statement in revision['SCHEMA_SQL'] if 'CREATE TABLE ' in statement}
    assert len(tables) == 12 and tables == set(metadata.tables)
    required = (BACKEND / 'requirements.txt').read_text(encoding='utf-8')
    for dependency in ('SQLAlchemy>=2.0,<3', 'psycopg[binary]>=3.2,<4', 'alembic>=1.14,<2'):
        assert dependency in required
    workflow = WORKFLOW.read_text(encoding='utf-8')
    assert "'SQLAlchemy>=2.0,<3' 'psycopg[binary]>=3.2,<4' 'alembic>=1.14,<2'" in workflow
    alembic_ini = (BACKEND / 'alembic.ini').read_text(encoding='utf-8')
    assert 'script_location = migrations' in alembic_ini
    assert 'prepend_sys_path = .' in alembic_ini
    environment = (BACKEND / 'migrations' / 'env.py').read_text(encoding='utf-8')
    assert environment.index('check_target()') < environment.index('engine = create_engine(')
    assert 'poolclass=pool.NullPool' in environment
