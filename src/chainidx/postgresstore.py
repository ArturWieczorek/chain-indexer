"""A Postgres-backed store - the same indexer over a different database.

This is the payoff of design seam three (the ``Store`` interface): the API, CLI,
and explorer depend only on the interface, so a different backend drops in without
touching them. And here even the store's own query code and the indexers are
reused unchanged - ``PostgresStore`` subclasses ``SqliteStore`` and only swaps the
connection for a small **adapter** that makes psycopg look like the sqlite3
connection the code expects. The adapter translates three things on the fly:

- placeholders ``?`` -> ``%s``;
- the SQLite-only DDL ``INTEGER PRIMARY KEY AUTOINCREMENT`` -> ``SERIAL PRIMARY KEY``;
- ``cursor.lastrowid`` -> ``INSERT ... RETURNING id`` (Postgres has no lastrowid).

So the whole of ``store.py``, ``indexers.py``, and the migration list run as they
are. Like the other backends that need a live server (``ogmios``, ``node``), this
module is excluded from the coverage gate; it is exercised against a real Postgres
instead. Install the driver with ``pip install 'chainidx[postgres]'``.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

from chainidx.indexers import Indexer, default_indexers
from chainidx.store import SqliteStore, _run_migrations

# Tables whose primary key is a serial ``id``; an INSERT into one gets a
# ``RETURNING id`` appended so the adapter can report ``lastrowid``.
_ID_TABLES = frozenset(
    {
        "block",
        "tx",
        "tx_out",
        "ma_tx_out",
        "tx_in",
        "stake_registration",
        "stake_deregistration",
        "delegation",
        "pool_registration",
        "pool_retirement",
        "drep_registration",
        "drep_deregistration",
        "gov_action_proposal",
        "voting_procedure",
        "certificate",
        "withdrawal",
        "asset_metadata",
        "mint_event",
    }
)


def _to_pg(sql: str) -> str:
    """Translate a SQLite statement to its Postgres equivalent.

    SQLite's ``INTEGER`` is 64-bit; Postgres's is 32-bit, which overflows on
    lovelace amounts. So an id column becomes ``BIGSERIAL`` and every other
    ``INTEGER`` becomes ``BIGINT`` (as db-sync uses wide numeric types). Foreign
    keys then line up (all ``int8``).
    """
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    sql = sql.replace("INTEGER", "BIGINT")
    return sql.replace("?", "%s")


def _wants_id(sql: str) -> bool:
    stripped = sql.lstrip()
    if not stripped[:12].upper().startswith("INSERT INTO ") or "RETURNING" in sql.upper():
        return False
    table = stripped[12:].lstrip().split()[0].split("(")[0]
    return table in _ID_TABLES


class _HybridRow:
    """A row addressable by column name (``row["x"]``) or position (``row[0]``),
    matching what ``sqlite3.Row`` gave the store."""

    def __init__(self, values: tuple[Any, ...], columns: dict[str, int]) -> None:
        self._values = values
        self._columns = columns

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._columns[key]]


def _row_factory(cursor: Any) -> Any:
    columns = {c.name: i for i, c in enumerate(cursor.description or [])}

    def make(values: Sequence[Any]) -> _HybridRow:
        return _HybridRow(tuple(values), columns)

    return make


class _PgCursor:
    def __init__(self, cursor: Any, lastrowid: int | None) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return list(self._cursor.fetchall())


class _PgConn:
    """Enough of the sqlite3.Connection surface for the store to run unchanged.

    psycopg connections are not thread-safe, and FastAPI runs the read endpoints in
    a worker-thread pool while the follower writes on the event-loop thread. So each
    thread gets its own connection (thread-local), which is how the shared store can
    be used from both at once, as it was with SQLite.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._local = threading.local()

    def _pg(self) -> Any:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            import psycopg

            conn = psycopg.connect(self._dsn, autocommit=True, row_factory=_row_factory)
            self._local.conn = conn
        return conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> _PgCursor:
        text = _to_pg(sql)
        want_id = _wants_id(sql)
        if want_id:
            text += " RETURNING id"
        cursor = self._pg().cursor()
        cursor.execute(text, tuple(params))
        lastrowid = None
        if want_id:
            row = cursor.fetchone()
            lastrowid = row["id"] if row is not None else None
        return _PgCursor(cursor, lastrowid)

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> None:
        cursor = self._pg().cursor()
        cursor.executemany(_to_pg(sql), [tuple(row) for row in seq])

    def commit(self) -> None:
        pass  # the connection is in autocommit mode

    def __enter__(self) -> _PgConn:
        self._local.tx = self._pg().transaction()
        self._local.tx.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        tx = self._local.tx
        self._local.tx = None
        return tx.__exit__(exc_type, exc, tb)

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()


class PostgresStore(SqliteStore):
    """The SQLite store's logic, backed by Postgres through the adapter."""

    def __init__(self, dsn: str, indexers: Sequence[Indexer] | None = None) -> None:
        self._conn = _PgConn(dsn)  # type: ignore[assignment]
        self._indexers: tuple[Indexer, ...] = (
            tuple(indexers) if indexers is not None else default_indexers()
        )
        _run_migrations(self._conn)
