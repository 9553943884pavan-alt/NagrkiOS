"""Local operator bootstrap for the first public administrator; password is never an argument."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.account import canonical, password_policy  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.db import connect, initialize  # noqa: E402
from app import postgres  # noqa: E402
from scripts.check_production_target import check_admin_target  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email')
    parser.add_argument('--name')
    args=parser.parse_args()
    if os.getenv('NAGRIKOS_MODE') != 'public':
        parser.error('Set NAGRIKOS_MODE=public before provisioning')
    check_admin_target()
    # Actions reads these from protected environment secrets. Keep them out of
    # process arguments, which can be visible to other processes on the runner.
    name=(args.name or os.getenv('BOOTSTRAP_ADMIN_NAME', '')).strip()
    if not 2<=len(name)<=100:
        parser.error('Name must be 2 to 100 characters')
    email=canonical(args.email or os.getenv('BOOTSTRAP_ADMIN_EMAIL', ''))
    # A one-time environment secret allows a manually triggered CI bootstrap.
    # Interactive local provisioning still confirms the password twice.
    password=os.getenv('NAGRIKOS_BOOTSTRAP_ADMIN_PASSWORD')
    if password is None:
        if os.getenv('GITHUB_ACTIONS') == 'true':
            parser.error('Protected bootstrap password is missing')
        password=getpass.getpass('New administrator password: ')
        if password != getpass.getpass('Confirm password: '):
            parser.error('Passwords do not match')
    password_policy(password)
    initialize()
    with connect() as db:
        if postgres.enabled():
            # PgBouncer transaction pooling supports transaction-level locks.
            # Serialize the existence check and insert across manual callers.
            db.execute('SELECT pg_advisory_xact_lock(?)', (2026111401,)).fetchone()
        if db.execute("SELECT 1 FROM users WHERE role='admin' AND is_demo=0 LIMIT 1").fetchone():
            parser.error('A public administrator already exists; use a staff invitation')
        if db.execute('SELECT 1 FROM users WHERE email_canonical=?', (email,)).fetchone():
            parser.error('Account already exists')
        db.execute('INSERT INTO users(name,email,email_canonical,email_verified_at,password_hash,role,created_at,is_demo) '
                   'VALUES (?,?,?,?,?,?,?,0)',
                   (name,email,email,int(time.time()),hash_password(password),'admin',
                    time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print('Administrator provisioned. Protect this operator account with two-step verification.')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        # Driver and provider exceptions can contain URLs or other private data.
        print('Administrator provisioning FAILED; inspect preflight and database state before any retry.',
              file=sys.stderr)
        raise SystemExit(1) from None
