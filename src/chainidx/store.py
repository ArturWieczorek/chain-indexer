"""The store: where indexed chain data lives.

We define storage as an *interface* (a ``Protocol``) and give one concrete
implementation backed by SQLite. The rest of the code depends only on the
interface, so a different backend (Postgres, for scale) could be dropped in later
without touching the indexer or the API. That is the third of the project's
design seams.

The schema is a deliberately small version of cardano-db-sync's. This chapter
creates just two tables, `block` and `tx`; later chapters add outputs, inputs,
assets, staking, and governance. Two design choices carry through all of them:

- **Every table hangs off a block.** `tx.block_id` points at `block.id`. When a
  rollback deletes a block (chapter 05), everything that belongs to it can be
  found and deleted too. New tables just need a `block_id` to roll back for free.
- **Migrations are versioned.** The schema is built by a numbered list of
  migrations. On startup we apply only the ones newer than what the database
  already has, so opening an existing database is safe and idempotent. This
  mirrors how db-sync manages its own schema.

We store hashes as hex text and amounts as integers to keep the teaching code
readable. Real db-sync uses raw `bytea` for hashes and `numeric` for lovelace so
that large sums cannot overflow; chapter 18 discusses the difference.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from chainidx.model import Block, Point, Tip, Tx


class Store(Protocol):
    """The contract every storage backend must satisfy."""

    def apply_block(self, block: Block) -> None:
        """Persist a block and its transactions."""
        ...

    def get_block(self, block_hash: str) -> Block | None:
        """Return the stored block with this hash, or ``None``."""
        ...

    def tip(self) -> Tip | None:
        """Return the newest stored block as a tip, or ``None`` if empty."""
        ...

    def block_count(self) -> int:
        """Return how many blocks are stored."""
        ...

    def close(self) -> None:
        """Release the underlying resources."""
        ...


# Each migration is (version, statements). Apply the ones newer than the
# database's current version, in order. Never edit a released migration; add a
# new one. Later chapters append to this list.
MIGRATIONS: list[tuple[int, tuple[str, ...]]] = [
    (
        1,
        (
            """
            CREATE TABLE block (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                hash      TEXT    NOT NULL UNIQUE,
                slot_no   INTEGER NOT NULL,
                block_no  INTEGER NOT NULL,
                prev_hash TEXT    NOT NULL,
                tx_count  INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE tx (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hash        TEXT    NOT NULL UNIQUE,
                block_id    INTEGER NOT NULL REFERENCES block(id),
                block_index INTEGER NOT NULL
            )
            """,
        ),
    ),
]


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Bring the database schema up to the newest migration version."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current: int = row[0] if row is not None and row[0] is not None else 0

    for version, statements in MIGRATIONS:
        if version > current:
            for sql in statements:
                conn.execute(sql)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


class SqliteStore:
    """A store backed by SQLite. Satisfies the ``Store`` protocol."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        # Enforce foreign keys so a bad delete order is caught, not silently
        # allowed. Chapter 05 relies on this to prove leaf-first deletion.
        self._conn.execute("PRAGMA foreign_keys = ON")
        _run_migrations(self._conn)

    def apply_block(self, block: Block) -> None:
        # `with self._conn` opens a transaction that commits on success and
        # rolls back if anything raises - so a half-written block never lands.
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO block (hash, slot_no, block_no, prev_hash, tx_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (block.block_hash, block.slot_no, block.block_no, block.prev_hash, len(block.txs)),
            )
            block_id = cur.lastrowid
            for index, tx in enumerate(block.txs):
                self._conn.execute(
                    "INSERT INTO tx (hash, block_id, block_index) VALUES (?, ?, ?)",
                    (tx.tx_id, block_id, index),
                )

    def get_block(self, block_hash: str) -> Block | None:
        row = self._conn.execute(
            "SELECT id, hash, slot_no, block_no, prev_hash FROM block WHERE hash = ?",
            (block_hash,),
        ).fetchone()
        if row is None:
            return None
        tx_rows = self._conn.execute(
            "SELECT hash FROM tx WHERE block_id = ? ORDER BY block_index",
            (row["id"],),
        ).fetchall()
        txs = tuple(Tx(tx_id=r["hash"]) for r in tx_rows)
        return Block(
            block_no=row["block_no"],
            slot_no=row["slot_no"],
            block_hash=row["hash"],
            prev_hash=row["prev_hash"],
            txs=txs,
        )

    def tip(self) -> Tip | None:
        row = self._conn.execute(
            "SELECT hash, slot_no, block_no FROM block ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Tip(
            point=Point(slot_no=row["slot_no"], block_hash=row["hash"]),
            block_no=row["block_no"],
        )

    def block_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM block").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
