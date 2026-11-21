"""Local, read-only preflight for the approved Sydney/Singapore testing pair.

Reads backend/.env without printing its values. It does not connect to either
Neon project or modify the file. Bucket privacy and credential scope require
separate verification through Neon Console/API before any live write.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values

from app import object_storage
from scripts.check_testing_target import check_target


REQUIRED = (
    'DATABASE_URL', 'DIRECT_URL', 'NEON_TESTING_DIRECT_HOST',
    'NEON_PRODUCTION_DIRECT_HOST', 'NEON_TESTING_BRANCH_ID',
    'AWS_ENDPOINT_URL_S3', 'AWS_REGION', 'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
)


def preflight(path: Path | None = None, live_read: bool = False) -> dict[str, bool]:
    env_path = path or Path(__file__).resolve().parents[1] / '.env'
    if not env_path.is_file():
        raise RuntimeError('backend/.env is missing')
    values = {key: value for key, value in dotenv_values(env_path).items() if value is not None}
    if any(not values.get(name) for name in REQUIRED):
        raise RuntimeError('Required testing configuration is incomplete')
    check_target(values)
    if values.get('OBJECT_STORAGE_BACKEND') not in (None, '', 'neon'):
        raise RuntimeError('Storage backend conflicts with the approved Neon target')
    if values.get('OBJECT_STORAGE_BUCKET') not in (None, '', 'nagrikos-attachments'):
        raise RuntimeError('Storage bucket conflicts with the approved testing bucket')
    with patch.dict(os.environ, {**values, 'OBJECT_STORAGE_BACKEND': 'neon',
                                 'OBJECT_STORAGE_BUCKET': 'nagrikos-attachments'}, clear=True):
        object_storage.validate_config()
        if live_read:
            print('testing_target_configuration: PASS')
            from app.postgres import engine_for

            try:
                engine = engine_for(values['DATABASE_URL'])
                try:
                    with engine.connect() as connection:
                        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                        revision = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
                        if revision != '20261114_01':
                            raise RuntimeError('Unexpected testing database schema revision')
                        connection.rollback()
                finally:
                    engine.dispose()
            except Exception as exc:
                state = getattr(getattr(exc, 'orig', None), 'sqlstate', None)
                print(f'sydney_schema_read: FAIL ({type(exc).__name__}, sqlstate={state or "none"})')
                raise
            print('sydney_schema_read: PASS')
            # MaxKeys=0 authenticates against the exact bucket without returning
            # any existing object names or bytes. This is not a privacy check.
            try:
                result = object_storage._client().list_objects_v2(
                    Bucket='nagrikos-attachments', MaxKeys=0)
                if result.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
                    raise RuntimeError('Testing bucket read-only authentication failed')
            except Exception as exc:
                print(f'singapore_bucket_read: FAIL ({type(exc).__name__})')
                raise
            print('singapore_bucket_read: PASS')
    return {
        'backend_env_present': True,
        'root_env_present': (env_path.parent.parent / '.env').is_file(),
        'testing_db_guard': True,
        'testing_storage_config': True,
        'backend_selector_in_file': bool(values.get('OBJECT_STORAGE_BACKEND')),
        'bucket_in_file': bool(values.get('OBJECT_STORAGE_BUCKET')),
        **({'sydney_schema_read': True, 'singapore_bucket_read': True} if live_read else {}),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-read', action='store_true')
    args = parser.parse_args()
    try:
        results = preflight(live_read=args.live_read)
    except Exception:
        # Error text from parsing libraries may contain secret input. Print only
        # a fixed message; the operator can inspect the local .env separately.
        print('Testing configuration preflight: FAIL')
        raise SystemExit(1) from None
    for name, result in results.items():
        print(f'{name}: {"PASS" if result else "NO"}')
    print('Bucket privacy and credential scope: NOT VERIFIED by this offline check')
