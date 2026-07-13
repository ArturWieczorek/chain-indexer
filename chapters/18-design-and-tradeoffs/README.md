# Chapter 18 - Design and tradeoffs

> **Goal:** step back. What did we build, how does it compare to the real tools,
> what did we deliberately leave out, and where would a real deployment go next?
> An honest map of the edges is part of doing the project properly.

There is no new code here. This chapter is the reflection that turns a working
program into an understood one.

## Where this sits: db-sync and Dolos

Two production tools do what our indexer does, at scale:

- **[cardano-db-sync](https://github.com/IntersectMBO/cardano-db-sync)** is the
  reference indexer: Haskell, PostgreSQL, around eighty-five tables, and a
  complete picture of the chain including ledger-state data. Our schema, our
  naming (`block`, `tx`, `tx_out`, `tx_in`, the staking and governance tables),
  and our rollback strategy are deliberately modelled on it, in miniature.
- **[Dolos](https://github.com/txpipe/dolos)** is a lightweight "Cardano data
  node": it speaks the mini-protocols itself (as we do) and keeps a compact store,
  aimed at being smaller and easier to run than db-sync. Our project is closest in
  spirit to Dolos - follow the node directly, index what you need - but sized for
  reading in an afternoon.

Naming these is not name-dropping; it is knowing the landscape. If you understand
this project, the real ones are the same ideas with more surface.

## The one boundary that matters: on-chain vs ledger state

The single most important thing to state plainly is what we cannot compute.

Everything we index is **on-chain**: it appears in a block, in a transaction body.
Delegations, pool registrations, DReps, votes, governance actions - all of it
arrives over chain-sync, so we can index it from blocks alone.

What we do **not** compute is **ledger state**: the numbers the node derives from
the entire history and the protocol's equations.

```
  ON-CHAIN (we index it)                 LEDGER STATE (we do not)
  ----------------------                 ------------------------
  "alice delegated to pool1"             "pool1's live stake is 4.2M ADA"
  "pool1 registered, 3% margin"          "alice earned 12 ADA in rewards"
  "gov1 was proposed and voted Yes"      "the epoch stake snapshot"
  UTxO balances (from outputs)           "the treasury and reserves pots"
```

The right-hand column is not in any block. db-sync produces it by querying the
node's ledger state through a second mini-protocol, `local-state-query`, and by
replaying reward calculations at epoch boundaries. We deliberately implemented
only chain-sync, so our indexer can tell you *who delegated to whom* but not *how
much they earned*. That is a real limitation, stated on purpose - and it is an
*additive* one: adding `local-state-query` and an epoch-boundary indexer would
fill it in without changing the storage or the reorg engine.

## Shortcuts we took (and what production does)

| We did | Production does | Why it matters |
| ------ | --------------- | -------------- |
| Hashes and addresses as hex text | raw 28/32-byte `bytea`; addresses bech32-encoded | smaller storage; human-readable addresses |
| Amounts as SQLite integers | `numeric` (up to 128-bit) | summing millions of rows cannot overflow |
| SQLite | PostgreSQL | concurrent readers, size, operational tooling |
| A subset of certificate types decoded | every certificate, script, datum, redeemer, witness, metadata | completeness |
| Chain-sync only | chain-sync + local-state-query + local-tx-submission | rewards, live stake, tx submission |
| `check_same_thread=False` on one connection | a connection pool per request | real concurrency under load |

None of these are accidents; each is a deliberate trade of completeness for
clarity, and each is called out where it appears in the chapters.

## The four seams, revisited

The project was built so that growth is additive, not a rewrite. Four seams make
that true:

1. **Every table carries `block_id`, and rollback is generic.** Add a table with a
   `block_id` and it rolls back for free (`_ROLLBACK_TABLES`). This is how staking
   (chapter 06) and governance (chapter 07) cost almost nothing to add.
2. **The indexer pipeline is pluggable.** New data domains are new indexer modules;
   the source, sync loop, and reorg engine never change.
3. **Storage is behind a `Store` interface.** A `PostgresStore` for mainnet-scale
   volume is a drop-in, exactly as `url-shortener` moved from SQLite to Postgres.
   (This is the complement to the sibling
   [`storage-engine`](https://github.com/ArturWieczorek/storage-engine) project,
   which is the durable-on-disk side; this project is the chain-facing side.)
4. **The event bus decouples consumers.** The live dashboard is one subscriber; a
   webhook notifier would be another. Nothing in the core knows they exist.

The one genuine boundary, ledger state, is a *data-source* addition, not a storage
change - so even the biggest missing piece slots in without disturbing what is
here.

## Performance, briefly

At testnet and preview sizes, SQLite with a handful of indexes (on `tx_out.address`
and the join columns) is comfortable. The costs that would bite at mainnet scale
are the ones production addresses: write throughput during initial sync, the size
of the `tx_out` table, and concurrent read load - which is why db-sync uses
Postgres, batches writes, and maintains a `reverse_index` to speed rollbacks near
the tip. Our `rollback_to` deletes by `block_id > target` with an index on it;
db-sync's is more elaborate for the same reason: at the tip, rollbacks are frequent
and must be fast.

## Finality

Blocks near the tip are not final. A block becomes practically permanent only once
about `k = 2160` blocks are built on top of it. Our indexer, like db-sync, always
follows the node's current chain and rolls back whenever told - it never assumes a
recent block is safe. An application reading our data should treat the last ~2160
blocks as provisional, which is why the tip and rollbacks are first-class
throughout.

## What we built, in one sentence

A reorg-aware Cardano chain indexer that follows a node over a wire protocol we
wrote by hand, indexes value, staking, and governance into a relational store that
rolls back correctly, and serves the result as an API, a CLI, and a browsable,
live-updating explorer.

## Commit and tag

```bash
git add -A
git commit -m "docs(ch18): design, tradeoffs, and the honest boundaries"
git tag ch18
```

## Next up

[Chapter 19 - Publish](../19-publish/): the finish line. We tidy the README,
finalize the changelog, confirm `make check` is green across every chapter, and
tag `v1.0.0`.
