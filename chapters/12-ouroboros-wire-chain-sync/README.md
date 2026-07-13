# Chapter 12 - Ouroboros wire II: chain-sync

> **Goal:** finish the wire protocol. Drive the chain-sync mini-protocol - find an
> intersection, request blocks, receive roll-forwards and roll-backwards - and
> assemble a `NodeSource` that satisfies the same `ChainSource` interface as
> Ogmios. Then point the follower at it and delete Ogmios from the pipeline.

This is the chapter the README brags about: *originally built on Ogmios, then
rebuilt on my own from-scratch implementation of the Ouroboros chain-sync
mini-protocol.* Everything is in place - the mux, the handshake, the CBOR decoder.
Chain-sync ties them together.

## The chain-sync state machine

Chain-sync is a small conversation. After the handshake, we and the node exchange
these CBOR messages:

```
  us -> node:  [4, [point, ...]]   MsgFindIntersect   "do we share any of these?"
  node -> us:  [5, point, tip]     MsgIntersectFound
  node -> us:  [6, tip]            MsgIntersectNotFound

  us -> node:  [0]                 MsgRequestNext      "give me the next block"
  node -> us:  [1]                 MsgAwaitReply       "wait, nothing new yet"
  node -> us:  [2, block, tip]     MsgRollForward      "here is the next block"
  node -> us:  [3, point, tip]     MsgRollBackward     "back up to this point"
```

A point on the wire is `[slot, hashBytes]`, or the empty array `[]` for the
origin. A block inside `MsgRollForward` is the tag-24 wrapper we decode with
chapter 10's decoder.

Notice these are exactly the same two events - roll forward, roll backward - that
Ogmios reported as JSON in chapter 08. Same protocol underneath; we are just
speaking it directly now instead of through a translator.

## Pure messages, thin plumbing (again)

We keep the same split that made the Ogmios client testable:

- `chainsync.py` - **pure**: build `MsgFindIntersect` and `MsgRequestNext`, and
  parse the replies into `Point`/`Origin` or `RollForward`/`RollBackward`. Fully
  unit-tested, including parsing a real captured block into a roll-forward event.
- `node.py` - the `NodeSource`: opens the socket, handshakes, and runs the
  request/reply loop. Socket-bound, so excluded from the coverage gate and covered
  by the integration test.

### The await-reply loop

One subtlety: after `MsgRequestNext`, the node may answer immediately with a block,
or reply `MsgAwaitReply` meaning "I have nothing new; I will send it when I do."
When caught up at the tip, that is the normal reply. So `next_event` sends one
request and then reads until it gets an actual roll message:

```python
await mux.send(CHAIN_SYNC, encode(request_next_message()))
while True:
    event = parse_next_reply(await mux.receive(CHAIN_SYNC))
    if event is not None:
        return event
    # MsgAwaitReply: keep reading; the node will push the block when ready.
```

That is what makes a follower *follow* - it blocks at the tip and wakes when a new
block is forged.

## Deleting Ogmios

`NodeSource` implements `find_intersection`, `next_event`, and `close` - the whole
`ChainSource` interface. So the chapter 09 follower drives it with **no changes**:

```python
source = NodeSource(socket_path, network_magic=42)   # was OgmiosSource(url)
follower = Follower(source, store)
await follower.run()
```

That one-line swap is the reward for defining the interface back in chapter 08.

## Proven equal to Ogmios

The integration test points the follower at a `NodeSource` and follows a real
cardonnay cluster. Run side by side with the Ogmios path over the same 800 events,
the two agree exactly: the same block count, the same tip height, the same three
stake pools, the same five DReps. Our from-scratch protocol implementation is not
a toy that limps along - it reproduces the reference bridge's results to the row.

## Test first (red), make it pass (green)

Unit tests cover point encoding (including the origin), the message builders,
parsing both intersect replies, and parsing roll-forward (against a real block),
roll-backward, and await-reply. `make check` stays green and fully covered; the
live follow is an opt-in integration test.

## What we built

- `chainidx.chainsync`: the pure chain-sync message layer.
- `chainidx.node.NodeSource`: a `ChainSource` that speaks to the node directly.
- The Ogmios-to-own-protocol swap, behind one unchanged interface.

**Phase 1.5 is complete.** We can index a Cardano chain with no dependency but the
node itself.

## Glossary

- **chain-sync**: the mini-protocol for following a chain.
- **Intersection**: the shared point two chains agree to resume from.
- **MsgAwaitReply**: the node's "nothing new yet, I will send when ready".
- **Roll forward / roll backward**: the two chain-sync events; the same ones Ogmios
  reported in chapter 08.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch12): hand-write chain-sync and replace Ogmios"
git tag ch12
```

## Next up

[Chapter 13 - The query API](../13-the-query-api/): with a database full of indexed
data, we expose it. A Blockfrost-style REST API over FastAPI serves blocks,
transactions, addresses, assets, pools, and governance - the read side that the
CLI and the explorer will both use.
