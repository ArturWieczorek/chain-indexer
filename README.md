# chain-indexer

[![CI](https://github.com/ArturWieczorek/chain-indexer/actions/workflows/ci.yml/badge.svg)](https://github.com/ArturWieczorek/chain-indexer/actions/workflows/ci.yml)

A mini Cardano chain indexer, done seriously.

This is "cardano-db-sync, but tiny and mine": a program that follows a Cardano
chain, indexes its blocks and transactions into a database, and - the genuinely
hard part - **undoes that indexed state correctly when the chain reorganizes**.
On top of the engine sit a REST query API, a command-line tool, and a browsable
block explorer with a live view.

It is also a step-by-step, test-driven **course**. You start from a plain
description of a block and finish with a running indexer that talks to a real
`cardano-node` over a wire protocol you wrote yourself, backfills a database,
serves an explorer, and rolls back cleanly when the chain forks underneath it.

Every chapter is a git tag (`ch00`, `ch01`, ...) and has its own `README.md`
under [`chapters/`](chapters/). If you read the chapters in order and check out
each tag, the git history itself becomes the lesson plan.

## What it is (in one picture)

```
      a Cardano node                    chain-indexer                    you
   (the source of truth)         (a faithful, reorg-aware follower)
          |                                                             |
          |  "here is the next block"   +----------------------+       |
          |  (RollForward) ------------>|  decode the block    |       |
          |                             |         |            |       |
          |                             |         v            |       |
          |                             |  [ indexers ]        |       |
          |                             |  outputs / certs /   |       |
          |                             |  governance ...      |       |
          |                             |         |            |       |
          |                             |         v            |       |
          |                             |  SQLite (the index)  |--REST->|  API + CLI
          |                             |         |            |       |
          |  "back up to block X!"      |         v            |--WS -->|  explorer
          |  (RollBackward) ----------->|  ROLL BACK the index |       |  (live view)
          |                             +----------------------+       |
```

The node sends two kinds of message. `RollForward` hands over the next block, and
the indexer writes it down. `RollBackward` says "the last few blocks were not
final, throw them away and follow this other version instead" - and the indexer
must undo exactly the right rows. Those two messages come from the same place:
the **chain-sync mini-protocol**. The hardest sub-problem (correct rollback) and
the most impressive sub-problem (implementing the wire protocol) turn out to be
the same problem, which is what makes this a good project.

## The reorg story, in one line

The chain-sync protocol hands you a `RollBackward` message; the storage engine's
job is to rewind the indexed state to that point without corrupting it. That is
the whole game, and it is [chapter 05](chapters/05-rollbacks-and-reorgs/).

## Where this sits in the real world

The professional-grade versions of this idea are
[cardano-db-sync](https://github.com/IntersectMBO/cardano-db-sync) (the reference
Postgres indexer) and [Dolos](https://github.com/txpipe/dolos) (a lightweight
"Cardano data node"). This project is a teaching-sized cousin: small enough to
read in an afternoon, honest about what it does and does not do. The REST API
takes its endpoint shapes from [Blockfrost](https://blockfrost.io); the database
schema is a simplified subset of db-sync's tables.

## What it indexes

Everything that arrives on-chain in blocks and transaction bodies, all
reorg-aware:

- blocks and transactions;
- transaction outputs and inputs, native assets, and a derived address-balance view;
- Shelley staking declarations (stake registration, delegation, pool registration);
- Conway governance (DReps, votes, governance actions, committee and constitution).

It does **not** compute ledger-state-derived numbers (reward amounts, live stake
distribution). Those are not in blocks - db-sync derives them from ledger state,
which is deliberately out of scope for v1. See
[chapter 18](chapters/18-design-and-tradeoffs/) for the full boundary.

## The course

| Chapter | Title | What you build |
| ------- | ----- | -------------- |
| [00](chapters/00-orientation/) | Orientation | Scaffold, tooling, the mental model |
| [01](chapters/01-block-and-chain-model/) | The block and chain model | The domain types and how blocks link up |
| [02](chapters/02-the-fork-problem/) | The fork problem | Detect a fork, find the rollback point |
| [03](chapters/03-sqlite-schema-and-store/) | SQLite schema and store | The `Store` interface and the schema |
| [04](chapters/04-indexing-transactions/) | Indexing transactions | Outputs, inputs, assets, address balances |
| [05](chapters/05-rollbacks-and-reorgs/) | Rollbacks and reorgs | The headline: undo indexed state correctly |
| [06](chapters/06-shelley-staking/) | Shelley staking | Index stake and pool certificates |
| [07](chapters/07-conway-governance/) | Conway governance | Index DReps, votes, governance actions |
| [08](chapters/08-a-source-and-ogmios/) | A source and the Ogmios client | First real data end to end |
| [09](chapters/09-the-sync-loop/) | The sync loop | Follow the tip, resume, stay consistent |
| [10](chapters/10-cbor-and-real-blocks/) | CBOR and real blocks | Decode real Cardano blocks |
| [11](chapters/11-ouroboros-wire-mux-handshake/) | Ouroboros wire I | Mux framing and the handshake, by hand |
| [12](chapters/12-ouroboros-wire-chain-sync/) | Ouroboros wire II | Chain-sync by hand, replacing Ogmios |
| [13](chapters/13-the-query-api/) | The query API | A Blockfrost-style REST API |
| [14](chapters/14-the-cli/) | The CLI | Query the index from the terminal |
| [15](chapters/15-the-explorer/) | The explorer | A browsable block explorer UI |
| [16](chapters/16-live-view-and-analytics/) | Live view and analytics | New blocks and reorgs, live over WebSocket |
| [17](chapters/17-a-real-cluster-and-reorgs/) | A real cluster | Force a reorg with cardonnay and watch it roll back |
| [18](chapters/18-design-and-tradeoffs/) | Design and tradeoffs | Where this sits next to db-sync and Dolos |
| [19](chapters/19-publish/) | Publish | Tag v1.0.0 |

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
make check
```

`make check` runs the linter, the type checker, and the tests - exactly what CI
runs. It should be green at every chapter tag.

## Run it against a local cluster

The integration path uses [cardonnay](https://github.com/mkoura/cardonnay) to run
a real local Cardano node. Once one is up:

```bash
source <(cardonnay control print-env -i 0)   # sets CARDANO_NODE_SOCKET_PATH

# Follow the chain with our own from-scratch protocol client and index it:
chainidx --db chain.db follow --source node --events 500

# Query it:
chainidx --db chain.db tip
chainidx --db chain.db pools

# Browse it:
CHAINIDX_DB=chain.db make explorer   # explorer at http://127.0.0.1:8000
make live                            # live dashboard at /live
```

The unit tests need none of this - they are fully offline and deterministic. The
integration tests (a real handshake, a follow via Ogmios, a follow via our own
protocol, and a forced rollback) run only when a node socket is present.

## License

MIT. See [LICENSE](LICENSE).
