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
from collections.abc import Sequence
from typing import Protocol

from chainidx.indexers import Indexer, default_indexers
from chainidx.model import Asset, Block, Point, Tip, Tx, TxOut


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

    def balance(self, address: str) -> int:
        """Return the unspent lovelace held by an address."""
        ...

    def utxos(self, address: str) -> tuple[TxOut, ...]:
        """Return an address's unspent outputs."""
        ...

    def rollback_to(self, point: Point | None) -> list[str]:
        """Undo every block after ``point``; return removed hashes, newest-first."""
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
    (
        2,
        (
            # Every table carries block_id directly, so the chapter 05 rollback
            # engine can delete a block's rows with one uniform query per table.
            # `consumed_by_tx_id` is NULL until the output is spent; an address
            # balance is the sum of its outputs where it is still NULL.
            """
            CREATE TABLE tx_out (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id             INTEGER NOT NULL REFERENCES tx(id),
                block_id          INTEGER NOT NULL REFERENCES block(id),
                index_no          INTEGER NOT NULL,
                address           TEXT    NOT NULL,
                lovelace          INTEGER NOT NULL,
                consumed_by_tx_id INTEGER REFERENCES tx(id)
            )
            """,
            """
            CREATE TABLE ma_tx_out (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_out_id  INTEGER NOT NULL REFERENCES tx_out(id),
                block_id   INTEGER NOT NULL REFERENCES block(id),
                policy_id  TEXT    NOT NULL,
                asset_name TEXT    NOT NULL,
                quantity   INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE tx_in (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_in_id     INTEGER NOT NULL REFERENCES tx(id),
                block_id     INTEGER NOT NULL REFERENCES block(id),
                tx_out_hash  TEXT    NOT NULL,
                tx_out_index INTEGER NOT NULL
            )
            """,
            "CREATE INDEX idx_tx_out_address ON tx_out (address)",
            "CREATE INDEX idx_tx_out_tx ON tx_out (tx_id, index_no)",
            "CREATE INDEX idx_ma_tx_out_parent ON ma_tx_out (tx_out_id)",
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

    def __init__(self, path: str = ":memory:", indexers: Sequence[Indexer] | None = None) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        # Enforce foreign keys so a bad delete order is caught, not silently
        # allowed. Chapter 05 relies on this to prove leaf-first deletion.
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._indexers: tuple[Indexer, ...] = (
            tuple(indexers) if indexers is not None else default_indexers()
        )
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
            assert block_id is not None
            for index, tx in enumerate(block.txs):
                cur = self._conn.execute(
                    "INSERT INTO tx (hash, block_id, block_index) VALUES (?, ?, ?)",
                    (tx.tx_id, block_id, index),
                )
                tx_db_id = cur.lastrowid
                assert tx_db_id is not None
                for indexer in self._indexers:
                    indexer.index_tx(self._conn, block_id, tx_db_id, tx)

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

    def balance(self, address: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(lovelace), 0) AS bal FROM tx_out "
            "WHERE address = ? AND consumed_by_tx_id IS NULL",
            (address,),
        ).fetchone()
        return int(row["bal"])

    def utxos(self, address: str) -> tuple[TxOut, ...]:
        rows = self._conn.execute(
            "SELECT id, address, lovelace FROM tx_out "
            "WHERE address = ? AND consumed_by_tx_id IS NULL ORDER BY id",
            (address,),
        ).fetchall()
        outputs: list[TxOut] = []
        for r in rows:
            asset_rows = self._conn.execute(
                "SELECT policy_id, asset_name, quantity FROM ma_tx_out "
                "WHERE tx_out_id = ? ORDER BY id",
                (r["id"],),
            ).fetchall()
            assets = tuple(
                Asset(policy_id=a["policy_id"], asset_name=a["asset_name"], quantity=a["quantity"])
                for a in asset_rows
            )
            outputs.append(TxOut(address=r["address"], lovelace=r["lovelace"], assets=assets))
        return tuple(outputs)

    def rollback_to(self, point: Point | None) -> list[str]:
        """Undo every block after ``point`` and return the removed hashes.

        This is the reorg engine. ``point`` is where the node told us to back up
        to (or ``None`` for the origin, meaning "throw everything away"). We map
        the point to a block id and then undo everything above it.

        The order below is not arbitrary; foreign keys force it:

        1. **Un-consume first.** Outputs from *surviving* blocks may have been
           spent by transactions in the blocks we are about to delete. We clear
           their `consumed_by_tx_id` so those outputs become unspent again -
           this is how a rollback restores balances. It must happen before we
           delete those transactions, or the foreign key would refuse.
        2. **Delete leaf-first.** `ma_tx_out` before `tx_out` (it points at it),
           and everything that points at `tx` before `tx`, and `tx` before
           `block`. Deleting a parent before its children would raise a foreign
           key error - which is exactly the safety net we want.

        Everything runs in one transaction, so a crash mid-rollback leaves the
        database untouched rather than half-rewound.
        """
        if point is None:
            target_id = 0
        else:
            row = self._conn.execute(
                "SELECT id FROM block WHERE hash = ?", (point.block_hash,)
            ).fetchone()
            if row is None:
                raise ValueError(f"cannot roll back to unknown point: {point!r}")
            target_id = int(row["id"])

        removed = [
            r["hash"]
            for r in self._conn.execute(
                "SELECT hash FROM block WHERE id > ? ORDER BY id DESC", (target_id,)
            ).fetchall()
        ]

        with self._conn:
            # 1. Restore outputs that the removed transactions had consumed.
            self._conn.execute(
                "UPDATE tx_out SET consumed_by_tx_id = NULL "
                "WHERE consumed_by_tx_id IN (SELECT id FROM tx WHERE block_id > ?)",
                (target_id,),
            )
            # 2. Delete the removed blocks' rows, leaf-first.
            for table in ("ma_tx_out", "tx_out", "tx_in", "tx"):
                self._conn.execute(f"DELETE FROM {table} WHERE block_id > ?", (target_id,))
            self._conn.execute("DELETE FROM block WHERE id > ?", (target_id,))

        return removed

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
