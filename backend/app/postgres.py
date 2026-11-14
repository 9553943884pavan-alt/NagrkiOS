"""PostgreSQL connection adapter for the existing parameterized SQL queries."""
from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine


def _url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {'postgresql', 'postgresql+psycopg'} or not parsed.hostname:
        raise RuntimeError('DATABASE_URL must be a PostgreSQL connection URL')
    sslmode = parse_qs(parsed.query).get('sslmode', ['require'])[-1]
    if sslmode not in {'require', 'verify-ca', 'verify-full'}:
        raise RuntimeError('DATABASE_URL must require TLS')
    return value.replace('postgresql://', 'postgresql+psycopg://', 1)


@lru_cache(maxsize=4)
def engine_for(value: str):
    sslmode = parse_qs(urlsplit(value).query).get('sslmode', ['require'])[-1]
    return create_engine(_url(value), connect_args={'sslmode': sslmode},
                         pool_size=5, max_overflow=5, pool_timeout=20,
                         pool_pre_ping=True, pool_recycle=1800)


def enabled() -> bool:
    return bool(os.getenv('DATABASE_URL', '').strip())


class Record(Mapping):
    def __init__(self, row):
        self._values = tuple(row)
        self._mapping = dict(row._mapping)

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self):
        return len(self._mapping)


class Result:
    def __init__(self, result):
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self._result.fetchone()
        return Record(row) if row is not None else None

    def fetchall(self):
        return [Record(row) for row in self._result.fetchall()]

    def __iter__(self):
        for row in self._result:
            yield Record(row)


class Connection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params=()):
        # Application SQL uses SQLite's positional placeholders. All values stay
        # bound parameters; SQL is never interpolated with their contents.
        return Result(self._connection.exec_driver_sql(sql.replace('?', '%s'), tuple(params)))

    def executemany(self, sql: str, rows):
        return Result(self._connection.exec_driver_sql(sql.replace('?', '%s'), [tuple(row) for row in rows]))

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def connect():
    return Connection(engine_for(os.environ['DATABASE_URL']).connect())
