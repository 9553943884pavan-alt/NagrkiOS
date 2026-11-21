"""Offline tests for the live storage harness; no Neon requests or real secrets."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_live_storage_preflight import preflight
from scripts.check_testing_target import TESTING_BRANCH_ID, TESTING_DIRECT_HOST, PRODUCTION_DIRECT_HOST
from scripts.run_live_storage_validation import object_absent


BACKEND = Path(__file__).resolve().parents[1]


def dummy_file(tmp_path: Path) -> Path:
    backend = tmp_path / 'backend'
    backend.mkdir()
    path = backend / '.env'
    path.write_text('\n'.join([
        f'NEON_TESTING_BRANCH_ID={TESTING_BRANCH_ID}',
        f'NEON_TESTING_DIRECT_HOST={TESTING_DIRECT_HOST}',
        f'NEON_PRODUCTION_DIRECT_HOST={PRODUCTION_DIRECT_HOST}',
        f'DIRECT_URL=postgresql://dummy:password@{TESTING_DIRECT_HOST}/dummy?sslmode=require',
        'DATABASE_URL=postgresql://dummy:password@'
        f'{TESTING_DIRECT_HOST.replace(".", "-pooler.", 1)}/dummy?sslmode=require',
        'AWS_ENDPOINT_URL_S3=https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech',
        'AWS_REGION=ap-southeast-1',
        'AWS_ACCESS_KEY_ID=dummy-access',
        'AWS_SECRET_ACCESS_KEY=dummy-secret',
    ]), encoding='utf-8')
    return path


def test_offline_preflight_accepts_only_approved_testing_pair(tmp_path):
    path = dummy_file(tmp_path)
    result = preflight(path)
    assert result['testing_db_guard'] and result['testing_storage_config']
    assert not result['backend_selector_in_file'] and not result['bucket_in_file']


def test_offline_preflight_rejects_production_and_missing_secret(tmp_path):
    path = dummy_file(tmp_path)
    content = path.read_text(encoding='utf-8')
    path.write_text(content.replace(TESTING_DIRECT_HOST, PRODUCTION_DIRECT_HOST), encoding='utf-8')
    with pytest.raises(RuntimeError):
        preflight(path)
    path.write_text(content.replace('AWS_SECRET_ACCESS_KEY=dummy-secret', 'AWS_SECRET_ACCESS_KEY='),
                    encoding='utf-8')
    with pytest.raises(RuntimeError):
        preflight(path)


def test_harness_requires_private_verification_before_env_or_network_access():
    result = subprocess.run([sys.executable, '-m', 'scripts.run_live_storage_validation'],
                            cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 2
    assert 'independent private-bucket confirmation required' in result.stdout
    assert 'AWS_' not in result.stdout and 'postgresql://' not in result.stdout


def test_object_absence_checks_only_exact_test_key():
    key = 'a' * 24 + '.png'
    class Store:
        def list_objects_v2(self, **kwargs):
            assert kwargs == {'Bucket': 'nagrikos-attachments', 'Prefix': key, 'MaxKeys': 1}
            return {'Contents': [{'Key': key + '-unrelated'}]}
    assert object_absent(Store(), 'nagrikos-attachments', key)
