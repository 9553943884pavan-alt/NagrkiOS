"""Read-only post-migration checks for the guarded Sydney production branch."""
from __future__ import annotations

import os

from sqlalchemy import UniqueConstraint, create_engine, inspect, pool

from app.models import metadata
from scripts.check_production_target import check_target, check_backup


EXPECTED_REVISION = '20261114_01'


def verify(environ: dict[str, str] | None = None, engine_factory=None) -> dict[str, int]:
    env = os.environ if environ is None else environ
    check_target(env)
    check_backup(env)
    url = env['DIRECT_URL'].replace('postgresql://', 'postgresql+psycopg://', 1)
    engine = (engine_factory(url) if engine_factory else
              create_engine(url, poolclass=pool.NullPool, connect_args={'connect_timeout': 5}))
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            inspector = inspect(connection)
            tables = set(inspector.get_table_names(schema='public'))
            if tables != set(metadata.tables) | {'alembic_version'}:
                raise RuntimeError('Production table set differs from the expected migration')
            revision = connection.exec_driver_sql('SELECT version_num FROM alembic_version').fetchall()
            if len(revision) != 1 or revision[0][0] != EXPECTED_REVISION:
                raise RuntimeError('Production Alembic revision is not expected head')
            foreign_keys = 0
            indexes = 0
            for name, table in metadata.tables.items():
                columns = {item['name'] for item in inspector.get_columns(name)}
                if columns != set(table.columns.keys()):
                    raise RuntimeError('Production table columns differ from metadata')
                actual_fks = inspector.get_foreign_keys(name)
                expected_fks = {tuple(fk.parent.name for fk in constraint.elements)
                                for constraint in table.foreign_key_constraints}
                if {tuple(fk['constrained_columns']) for fk in actual_fks} != expected_fks:
                    raise RuntimeError('Production foreign keys differ from metadata')
                foreign_keys += len(actual_fks)
                actual_indexes = {item['name'] for item in inspector.get_indexes(name)}
                expected_indexes = {item.name for item in table.indexes}
                if not expected_indexes.issubset(actual_indexes):
                    raise RuntimeError('Production indexes differ from metadata')
                indexes += len(expected_indexes)
                actual_unique = {tuple(item['column_names'])
                                 for item in inspector.get_unique_constraints(name)}
                expected_unique = {tuple(column.name for column in constraint.columns)
                                   for constraint in table.constraints
                                   if isinstance(constraint, UniqueConstraint)}
                if not expected_unique.issubset(actual_unique):
                    raise RuntimeError('Production unique constraints differ from metadata')
                pk = inspector.get_pk_constraint(name)
                if set(pk.get('constrained_columns') or []) != {column.name for column in table.primary_key.columns}:
                    raise RuntimeError('Production primary key differs from metadata')
                if connection.exec_driver_sql(f'SELECT COUNT(*) FROM public.{name}').scalar_one() != 0:
                    raise RuntimeError('Production application table is unexpectedly populated')
            connection.rollback()
            return {'tables': len(metadata.tables), 'foreign_keys': foreign_keys,
                    'explicit_indexes': indexes}
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        result = verify()
    except Exception:
        print('Production schema verification FAILED')
        raise SystemExit(1) from None
    print('Production schema verification PASSED: '
          f'{result["tables"]} tables, {result["foreign_keys"]} foreign keys, '
          f'{result["explicit_indexes"]} explicit indexes, expected revision, zero application rows')
