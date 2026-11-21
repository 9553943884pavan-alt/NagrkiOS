"""Fail-closed offline guard for the owner's Sydney production migration target.

This guard does not connect to Neon. Backup parentage and READY status must be
checked independently in Neon Console/API before the manual workflow is run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.check_testing_target import _url


PROJECT_ID = 'winter-meadow-40329605'
PRODUCTION_BRANCH_ID = 'br-super-glitter-a769u0u1'
PRODUCTION_DIRECT_HOST = 'ep-frosty-union-a7d7vufy.ap-southeast-2.aws.neon.tech'
TESTING_DIRECT_HOST = 'ep-curly-term-a7dqknkk.ap-southeast-2.aws.neon.tech'
TESTING_BRANCH_ID = 'br-hidden-smoke-a7qqswi1'
TESTING_BACKUP_BRANCH_ID = 'br-damp-mode-a744dvau'


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def check_target(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    if env.get('NAGRIKOS_MIGRATION_TARGET') != 'production':
        raise RuntimeError('Explicit production migration mode is required')
    for key, expected in (
        ('NEON_PRODUCTION_PROJECT_ID', PROJECT_ID),
        ('NEON_PRODUCTION_BRANCH_ID', PRODUCTION_BRANCH_ID),
        ('CONFIRMED_PRODUCTION_BRANCH_ID', PRODUCTION_BRANCH_ID),
        ('NEON_PRODUCTION_DIRECT_HOST', PRODUCTION_DIRECT_HOST),
        ('NEON_TESTING_DIRECT_HOST', TESTING_DIRECT_HOST),
    ):
        if env.get(key) != expected:
            raise RuntimeError(f'{key} does not match the verified production target')
    direct = _url(env.get('DIRECT_URL', ''), 'DIRECT_URL')
    pooled = _url(env.get('DATABASE_URL', ''), 'DATABASE_URL')
    if direct.hostname != PRODUCTION_DIRECT_HOST:
        raise RuntimeError('DIRECT_URL does not use the verified production direct endpoint')
    if pooled.hostname != PRODUCTION_DIRECT_HOST.replace('.', '-pooler.', 1):
        raise RuntimeError('DATABASE_URL does not use the verified production pooled endpoint')
    if (direct.path != pooled.path or direct.username != pooled.username or
            direct.password != pooled.password):
        raise RuntimeError('Production URLs must use the same database, role and password')
    return {'project_id': PROJECT_ID, 'branch_id': PRODUCTION_BRANCH_ID,
            'direct_host': PRODUCTION_DIRECT_HOST, 'database': direct.path.lstrip('/')}


def check_admin_target(environ: dict[str, str] | None = None, *, require_direct: bool = False) -> None:
    """Pin manual admin writes to Sydney production without opening a connection."""
    env = os.environ if environ is None else environ
    if (env.get('NAGRIKOS_ADMIN_TARGET') != 'production' or
            env.get('NEON_PRODUCTION_PROJECT_ID') != PROJECT_ID or
            env.get('NEON_PRODUCTION_BRANCH_ID') != PRODUCTION_BRANCH_ID):
        raise RuntimeError('Admin target is not the approved Sydney production branch')
    try:
        pooled = _url(env.get('DATABASE_URL', ''), 'DATABASE_URL')
        if pooled.hostname != PRODUCTION_DIRECT_HOST.replace('.', '-pooler.', 1):
            raise RuntimeError('Admin DATABASE_URL is not the approved pooled endpoint')
        if pooled.path != '/neondb' or pooled.username != 'neondb_owner':
            raise RuntimeError('Admin DATABASE_URL is not the approved production database and role')
        if require_direct:
            direct = _url(env.get('DIRECT_URL', ''), 'DIRECT_URL')
            if (direct.hostname != PRODUCTION_DIRECT_HOST or
                    direct.path != pooled.path or direct.username != pooled.username or
                    direct.password != pooled.password):
                raise RuntimeError('Admin direct and pooled targets do not match production')
    except (RuntimeError, ValueError):
        raise RuntimeError('Admin target URL validation failed') from None


def check_backup(environ: dict[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    supplied = env.get('NEON_PRODUCTION_BACKUP_BRANCH_ID', '')
    confirmed = env.get('CONFIRMED_PRODUCTION_BACKUP_BRANCH_ID', '')
    if (not re.fullmatch(r'br-[A-Za-z0-9-]+', supplied) or supplied != confirmed or
            supplied in {PRODUCTION_BRANCH_ID, TESTING_BRANCH_ID, TESTING_BACKUP_BRANCH_ID}):
        raise RuntimeError('Production backup branch ID is missing, mismatched or unsafe')


def verify_neon_branches(environ: dict[str, str] | None = None, opener=None) -> None:
    """Read Neon metadata to establish backup parentage and both branch states."""
    env = os.environ if environ is None else environ
    check_target(env)
    check_backup(env)
    key = env.get('NEON_API_KEY', '')
    if not key or key != key.strip():
        raise RuntimeError('NEON_API_KEY is required for branch identity verification')
    open_request = build_opener(_NoRedirect).open if opener is None else opener

    def branch(branch_id: str) -> dict:
        request = Request(
            f'https://console.neon.tech/api/v2/projects/{PROJECT_ID}/branches/{branch_id}',
            headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
            method='GET',
        )
        try:
            with open_request(request, timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError('Neon branch metadata request failed')
                payload = json.loads(response.read(65537))
        except Exception:
            raise RuntimeError('Neon branch metadata request failed') from None
        value = payload.get('branch') if isinstance(payload, dict) else None
        if not isinstance(value, dict):
            raise RuntimeError('Neon branch metadata is malformed')
        if (value.get('id') != branch_id or value.get('project_id') != PROJECT_ID or
                value.get('current_state', '').lower() != 'ready' or
                value.get('pending_state') not in (None, '')):
            raise RuntimeError('Neon branch identity or state is unsafe')
        return value

    production = branch(PRODUCTION_BRANCH_ID)
    backup = branch(env['NEON_PRODUCTION_BACKUP_BRANCH_ID'])
    if production.get('name') != 'production' or backup.get('parent_id') != PRODUCTION_BRANCH_ID:
        raise RuntimeError('Production or backup branch parentage is unsafe')


def read_only_empty_preflight(environ: dict[str, str] | None = None) -> None:
    """Require PostgreSQL 18 and a wholly empty public schema before first DDL."""
    env = os.environ if environ is None else environ
    check_target(env)
    check_backup(env)
    from sqlalchemy import create_engine, pool

    url = env['DIRECT_URL'].replace('postgresql://', 'postgresql+psycopg://', 1)
    engine = create_engine(url, poolclass=pool.NullPool,
                           connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            version = connection.exec_driver_sql('SHOW server_version_num').scalar_one()
            if int(version) // 10000 != 18:
                raise RuntimeError('Production PostgreSQL version is not 18')
            public_objects = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')"
            ).scalar_one()
            if public_objects != 0:
                raise RuntimeError('Production public schema is not empty; stop before migration')
            connection.rollback()
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Guard the Neon production target')
    parser.add_argument('--require-backup', action='store_true')
    parser.add_argument('--live-read-empty', action='store_true')
    parser.add_argument('--verify-neon-branches', action='store_true')
    args = parser.parse_args()
    try:
        check_target()
        if args.require_backup or args.live_read_empty:
            check_backup()
        if args.verify_neon_branches:
            verify_neon_branches()
        if args.live_read_empty:
            read_only_empty_preflight()
    except Exception:
        # SQLAlchemy/driver exceptions can include connection strings. Keep
        # workflow output fixed and secret-free.
        print('Production target preflight FAILED')
        raise SystemExit(1) from None
    print('Production target preflight PASSED; backup READY and parentage need independent verification')
