# Chapter 03 - SQLite schema and store

> **Goal:** give the indexer a real place to keep data. Define storage as an
> interface, build a tiny relational schema (modelled on cardano-db-sync) behind
> it, run versioned migrations, and persist a block with its transactions.

So far everything lived in memory and vanished when the process exited. An
indexer has to remember what it has seen, so this chapter introduces a database.
We use **SQLite**, which ships with Python (`import sqlite3`) and stores the whole
database in a single file - no server to install. It is the honest starting point;
chapter 18 explains when you would reach for Postgres instead.

## Storage as an interface

We do not want the rest of the code bolted to SQLite forever. So we first write
the *contract* - a `Store` interface - and then one implementation of it:

```python
class Store(Protocol):
    def apply_block(self, block: Block) -> None: ...
    def get_block(self, block_hash: str) -> Block | None: ...
    def tip(self) -> Tip | None: ...
    def block_count(self) -> int: ...
    def close(self) -> None: ...
```

> **Python note - `Protocol`.** A `Protocol` describes the *shape* something must
> have without requiring inheritance. Any class with these methods "is a" `Store`
> as far as the type checker is concerned. This is called structural typing, or
> duck typing with a type checker watching. It means `SqliteStore` does not have
> to subclass anything, and a future `PostgresStore` would just need the same
> methods. That is design seam number three from the project overview.

## The schema (a simplified db-sync)

cardano-db-sync has around eighty-five tables. We start with two and grow slowly.
The shapes mirror db-sync so the naming transfers if you ever read the real
thing.

```
  block                              tx
  +----------------+                 +-------------------+
  | id     (PK)    |<----------------| block_id  (FK)    |
  | hash    UNIQUE |                 | id     (PK)       |
  | slot_no        |                 | hash    UNIQUE    |
  | block_no       |                 | block_index       |
  | prev_hash      |                 +-------------------+
  | tx_count       |
  +----------------+
```

Two decisions here carry through the whole project:

1. **Every table hangs off a block.** A transaction row records the `block_id` it
   came in. That single foreign key is what makes rollback tractable: to undo a
   block, find everything with that `block_id` and delete it. Every table we add
   later (outputs, certificates, votes) will carry a `block_id` for the same
   reason, and so will roll back for free. This is design seam number one.
2. **Foreign keys are enforced** (`PRAGMA foreign_keys = ON`). SQLite does not
   enforce them by default. We turn them on so that deleting a `block` while a
   `tx` still points at it is an *error*, not silent corruption. In chapter 05
   that rule is what forces us to delete in the correct, leaf-first order.

> **Simplifications, stated honestly.** We store hashes as hex text (db-sync uses
> raw 32-byte `bytea`) and amounts as plain integers (db-sync uses `numeric` so
> that sums across millions of rows cannot overflow a 64-bit column). These make
> the teaching code readable; chapter 18 lists every such shortcut.

## Versioned migrations

How does the schema get created, and what happens when you open an existing
database? We keep a numbered list of migrations and a `schema_version` table that
records which ones have run:

```python
MIGRATIONS = [
    (1, ("CREATE TABLE block (...)", "CREATE TABLE tx (...)")),
]
```

On startup we apply only the migrations whose version is newer than what the
database already has. Opening a fresh database runs migration 1; opening an
existing one runs nothing and leaves the data alone. The rule that keeps this
safe: **never edit a released migration, only append a new one.** This is exactly
how db-sync evolves its schema across releases.

## Transactions that are actually transactional

`apply_block` inserts the block row, then one `tx` row per transaction. If the
process died between those inserts we would have a block with missing
transactions. SQLite's connection is a context manager that wraps a database
transaction:

```python
with self._conn:            # BEGIN
    cur = self._conn.execute("INSERT INTO block ...")
    for index, tx in enumerate(block.txs):
        self._conn.execute("INSERT INTO tx ...")
# COMMIT here, or ROLLBACK automatically if anything raised
```

Either the whole block lands or none of it does. That all-or-nothing property is
the foundation the reorg logic will build on.

## Test first (red), make it pass (green)

The tests describe the behaviour we want - an empty store, persisting a block,
round-tripping it with its transactions, the tip tracking the newest block, and
data surviving a reopen:

```python
def test_data_survives_reopening_the_database(tmp_path) -> None:
    db = str(tmp_path / "chain.db")
    first = SqliteStore(db)
    first.apply_block(block(1, "b1", "genesis"))
    first.close()

    second = SqliteStore(db)          # migrations do not re-run
    assert second.block_count() == 1
    assert second.get_block("b1") is not None
    second.close()
```

`SqliteStore` implements the five interface methods plus a context manager so
`with SqliteStore() as store:` closes it for you. `make check` stays green and
fully covered.

## What we built

- A `Store` interface and a `SqliteStore` implementation of it.
- A two-table schema (`block`, `tx`) modelled on db-sync, with block-keyed rows
  and enforced foreign keys.
- A versioned migration runner that makes opening a database idempotent.
- All-or-nothing `apply_block`.

## Glossary

- **SQLite**: a small, serverless SQL database kept in one file; built into
  Python.
- **Protocol / structural typing**: an interface defined by method shape, not by
  inheritance.
- **Migration**: a versioned schema change; the runner applies pending ones.
- **Foreign key**: a column that must reference an existing row in another table.
- **Transaction (database)**: a group of statements that commit together or not
  at all - do not confuse with a Cardano transaction.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch03): add the SQLite store, schema, and migrations"
git tag ch03
```

## Next up

[Chapter 04 - Indexing transactions](../04-indexing-transactions/): we index what
is *inside* the transactions - outputs, inputs, and native assets - and build the
first derived view: an address's balance from its unspent outputs. We also
introduce the pluggable indexer pipeline (design seam number two).
