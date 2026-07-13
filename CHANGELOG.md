# Changelog

All notable changes to this project are documented here. The format is loosely
based on Keep a Changelog. Each chapter tag (`chNN`) is a release of the course.

## [Unreleased]

## [ch08] - A source and the Ogmios client

### Added

- `chainidx.source`: `RollForward`/`RollBackward` events, the `ChainSource`
  interface, an `Origin` marker, and a scripted `FakeSource`.
- `chainidx.ogmios_parse` (pure, covered) and `chainidx.ogmios.OgmiosSource`
  (integration-only), with real captured fixtures under `tests/fixtures/`.
- An integration test that follows a real chain from the origin via Ogmios.

## [ch07] - Conway governance

### Added

- Governance model: `DRepRegistration`, `DRepDeregistration`,
  `GovActionProposal`, `GovVote`, plus `Tx.proposals` and `Tx.votes`.
- `GovIndexer` and DRep handling in `CertIndexer`; migration 4 (governance
  tables), wired into the rollback loop.
- Derived views: `dreps`, `governance_actions`, `vote_tally`.

## [ch06] - Shelley staking

### Added

- Certificate model (`StakeRegistration`, `StakeDeregistration`,
  `StakeDelegation`, `PoolRegistration`, `PoolRetirement`) and `Tx.certificates`.
- `CertIndexer` and schema migration 3 (staking + pool tables), added to the
  generic rollback loop via `_ROLLBACK_TABLES`.
- Derived views: `pools`, `delegation_of`, `is_stake_registered`.

## [ch05] - Rollbacks and reorgs

### Added

- `SqliteStore.rollback_to(point)`: the reorg engine. Restores outputs the
  removed blocks spent, then deletes their rows leaf-first, in one transaction.
- A property test proving a reorg leaves the database identical to one built
  only from the winning branch.

## [ch04] - Indexing transactions

### Added

- `chainidx.indexers`: the pluggable indexer pipeline with `OutputIndexer` and
  `InputIndexer`.
- Schema migration 2: `tx_out`, `ma_tx_out`, `tx_in`, all block-keyed; spend
  tracking via `consumed_by_tx_id`.
- `SqliteStore.balance` and `SqliteStore.utxos` derived views.

## [ch03] - SQLite schema and store

### Added

- `chainidx.store`: a `Store` protocol and a `SqliteStore` backed by SQLite.
- A versioned migration runner and the first schema (`block`, `tx`), modelled on
  cardano-db-sync, with block-keyed rows and enforced foreign keys.

## [ch02] - The fork problem

### Added

- `chainidx.chain.Chain`: an in-memory chain with `add_block`, `has_point`,
  `find_intersection`, `rollback_to`, and `points`.
- `ForkError`, raised when a block does not build on the current tip.

## [ch01] - The block and chain model

### Added

- `chainidx.model`: immutable dataclasses `Asset`, `TxOut`, `TxIn`, `Tx`,
  `Block`, `Point`, and `Tip` that describe a Cardano chain.
- `Block.point` and `Block.links_onto`, the seed of fork detection.

## [ch00] - Orientation

### Added

- Project scaffold: `src/chainidx/` package, `tests/`, and `chapters/`.
- Tooling: ruff (lint and format), mypy (strict), pytest with a 100 percent
  coverage gate, pre-commit hooks, and a GitHub Actions CI workflow.
- Makefile with `install`, `fmt`, `lint`, `type`, `test`, and `check` targets.
- MIT license, README with the course outline, this changelog, and a progress
  checklist.
- A smoke test proving the package imports and the toolchain is wired up.
