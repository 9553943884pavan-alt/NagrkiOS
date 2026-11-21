"""Alembic configuration. Schema changes always use the direct connection."""
import os
from logging.config import fileConfig
from urllib.parse import parse_qs, urlsplit

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import metadata
from scripts.check_testing_target import check_target
from scripts.check_production_target import (
    check_target as check_production_target,
    check_backup as check_production_backup,
    verify_neon_branches,
)

config = context.config
target_metadata = metadata


def direct_url():
    # Protect direct Alembic invocations as well as the GitHub workflow.
    # An operator must update the pinned branch mapping after a verified
    # endpoint change before any migration can connect elsewhere.
    migration_target = os.environ.get('NAGRIKOS_MIGRATION_TARGET', 'testing')
    if migration_target == 'testing':
        check_target()
    elif migration_target == 'production':
        check_production_target()
        check_production_backup()
        verify_neon_branches()
    else:
        raise RuntimeError('Unknown Neon migration target')
    value = os.environ.get('DIRECT_URL', '').strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {'postgresql', 'postgresql+psycopg'} or not parsed.hostname:
        raise RuntimeError('DIRECT_URL must be a direct PostgreSQL connection URL')
    if '-pooler.' in parsed.hostname:
        raise RuntimeError('DIRECT_URL must not use the pooled endpoint')
    if parse_qs(parsed.query).get('sslmode', ['require'])[-1] not in {'require', 'verify-ca', 'verify-full'}:
        raise RuntimeError('DIRECT_URL must require TLS')
    return value.replace('postgresql://', 'postgresql+psycopg://', 1)


def run_migrations_online():
    value = direct_url()
    sslmode = parse_qs(urlsplit(value).query).get('sslmode', ['require'])[-1]
    engine = create_engine(value, connect_args={'sslmode': sslmode}, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
