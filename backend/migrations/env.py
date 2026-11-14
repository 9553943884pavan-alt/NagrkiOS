"""Alembic configuration. Schema changes always use the direct connection."""
import os
from logging.config import fileConfig
from urllib.parse import parse_qs, urlsplit

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import metadata

config = context.config
target_metadata = metadata


def direct_url():
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
