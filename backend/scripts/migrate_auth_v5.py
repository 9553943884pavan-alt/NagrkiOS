"""Back up an existing SQLite database, apply additive auth schema, verify data counts."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import DEFAULT_DB, initialize  # noqa: E402


def counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as db:
        return {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in ('users','sessions','complaints','notes','history','attachments')}


def preserved_old_columns(path: Path, backup: Path) -> bool:
    with sqlite3.connect(path) as current, sqlite3.connect(backup) as original:
        for table in ('users','sessions','complaints','notes','history','attachments'):
            columns=[row[1] for row in original.execute(f'PRAGMA table_info({table})')]
            projection=','.join('"'+name.replace('"','""')+'"' for name in columns)
            old_rows=original.execute(f'SELECT {projection} FROM {table} ORDER BY rowid').fetchall()
            new_rows=current.execute(f'SELECT {projection} FROM {table} ORDER BY rowid').fetchall()
            if old_rows != new_rows:
                return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    path = args.database.resolve()
    if not path.is_file():
        parser.error(f'Database does not exist: {path}')
    before = counts(path)
    suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = path.with_name(f'{path.stem}.pre-auth-v5.{suffix}.db')
    if backup.exists():
        parser.error(f'Backup exists: {backup}')
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    os.environ['DATABASE_PATH'] = str(path)
    initialize()
    after = counts(path)
    with sqlite3.connect(path) as db:
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    unchanged=preserved_old_columns(path,backup)
    if before != after or integrity != 'ok' or not unchanged:
        raise RuntimeError(f'Migration verification failed. Backup: {backup}; before={before}; after={after}; integrity={integrity}')
    print(f'Backup: {backup}')
    print(f'Preserved rows: {after}')
    print('SQLite integrity: ok')
    print('Existing row values: unchanged')


if __name__ == '__main__':
    main()
