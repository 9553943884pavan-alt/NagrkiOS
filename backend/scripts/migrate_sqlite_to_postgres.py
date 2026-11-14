"""Copy an SQLite snapshot to an empty, migrated PostgreSQL development branch.

Stop all writers before using this for a cutover. The source database is never edited.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.auth import decrypt_totp  # noqa: E402
from app.db import DEFAULT_DB, initialize  # noqa: E402
from app.models import metadata  # noqa: E402

REVISION = '20261114_01'


def urls():
    direct = os.getenv('DIRECT_URL', '').strip()
    pooled = os.getenv('DATABASE_URL', '').strip()
    a, b = urlsplit(direct), urlsplit(pooled)
    if a.scheme not in {'postgresql', 'postgresql+psycopg'} or b.scheme not in {'postgresql', 'postgresql+psycopg'}:
        raise RuntimeError('Set DIRECT_URL and DATABASE_URL to PostgreSQL URLs')
    if not a.hostname or not b.hostname or '-pooler.' in a.hostname or b.hostname != a.hostname.replace('.', '-pooler.', 1):
        raise RuntimeError('DIRECT_URL and DATABASE_URL must point to the same Neon branch (direct and pooled hosts)')
    if a.path != b.path or a.username != b.username:
        raise RuntimeError('DIRECT_URL and DATABASE_URL must use the same database and role')
    for url in (a, b):
        if parse_qs(url.query).get('sslmode', ['require'])[-1] not in {'require', 'verify-ca', 'verify-full'}:
            raise RuntimeError('Both PostgreSQL connections must require TLS')
    mode = parse_qs(a.query).get('sslmode', ['require'])[-1]
    return direct.replace('postgresql://', 'postgresql+psycopg://', 1), mode


def snapshot(source: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = source.with_name(f'{source.stem}.pre-postgres.{stamp}.db')
    if backup.exists():
        raise RuntimeError('Timestamped SQLite backup already exists; retry in one second')
    with sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True) as old, sqlite3.connect(backup) as copy:
        old.backup(copy)
    with sqlite3.connect(backup) as copy:
        if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite snapshot failed integrity_check')
        if copy.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise RuntimeError('SQLite snapshot contains broken relationships')
    return backup


def upgrade_snapshot(backup: Path) -> None:
    original = {name: os.environ.get(name) for name in ('DATABASE_URL', 'DATABASE_PATH', 'NAGRIKOS_MODE')}
    try:
        os.environ.pop('DATABASE_URL', None)
        os.environ['DATABASE_PATH'] = str(backup)
        os.environ['NAGRIKOS_MODE'] = 'public'  # Never seed a blank snapshot.
        initialize()
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def source_rows(db, table):
    cols = [column.name for column in table.columns]
    actual = {row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')}
    if set(cols) != actual:
        raise RuntimeError(f'Unexpected SQLite schema for {table.name}; stop and inspect the backup')
    query = f'SELECT {", ".join(chr(34) + col + chr(34) for col in cols)} FROM "{table.name}"'
    return [dict(zip(cols, row)) for row in db.execute(query)]


def comparable(rows, table):
    cols = [column.name for column in table.columns]
    return sorted(json.dumps({col: row[col] for col in cols}, sort_keys=True,
                             separators=(',', ':'), ensure_ascii=False, default=str)
                  for row in rows)


def verify_mfa(rows):
    # The production key must be the SAME persistent key that encrypted the
    # SQLite values. A wrong or missing key stops the migration before writes.
    if not os.getenv('NAGRIKOS_TOTP_KEY', '').strip():
        if any(row['mfa_secret'] or row['mfa_pending'] for row in rows):
            raise RuntimeError('Set NAGRIKOS_TOTP_KEY to the existing SQLite MFA key before migrating')
        return
    for row in rows:
        for name in ('mfa_secret', 'mfa_pending'):
            if row[name]:
                try:
                    decrypt_totp(row[name])
                except Exception as exc:
                    raise RuntimeError('Existing MFA values cannot be decrypted with NAGRIKOS_TOTP_KEY') from exc


def copy(backup: Path, direct: str, sslmode: str) -> dict[str, int]:
    engine = create_engine(direct, connect_args={'sslmode': sslmode}, poolclass=NullPool)
    try:
        with sqlite3.connect(backup) as sqlite:
            tables = list(metadata.sorted_tables)
            rows = {table.name: source_rows(sqlite, table) for table in tables}
            verify_mfa(rows['users'])
            counts = {name: len(values) for name, values in rows.items()}
            with engine.begin() as pg:
                version = pg.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
                if version != REVISION:
                    raise RuntimeError('Run Alembic upgrade head on the development branch first')
                existing = {table.name: pg.execute(select(func.count()).select_from(table)).scalar_one()
                            for table in tables}
                if any(existing.values()):
                    if existing != counts:
                        raise RuntimeError('PostgreSQL target is populated with different counts; no rows copied')
                    for table in tables:
                        target_rows = [dict(row._mapping) for row in pg.execute(select(table))]
                        if comparable(rows[table.name], table) != comparable(target_rows, table):
                            raise RuntimeError(f'PostgreSQL target differs in {table.name}; no rows copied')
                    return counts
                for table in tables:
                    values = rows[table.name]
                    for offset in range(0, len(values), 500):
                        pg.execute(table.insert(), values[offset:offset + 500])
                after = {table.name: pg.execute(select(func.count()).select_from(table)).scalar_one()
                         for table in tables}
                if after != counts:
                    raise RuntimeError('PostgreSQL count verification failed; transaction rolled back')
                for table in tables:
                    target_rows = [dict(row._mapping) for row in pg.execute(select(table))]
                    if comparable(rows[table.name], table) != comparable(target_rows, table):
                        raise RuntimeError(f'PostgreSQL row verification failed for {table.name}; transaction rolled back')
                for table in tables:
                    if 'id' in table.c and table.c.id.primary_key:
                        pg.execute(text('SELECT setval(pg_get_serial_sequence(:name, :column), '
                                        'GREATEST(COALESCE((SELECT max(id) FROM "' + table.name + '"), 0), 1), '
                                        ':has_rows)'), {'name': table.name, 'column': 'id',
                                                       'has_rows': bool(rows[table.name])})
                # Foreign keys are enforced on every insert. The transaction
                # commits only after counts and every row value match.
                return counts
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    source = args.database.resolve()
    if not source.is_file():
        parser.error('SQLite source database does not exist')
    direct, sslmode = urls()
    backup = snapshot(source)
    print(f'SQLite snapshot: {backup}')
    upgrade_snapshot(backup)
    counts = copy(backup, direct, sslmode)
    print(f'Verified table counts: {counts}')
    print('PostgreSQL copy committed; SQLite source and snapshot are unchanged')


if __name__ == '__main__':
    main()
