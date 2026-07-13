# Chapter 19 - Publish

> **Goal:** the finish line. Tidy the README, finalize the changelog, confirm
> `make check` is green across the whole course, and tag `v1.0.0`.

Nineteen chapters ago this was an empty directory. Now it is a reorg-aware Cardano
chain indexer that follows a node over a wire protocol we wrote by hand, indexes
value, staking, and governance into a store that rolls back correctly, and serves
the result as an API, a CLI, and a browsable, live-updating explorer. This chapter
ships it.

## The finishing checklist

- **README**: the one-picture diagram, the reorg story, the landscape (db-sync,
  Dolos, Blockfrost), and a chapter table where every row links to its chapter.
- **CHANGELOG**: an entry per chapter, closed off with a `1.0.0` release.
- **PROGRESS**: every box ticked.
- **`make check`**: green - ruff, mypy strict, and pytest at 100 percent coverage
  on the core, every integration test passing against a real cluster.

## What "done" means here

`make check` is green at **every** chapter tag, not just the last one. Check out
`ch05` and the reorg engine's tests pass; check out `ch12` and the from-scratch
chain-sync tests pass. The git history is not a rough draft that was cleaned up at
the end - it is the course, and each step stands on its own.

The numbers at the finish: around 20 source modules, over 100 tests, 100 percent
coverage on the pure-logic core, and four integration tests that run against a
live cardonnay cluster (a real handshake, a real follow via Ogmios, a real follow
via our own protocol, and a forced rollback with recovery).

## Try it yourself

```bash
make install

# Against a local cluster (cardonnay create -t conway_fast):
source <(cardonnay control print-env -i 0)

chainidx --db chain.db follow --source node --events 500   # index 500 blocks
chainidx --db chain.db tip                                 # see the tip
chainidx --db chain.db pools                               # the cluster's pools

CHAINIDX_DB=chain.db make explorer   # browse at http://127.0.0.1:8000
make live                            # live dashboard at /live
```

## Tag the release

```bash
git add -A
git commit -m "chore(ch19): finalize docs and publish v1.0.0"
git tag ch19
git tag v1.0.0
```

## Thank you for reading

If you followed the whole course, you have written a blockchain wire protocol by
hand, decoded real blocks byte-for-byte, and built a storage engine that undoes
itself correctly when the chain changes its mind. Those are not common skills.
The next steps, if you want them, are in [chapter 18](../18-design-and-tradeoffs/):
ledger state via `local-state-query`, a Postgres backend, and the fuller
certificate and script coverage that a production indexer carries. The seams are
there for all of it.
