# Chapter 00 - Orientation

> **Goal:** set up a professional Python project (tests, linting, type checking,
> CI) and, just as important, build the mental model for the whole course. By the
> end you can run `make check` and see it pass, and you know what a chain indexer
> is and why the hard part is rollbacks.

This chapter writes almost no real code. That is deliberate. A project you will
extend twenty times over is worth starting on solid ground: a place for the code,
a place for the tests, and a machine that tells you the moment something breaks.

## What we are building, over the whole course

A **chain indexer**. Let us define that from scratch, assuming you have never
touched a blockchain.

A **blockchain** is, for our purposes, just a very long list of **blocks**. Each
block contains some **transactions** (records of value moving from one address to
another), and each block points back to the one before it by including that
previous block's **hash** (a short fingerprint). So the blocks form a chain:

```
  block 0  <--  block 1  <--  block 2  <--  block 3   ...
  (genesis)     prev=0        prev=1        prev=2
```

A **node** is a program that participates in the network, validates this chain,
and holds the official copy. Cardano's node is `cardano-node`.

A blockchain is great at answering "what is the very latest state?" but terrible
at answering questions like "what is the balance of this address?" or "show me
every transaction in the last hour". To answer those you would have to replay the
entire chain every time. That is where an **indexer** comes in:

> An **indexer** follows the chain block by block and writes the interesting parts
> into an ordinary database, in a shape that is easy to query.

That is all `cardano-db-sync` (the professional tool this project imitates) does:
it reads blocks from a node and writes rows into PostgreSQL so that explorers,
wallets, and analytics tools can use plain SQL. We are building a tiny version of
the same idea.

## The one hard problem: rollbacks

Here is the twist that makes this interesting rather than a boring copy loop.

The newest blocks at the tip of the chain are **not final**. Two block producers
can briefly create competing blocks at the same height, and the network later
picks one and discards the other. When that happens, the node tells every
follower: *"the last block (or last few blocks) are gone - back up and follow this
other version instead."* That message is a **rollback** (also called a **reorg**,
short for reorganization).

So our indexer keeps **two copies of reality**, and it treats them differently:

```
   THE NODE  =  the source of truth, decides everything
       |
       v
   +------------------------------------------------------+
   |  our indexer holds two things:                       |
   |                                                      |
   |   (1) THE DATABASE   - rows on disk, the thing        |
   |       people query. Expensive to change.             |
   |                                                      |
   |   (2) THE CHAIN VIEW - which blocks we think are      |
   |       current, in memory. Cheap to rewind.           |
   +------------------------------------------------------+
```

When a rollback arrives, we must undo exactly the database rows that belonged to
the discarded blocks - no more, no less - and do it safely even if the program
crashes halfway. Getting that right is the whole course. We will build it against
fake, synthetic chains first (chapter 05) so we can test every awkward case
without needing a real node, and only later connect to the real thing.

## Why the tooling, in plain terms

A professional Python project uses a few tools so that mistakes are caught by a
machine, not by a reader. We wire them up now so every later chapter is checked
automatically.

| Tool | What it does | Analogy |
| ---- | ------------ | ------- |
| **pytest** | Runs our tests | The thing that says "still working" or "you broke it" |
| **coverage** | Measures how much code the tests actually run | A checklist that no line went untested |
| **ruff** | Lints (finds likely bugs) and formats (fixes layout) | A tidy-up-and-proofread pass |
| **mypy** | Checks types (that an `int` is not used as a `str`) | A spell-checker for data shapes |
| **pre-commit** | Runs the above before each commit | A bouncer at the door |
| **GitHub Actions** | Runs everything again on every push | The same bouncer, in the cloud |

The `Makefile` bundles them: `make check` runs the linter, the type checker, and
the tests in one command. That single command is our definition of "green", and
every chapter must leave it green.

## Test first (red)

Before any code, a test. This one is tiny on purpose - it only checks that the
package imports and reports its version.

```python
# tests/test_smoke.py
import chainidx


def test_package_imports_and_has_a_version() -> None:
    assert chainidx.__version__ == "0.1.0"
```

Run it before the package exists and it fails to import: that is our "red".

## Make it pass (green)

Create the package with a version string:

```python
# src/chainidx/__init__.py
__version__ = "0.1.0"
```

Now the toolchain is proven end to end:

```bash
make install   # create the environment and install the tools
make check     # lint + type check + tests, all green
```

## What we built

- A `src/chainidx/` package and a `tests/` folder, laid out the standard way.
- `pyproject.toml` describing the package, its (currently empty) dependencies,
  and the configuration for ruff, mypy, pytest, and coverage.
- A `Makefile`, pre-commit hooks, and a CI workflow, so quality checks run the
  same way on your laptop and in the cloud.
- A smoke test that keeps us honest: if the package stops importing, we hear
  about it immediately.

Small as it is, the project is now a place we can build on with confidence.

## Glossary

- **Block**: one entry in the chain; holds transactions and points at the
  previous block by its hash.
- **Transaction (tx)**: a record of value moving between addresses.
- **Hash**: a short, fixed-size fingerprint of some data; used to name and link
  blocks.
- **Node**: the program that validates and serves the chain (Cardano's is
  `cardano-node`).
- **Indexer**: a follower that copies chain data into a queryable database.
- **Rollback / reorg**: the node discarding recent blocks and asking followers to
  undo them and follow a different version of the chain.
- **Tip**: the newest block of the chain.
- **Coverage gate**: a rule that fails the build if any tested line is left
  unrun; ours is set to 100 percent for the core engine.

## Commit and tag

```bash
git add -A
git commit -m "chore(ch00): scaffold the project and tooling"
git tag ch00
```

## Next up

[Chapter 01 - The block and chain model](../01-block-and-chain-model/): we write
the small set of Python types that represent a block, a transaction, and a point
on the chain, and we learn how blocks link into a chain by their hashes.
