# Chapter 20 - Local-state-query

> **Goal:** read data the chain does not carry in its blocks - the current epoch,
> protocol parameters, and the live stake distribution across pools - by
> hand-writing a second node-to-client mini-protocol: local-state-query.

Everything up to now came from chain-sync: blocks, transactions, certificates,
governance. But some of the most-wanted explorer data is not in any block. "How
much live stake does this pool control?" and "what are the current protocol
parameters?" are answers the node *computes* from the whole ledger. To read them
we speak a different mini-protocol, **local-state-query** (LSQ). This chapter is
the from-scratch implementation, and it is the start of growing the project toward
a cardanoscan-style explorer.

## The on-chain vs ledger-state line (revisited)

Back in chapter 06 we drew a line: on-chain declarations (who delegated to whom)
versus ledger state (how much stake that adds up to). Chain-sync gives us the left
column; LSQ gives us the right one:

```
  ON-CHAIN (chain-sync, chapters 08-12)   LEDGER STATE (LSQ, this chapter)
  -------------------------------------   -------------------------------
  "alice delegated to pool1"              "pool1 controls 12.4% of live stake"
  "pool1 registered, 3% margin"           the current protocol parameters
  block/tx/cert/governance records        the current epoch number
```

This chapter closes the single biggest gap in the project.

## The protocol: acquire, query, release

LSQ is a small state machine on mini-protocol id **7**. You **acquire** a
consistent ledger state (a snapshot at a point), run one or more **queries**
against it, then **release**:

```
  us -> node:  [8]            MsgAcquire   (acquire the volatile tip)
  node -> us:  [1]            MsgAcquired
  us -> node:  [3, query]     MsgQuery
  node -> us:  [4, result]    MsgResult
  us -> node:  [5]            MsgRelease
```

Acquiring pins the ledger at one moment so a batch of queries all see the same
state. We reuse the mux framing (chapter 11) and the handshake (chapter 11) and
just add protocol id 7 - the connection machinery is already built.

## The fiddly part: era-wrapped queries

Simple queries are trivial. `GetSystemStart` is just `[3, [1]]`. But a *ledger*
query (epoch, stake distribution, params) is wrapped twice by the **hard-fork
combinator**, the layer that lets one node speak every past era:

```
  MsgQuery = [3, [0, [0, [era, shelley_query]]]]
                  |    |    |    |
                  |    |    |    +-- the era-specific query, e.g. [1] = GetEpochNo
                  |    |    +-- era index: 6 = Conway
                  |    +-- "the current era" (QueryIfCurrent)
                  +-- "this is a block query"
```

The era index matters: query the wrong era and the node does not error, it returns
an *era-mismatch* result telling you which era it actually is. That is a friendly
design, but it means you must send the right era (6, Conway) to get real data.

As with chain-sync, these shapes were **confirmed by probing a live node**, not
guessed. The probe brute-forced candidate encodings until `GetEpochNo` returned
the real epoch, then the same wrapper worked for every other ledger query.

## The queries we implement

| Query | Shelley tag | Result |
| ----- | ----------- | ------ |
| `GetEpochNo` | `[1]` | the current epoch |
| `GetSystemStart` | (consensus, `[1]`) | `[year, day-of-year, picoseconds]` |
| `GetCurrentPParams` | `[3]` | positional protocol parameters |
| `GetStakeDistribution` | `[5]` | `{pool_id: [stake_fraction, vrf]}` - the headline |
| `GetStakePools` | `[16]` | the set of registered pool ids |

`GetStakeDistribution` is the one that unlocks "live stake" and, later,
saturation. System start unlocks converting a slot to a wall-clock time (chapter
21's dashboard needs that).

## Pure codec, socket client (same split as before)

- `statequery.py` (PURE, 100% covered): build the messages and parse the results.
  Tested against **result fixtures captured from a live node** (`tests/fixtures/
  lsq_*.cbor`), the same approach as the CBOR block fixtures.
- `localstate.py` (INTEGRATION, omitted from coverage like `ogmios.py`/`node.py`):
  `LocalStateClient` - open the socket, handshake, acquire, run the batch,
  release, and return a `LedgerSnapshot`.

> **A real-world wrinkle: retries.** A local cluster forges blocks *fast*, so the
> volatile tip we acquired can be superseded mid-batch and the node drops the
> connection. `snapshot` retries a few times. This is not a bug in our code; it is
> what querying a busy node's volatile state looks like, and handling it is part
> of doing the protocol properly.

## Seeing it work: `chainidx state`

The new CLI command reads and prints a snapshot:

```text
$ chainidx state
epoch:        77
system start: 2026-07-13T20:36:52+00:00
protocol params:
  min_fee_a: 44
  min_fee_b: 155381
  key_deposit: 400000
  pool_deposit: 500000000
  coins_per_utxo_byte: 4310
stake pools:  3
live stake distribution:
  03624db0b2d5d18e...  0.0153%
  89329854187a1297...  0.0153%
  6887684e60a31bf8...  0.0153%
```

Every number there was computed by the node's ledger and read over a protocol we
wrote from scratch. The epoch matches `cardano-cli query tip`; the three pools are
the cluster's real pools.

## Test first (red), make it pass (green)

Unit tests cover every message builder and every result parser against the
captured fixtures, plus the CLI's `format_state` renderer. The live path is an
opt-in integration test that reads a real snapshot and checks the epoch, params,
and the three pools. `make check` stays green and fully covered.

## What we built

- `chainidx.statequery`: the pure LSQ codec (acquire/query/release + parsers).
- `chainidx.localstate.LocalStateClient`: the socket client, with retries.
- `LedgerSnapshot` / `PoolStake` models and a `chainidx state` CLI command.

## Glossary

- **Local-state-query (LSQ)**: the mini-protocol for reading the node's computed
  ledger state.
- **Acquire / release**: pin a ledger snapshot for a batch of queries, then let
  it go.
- **Hard-fork combinator**: the consensus layer that speaks every era; it wraps
  ledger queries with an era index.
- **Live stake distribution**: each pool's share of the total active stake -
  ledger state, not on-chain.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch20): hand-write local-state-query for ledger state"
git tag ch20
```

## Next up

[Chapter 21 - Epochs and the dashboard](../21-epochs-and-dashboard/): with system
start in hand we can turn slots into times, aggregate per-epoch stats from the
blocks we index, and build a cardanoscan-style landing page - current epoch with a
progress bar, latest blocks and transactions, and network totals.
