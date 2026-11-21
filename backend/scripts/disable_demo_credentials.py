"""Revoke demo login material on PostgreSQL without deleting linked case history.

Run only after live validation and after provisioning a non-demo administrator.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import (account_tokens, auth_challenges, recovery_codes, sessions,
                        users)  # noqa: E402
from scripts.check_production_target import check_admin_target  # noqa: E402
from scripts.migrate_sqlite_to_postgres import urls  # noqa: E402

DISABLED_HASH = '!disabled-demo-account'


def disable(connection) -> int:
    if not connection.execute(select(func.count()).select_from(users).where(
            users.c.role == 'admin', users.c.is_demo == 0)).scalar_one():
        raise RuntimeError('Provision a verified non-demo administrator before disabling demo credentials')
    ids = select(users.c.id).where(users.c.is_demo == 1)
    count = connection.execute(select(func.count()).select_from(users).where(users.c.is_demo == 1)).scalar_one()
    for table in (sessions, account_tokens, auth_challenges, recovery_codes):
        connection.execute(delete(table).where(table.c.user_id.in_(ids)))
    connection.execute(update(users).where(users.c.is_demo == 1).values(
        password_hash=DISABLED_HASH, mfa_secret=None, mfa_pending=None,
        mfa_pending_expires_at=None, mfa_pending_attempts=0))
    return count


def main():
    if os.getenv('NAGRIKOS_MODE') != 'public':
        raise RuntimeError('Demo credential cleanup requires public mode')
    check_admin_target(require_direct=True)
    direct, sslmode = urls()
    engine = create_engine(direct, connect_args={'sslmode': sslmode}, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            count = disable(connection)
        print(f'Disabled credentials for {count} demo identities; linked case and audit rows remain')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
