# Chapter 17 - A real cluster and forced reorgs

> **Goal:** prove the hardest thing this project does against a real node. Bring up
> a local cluster, make the node send a genuine rollback, and watch the indexer
> rewind and re-index to exactly the same state.

Chapter 05 proved rollback correctness against synthetic chains. Chapters 09 and
12 followed a real chain. This chapter joins the two: a real node issues a real
`RollBackward`, and we verify the indexer obeys it correctly.

## The test rig: cardonnay

[cardonnay](https://github.com/mkoura/cardonnay) spins up a real Cardano cluster
locally - one or more `cardano-node` processes exposing the same node-to-client
socket that mainnet nodes expose. That is the ideal rig: real nodes, real
protocol, but ours to poke at.

```bash
cardonnay create -t conway_fast          # start a local Conway cluster
source <(cardonnay control print-env -i 0)   # sets CARDANO_NODE_SOCKET_PATH
```

Now our `NodeSource` can connect to `$CARDANO_NODE_SOCKET_PATH` and follow the
chain, exactly as the integration tests in earlier chapters did.

## Why a real fork is hard to stage

A rollback happens when the network briefly holds two competing chains and then
discards one. To *force* that, you need two block producers that cannot see each
other for a moment - a network partition - and then reconnect. A healthy local
cluster, with all its pools on localhost talking freely, simply agrees with
itself. So we rarely see a deep reorg by just watching it. (You can still catch
the occasional one-block slot battle at the tip, which our follower handles
silently.)

## Forcing a genuine rollback anyway

There is a reliable way to make the real node send us a `RollBackward` on demand,
and it uses the chain-sync protocol exactly as designed. When a client reconnects
and asks to resume from an earlier point, the node replies by rolling the client
back to that point. So:

```
  1. Follow the chain to height N.
  2. Reconnect and FindIntersect at height N-10 (a point we already have).
  3. The node's first reply is RollBackward to N-10  <-- a real node-issued rollback.
  4. Apply it: the store deletes blocks N-9..N and rewinds balances.
  5. Re-index forward from N-10 back up to N.
  6. Check the tip hash is identical to the original.
```

This is not an adversarial fork, but it is a real rollback message from a real
node, exercising the exact code path a reorg would - the mux, the chain-sync
parser, and the store's `rollback_to`. And step 6 is the strong claim: after
rewinding ten real blocks and re-indexing them, we land on the **same tip hash**,
so the rollback left no residue. It is chapter 05's property test, now against a
live node.

Run against a cluster, the drill reports exactly that: follow to height 198, force
a rollback of ten blocks to height 188, re-index, and recover the identical tip.

## Watching it live

Point `make live` at the cluster and open `/live`. As the drill (or a natural slot
battle) rolls the chain back, a **rollback** event arrives over the WebSocket and
is highlighted in red in the feed, listing the discarded block hashes. The reorg
is not just handled correctly in the database - you can watch it happen.

## The integration test

`tests/test_reorg_integration.py` codifies the drill: follow, force the rollback,
assert the tip dropped, re-index, and assert the recovered tip hash equals the
original. It is marked `integration` and skips unless a node socket is present, so
it never runs in CI - but run against a cardonnay cluster it passes, which is the
proof that the reorg engine works end to end against a real node.

## What we did

- Used cardonnay as a real, local test rig.
- Forced a genuine node-issued `RollBackward` via chain-sync re-intersection.
- Verified the indexer rewinds and re-indexes to a byte-identical tip.
- Watched the rollback stream to the live dashboard.

## Glossary

- **cardonnay**: a tool that runs a local Cardano cluster for testing.
- **Slot battle**: two blocks forged at the same height; one is later dropped, a
  natural small reorg.
- **Network partition**: producers temporarily unable to see each other; the way
  a deep fork is staged.
- **Re-intersection**: reconnecting and resuming from an earlier point, which
  makes the node roll the client back.

## Commit and tag

```bash
git add -A
git commit -m "test(ch17): force a real reorg on a cluster and verify recovery"
git tag ch17
```

## Next up

[Chapter 18 - Design and tradeoffs](../18-design-and-tradeoffs/): we step back and
compare what we built to cardano-db-sync and Dolos - what we index and what we do
not, the ledger-state boundary, the shortcuts we took, and where a real deployment
would go next.
