# Chapter 63 - A Postgres backend

> **Goal:** run the exact same indexer over Postgres instead of SQLite - the
> payoff of design seam three (the `Store` interface). And do it **additively**:
> not a line of the existing store, indexers, or migrations changes.

## The trick: an adapter, not a rewrite

`PostgresStore` subclasses `SqliteStore`, so every query method, `apply_block`, and
all the indexers are reused as-is. The only new thing is a small connection
**adapter** that makes psycopg look like the `sqlite3` connection the code expects,
translating three dialect gaps on the fly:

- placeholders `?` -> `%s`;
- the SQLite-only DDL `INTEGER PRIMARY KEY AUTOINCREMENT` -> `SERIAL PRIMARY KEY`;
- `cursor.lastrowid` -> `INSERT ... RETURNING id` (Postgres has no lastrowid), for
  the id-bearing tables.

It also provides a row that is addressable both by name (`row["x"]`) and position
(`row[0]`), matching `sqlite3.Row`, and maps `with conn:` onto a psycopg
transaction. Because all of that lives in the adapter, `store.py`, `indexers.py`,
and `MIGRATIONS` run unchanged.

Choosing a backend is one config field: set `postgres_dsn` (or
`CHAINIDX_POSTGRES_DSN`) and the live runner builds a `PostgresStore`; leave it
empty and it stays on SQLite. The driver is an optional extra: `pip install
'chainidx[postgres]'`.

## Verified against a real Postgres (and what it took)

The module is excluded from the coverage gate (it needs a live server, like the
`ogmios`/`node` clients), and was verified against a real Postgres by running the
whole live indexer into it: applying blocks, address balances, pool detail,
resolved inputs, a **reorg rollback**, and every explorer endpoint under
concurrent load all behave as on SQLite.

Getting there was honest work, and three things did not come for free. The adapter
gained two of them (still additive); the third touched a handful of queries:

- **64-bit amounts.** SQLite's `INTEGER` is 64-bit; Postgres's is 32-bit, which
  overflows on lovelace. The adapter maps `INTEGER` -> `BIGINT` (and ids to
  `BIGSERIAL`) - the wide-numeric point chapter 18 makes about db-sync.
- **Thread safety.** psycopg connections are not thread-safe, and FastAPI serves
  the read endpoints from a worker-thread pool while the follower writes on the
  event loop. So the adapter keeps a connection **per thread**; SQLite tolerated a
  single shared connection, Postgres does not.
- **Portable `GROUP BY`.** SQLite lets you select columns that are not in the
  `GROUP BY`; Postgres does not. A few queries were rewritten to standard SQL
  (grouping by the output alias, and listing every non-aggregated column). This is
  the one non-additive change - and it makes the SQLite queries more correct too.

## When to use which, and mainnet

- **SQLite** is in-process and fastest for the single-writer, row-by-row workload
  of a local cluster or testnet (the primary use) - keep it there.
- **Postgres** is the choice for scale, shared/concurrent readers, and mainnet
  volume. The code is network-agnostic, so mainnet is just a different socket,
  magic (`764824073`), and genesis.
- **Honest limit:** the translation layer costs almost nothing (a couple of string
  replacements per statement). The real cost at mainnet scale is the naive per-row
  `INSERT` (each with a `RETURNING` round-trip) - fine for testnets and for
  tip-following, but a full genesis-to-tip mainnet sync would want bulk `COPY`
  batching (as db-sync does), which is left as future work.

## Test first (red), make it pass (green)

The adapter's dialect logic is small and the backend is verified live; the config
change is unit-tested (`postgres_dsn` from file and environment). `make check`
stays green and fully covered (the Postgres module is coverage-omitted).

## What we built

- `postgresstore.py`: the psycopg adapter and `PostgresStore(SqliteStore)`.
- `Config.postgres_dsn` (+ `CHAINIDX_POSTGRES_DSN`); the live runner picks the
  backend; a `chainidx[postgres]` optional dependency.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch63): an additive Postgres backend via a psycopg adapter"
git tag ch63
```

## Where this leaves the project

All three design seams are now realised: block-keyed rollback, a pluggable indexer
pipeline, and - here - a swappable storage backend, with SQLite and Postgres both
working behind one `Store` interface.
