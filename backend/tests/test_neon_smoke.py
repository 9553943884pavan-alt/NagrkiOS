"""Offline safety tests; use dummy URLs and never connect to Neon."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_testing_target import TESTING_BRANCH_ID, TESTING_DIRECT_HOST, PRODUCTION_DIRECT_HOST
from scripts import smoke_neon_testing as smoke


BACKEND = Path(__file__).resolve().parents[1]
WORKFLOW = BACKEND.parent / '.github/workflows/smoke-neon-testing.yml'


def dummy_env():
    return {
        'NEON_TESTING_BRANCH_ID': TESTING_BRANCH_ID,
        'NEON_TESTING_DIRECT_HOST': TESTING_DIRECT_HOST,
        'NEON_PRODUCTION_DIRECT_HOST': PRODUCTION_DIRECT_HOST,
        'DIRECT_URL': f'postgresql://dummy:password@{TESTING_DIRECT_HOST}/dummy?sslmode=require',
        'DATABASE_URL': f'postgresql://dummy:password@{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy?sslmode=require',
        'SMOKE_APPROVAL': 'RUN-TESTING-SMOKE',
    }


def test_invalid_target_never_constructs_engine():
    calls = []
    env = dummy_env()
    env['DIRECT_URL'] = env['DIRECT_URL'].replace(TESTING_DIRECT_HOST, PRODUCTION_DIRECT_HOST)
    with pytest.raises(RuntimeError):
        smoke.run_smoke(env, lambda url: calls.append(url))
    assert calls == []


def test_missing_approval_never_constructs_engine():
    calls = []
    env = dummy_env()
    env.pop('SMOKE_APPROVAL')
    with pytest.raises(smoke.SmokeFailure):
        smoke.run_smoke(env, lambda url: calls.append(url))
    assert calls == []


class FakeTransaction:
    def __init__(self):
        self.rolled_back = False
        self.committed = False

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True


class FakeConnection:
    def __init__(self):
        self.transactions = []
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def begin(self):
        tx = FakeTransaction()
        self.transactions.append(tx)
        return tx

    def begin_nested(self):
        return self.begin()

    def rollback(self):
        pass

    def exec_driver_sql(self, *_):
        class Result:
            def scalar_one(self):
                return 0
        return Result()


class FakeEngine:
    def __init__(self):
        self.connections = []
        self.disposed = False

    def connect(self):
        conn = FakeConnection()
        self.connections.append(conn)
        return conn

    def dispose(self):
        self.disposed = True


@pytest.mark.parametrize('fail', [False, True])
def test_outer_transaction_always_rolls_back_and_engines_close(fail):
    engines = [FakeEngine(), FakeEngine()]
    def factory(_url):
        return engines.pop(0)
    direct, pooled = engines[:]
    def exercise(_connection, _marker):
        if fail:
            raise smoke.SmokeFailure('synthetic failure')
    with patch.object(smoke, 'schema_and_counts', return_value={name: 0 for name in smoke.TABLES}), \
         patch.object(smoke, 'temporary_commit_and_rollback'), \
         patch.object(smoke, 'exercise_api', side_effect=exercise):
        if fail:
            with pytest.raises(smoke.SmokeFailure):
                smoke.run_smoke(dummy_env(), factory)
        else:
            smoke.run_smoke(dummy_env(), factory)
    assert pooled.connections[0].transactions[0].rolled_back
    assert direct.disposed and pooled.disposed


def test_adapter_never_commits_application_transaction():
    class Underlying:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.closes = 0
        def commit(self): self.commits += 1
        def rollback(self): self.rollbacks += 1
        def close(self): self.closes += 1
    underlying = Underlying()
    wrapper = smoke.RollbackOnlyAdapter(underlying)
    wrapper.commit()
    wrapper.rollback()
    wrapper.close()
    assert (underlying.commits, underlying.rollbacks, underlying.closes) == (0, 0, 0)


def test_direct_preflight_uses_unpooled_engine_not_application_pooler():
    import sqlalchemy
    from app import postgres

    direct, pooled = FakeEngine(), FakeEngine()
    env = dummy_env()
    with patch.object(sqlalchemy, 'create_engine', return_value=direct) as create_direct, \
         patch.object(postgres, 'engine_for', return_value=pooled) as create_pooled, \
         patch.object(smoke, 'schema_and_counts', return_value={name: 0 for name in smoke.TABLES}), \
         patch.object(smoke, 'temporary_commit_and_rollback'), \
         patch.object(smoke, 'exercise_api'):
        smoke.run_smoke(env)
    assert create_direct.call_count == 1
    assert env['DIRECT_URL'].split('@', 1)[1] in create_direct.call_args.args[0]
    create_pooled.assert_called_once_with(env['DATABASE_URL'])
    assert direct.disposed and pooled.disposed


def test_savepoint_commit_and_failure_rollback():
    connection = FakeConnection()
    connect = smoke.rollback_only_connect(connection)
    with connect() as adapter:
        adapter.commit()
    assert connection.transactions[0].committed
    with pytest.raises(smoke.SmokeFailure), connect():
        raise smoke.SmokeFailure('test')
    assert connection.transactions[1].rolled_back


def test_workflow_is_manual_protected_testing_only_and_never_migrates():
    source = WORKFLOW.read_text(encoding='utf-8')
    assert 'workflow_dispatch:' in source
    assert 'environment: neon-schema' in source
    assert "if: github.ref == 'refs/heads/main'" in source
    assert 'group: neon-schema-testing' in source
    assert 'permissions:\n  contents: read' in source
    assert 'alembic upgrade' not in source and 'alembic current' not in source
    assert 'smoke_neon_testing.py' in source
    run = source.split('        run: |', 1)[1]
    assert run.index('SMOKE_APPROVAL') < run.index('check_testing_target.py') < run.index('smoke_neon_testing.py')
    for name in ('DIRECT_URL', 'DATABASE_URL', 'NEON_TESTING_DIRECT_HOST',
                 'NEON_PRODUCTION_DIRECT_HOST', 'NEON_TESTING_BRANCH_ID'):
        assert '${{ secrets.' + name + ' }}' in source


@pytest.mark.skipif(os.name == 'nt', reason='Run Bash workflow gate in WSL/Linux')
def test_workflow_gate_stops_before_smoke_for_bad_target(tmp_path):
    source = WORKFLOW.read_text(encoding='utf-8')
    script = textwrap.dedent(source.split('        run: |', 1)[1])
    root = tmp_path / 'scripts'
    root.mkdir()
    (root / 'check_testing_target.py').write_text(
        "import os,sys\nsys.exit(0 if os.getenv('NEON_TESTING_BRANCH_ID') == '" + TESTING_BRANCH_ID + "' else 1)\n",
        encoding='utf-8')
    marker = tmp_path / 'smoke-ran'
    (root / 'smoke_neon_testing.py').write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n", encoding='utf-8')
    for changes in ({'SMOKE_APPROVAL': 'wrong'},
                    {'CONFIRMED_TESTING_BRANCH_ID': 'br-wrong'},
                    {'NEON_TESTING_BRANCH_ID': 'br-wrong'}):
        marker.unlink(missing_ok=True)
        env = {**os.environ, **dummy_env(), 'CONFIRMED_TESTING_BRANCH_ID': TESTING_BRANCH_ID,
               'SMOKE_APPROVAL': 'RUN-TESTING-SMOKE', **changes}
        result = subprocess.run(['bash', '-c', script], cwd=tmp_path, env=env,
                                capture_output=True, text=True)
        assert result.returncode != 0 and not marker.exists()
    env = {**os.environ, **dummy_env(), 'CONFIRMED_TESTING_BRANCH_ID': TESTING_BRANCH_ID,
           'SMOKE_APPROVAL': 'RUN-TESTING-SMOKE'}
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0 and marker.exists()
