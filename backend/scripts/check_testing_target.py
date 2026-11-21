"""Offline guard for this project's verified Neon testing migration target.

The pinned identifiers come from the owner's Neon audit. This script never
connects to Neon and cannot establish whether the backup is still READY.
"""
from __future__ import annotations

import argparse
import os
import re
from urllib.parse import parse_qs, unquote, urlsplit


TESTING_BRANCH_ID = 'br-hidden-smoke-a7qqswi1'
TESTING_DIRECT_HOST = 'ep-curly-term-a7dqknkk.ap-southeast-2.aws.neon.tech'
PRODUCTION_DIRECT_HOST = 'ep-frosty-union-a7d7vufy.ap-southeast-2.aws.neon.tech'
BACKUP_BRANCH_ID = 'br-damp-mode-a744dvau'


def _url(value: str, name: str):
    if not value or value != value.strip():
        raise RuntimeError(f'{name} must be a complete PostgreSQL URL')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise RuntimeError(f'{name} is malformed') from exc
    if (parsed.scheme not in {'postgresql', 'postgresql+psycopg'} or
            not parsed.hostname or not parsed.username or not parsed.password or
            port not in (None, 5432) or parsed.fragment or
            not re.fullmatch(r'/[A-Za-z0-9_][A-Za-z0-9_.-]*', parsed.path) or
            not unquote(parsed.username).strip() or not unquote(parsed.password) or
            set(query) - {'sslmode', 'channel_binding'} or
            query.get('sslmode') not in (['require'], ['verify-ca'], ['verify-full']) or
            ('channel_binding' in query and query['channel_binding'] != ['require'])):
        raise RuntimeError(f'{name} must contain a role, password, database and explicit TLS')
    return parsed


def check_target(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    if env.get('NEON_TESTING_BRANCH_ID') != TESTING_BRANCH_ID:
        raise RuntimeError('Testing branch ID does not match the verified branch')
    if env.get('NEON_TESTING_DIRECT_HOST') != TESTING_DIRECT_HOST:
        raise RuntimeError('Testing direct host does not match the verified branch')
    if env.get('NEON_PRODUCTION_DIRECT_HOST') != PRODUCTION_DIRECT_HOST:
        raise RuntimeError('Production direct host does not match the verified branch')
    direct = _url(env.get('DIRECT_URL', ''), 'DIRECT_URL')
    pooled = _url(env.get('DATABASE_URL', ''), 'DATABASE_URL')
    if direct.hostname != TESTING_DIRECT_HOST:
        raise RuntimeError('DIRECT_URL does not match the verified testing direct host')
    if pooled.hostname != TESTING_DIRECT_HOST.replace('.', '-pooler.', 1):
        raise RuntimeError('DATABASE_URL does not match the testing pooled endpoint')
    if (direct.path != pooled.path or direct.username != pooled.username or
            direct.password != pooled.password):
        raise RuntimeError('Testing URLs must use the same database, role and password')
    return {'direct_host': TESTING_DIRECT_HOST, 'pooled_host': pooled.hostname,
            'database': direct.path.lstrip('/')}


def check_backup(environ: dict[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    if env.get('NEON_BACKUP_BRANCH_ID') != BACKUP_BRANCH_ID:
        raise RuntimeError('Backup branch ID does not match the verified pre-migration backup')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Offline Neon testing migration guard')
    parser.add_argument('--require-backup', action='store_true')
    args = parser.parse_args()
    check_target()
    if args.require_backup:
        check_backup()
    print('Testing target guard passed; confirm current Neon branch and backup state before any write')
