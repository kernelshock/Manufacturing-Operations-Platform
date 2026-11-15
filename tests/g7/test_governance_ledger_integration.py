"""Database-level mutation guards for governance evidence."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ, reason="requires disposable PostgreSQL"
)


@pytest.mark.parametrize("table", ["planning_governance_case", "planning_governance_event"])
@pytest.mark.parametrize("command", ["UPDATE {table} SET id = id WHERE false",
                                    "DELETE FROM {table} WHERE false",
                                    "TRUNCATE TABLE {table} CASCADE"])
def test_governance_ledger_rejects_mutation(table, command):
    engine = create_engine(os.environ["MOP_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(DBAPIError, match="planning governance records are append-only"):
                    connection.execute(text(command.format(table=table)))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
