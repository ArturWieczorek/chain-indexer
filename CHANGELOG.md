# Changelog

All notable changes to this project are documented here. The format is loosely
based on Keep a Changelog. Each chapter tag (`chNN`) is a release of the course.

## [Unreleased]

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
