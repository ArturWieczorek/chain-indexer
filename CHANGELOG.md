# Changelog

All notable changes to this project are documented here. The format is loosely
based on Keep a Changelog. Each chapter tag (`chNN`) is a release of the course.

## [Unreleased]

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
