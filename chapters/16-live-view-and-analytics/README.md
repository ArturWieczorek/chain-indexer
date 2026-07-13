# Chapter 16 - Live view and analytics

> **Goal:** show what is happening, not just what happened. The follower publishes
> events to an event bus; a WebSocket streams them to the browser; a small
> dashboard tracks blocks and transaction volume - and a reorg visibly rolls the
> state back in front of you.

The explorer is a pull model: you ask, it answers. A live view is a push model:
the server tells you the moment something changes. This chapter adds that, and
with it the fourth and final design seam - the event bus.

## The event bus

As the follower applies each block, it announces what it did. We model that with a
tiny publish/subscribe bus:

```python
class EventBus:
    def subscribe(self)   -> asyncio.Queue   # a consumer gets its own queue
    def unsubscribe(self, queue)
    def publish(self, event)                 # drop the event into every queue
```

The follower takes an optional bus. On a roll-forward it publishes the events a
block implies; on a roll-backward it publishes a **retraction**:

```python
if isinstance(event, RollForward):
    self._store.apply_block(event.block)
    for e in describe_block(event.block):
        self._bus.publish(e)
else:
    removed = self._store.rollback_to(target)
    self._bus.publish({"type": "rollback", "removed": removed, "count": len(removed)})
```

`describe_block` is a pure function that turns a block into its events: one
`block` event, then a `pool_registered`, `stake_delegated`, `drep_registered`,
`gov_action_proposed`, or `vote_cast` event for each thing inside it. Because it
is pure, we can test that a governance-heavy block produces exactly the right
stream. This is the "emit an event when a pool registers or an action is proposed"
capability, falling straight out of the indexer we already have.

## Streaming to the browser

A WebSocket is a two-way, always-open connection - unlike a normal HTTP request,
the server can send whenever it likes. The `/stream` endpoint subscribes to the
bus and forwards every event to the connected browser:

```python
@app.websocket("/stream")
async def stream(websocket):
    await websocket.accept()
    queue = bus.subscribe()
    while True:
        await websocket.send_json(await queue.get())
```

Because the follower and the web server run in one process on one event loop, the
follower's `publish` and this endpoint's `queue.get` are on the same loop - so the
hand-off is just a queue, with no locks or threads. `make live` starts both
together; we verified end to end that a published block event and a published
rollback event both arrive over the socket.

## The dashboard

`/live` is a single page that opens the WebSocket and renders events as they
arrive:

- **stat tiles**: blocks seen, transactions seen, certificates and votes,
  rollbacks;
- **a sparkline**: transactions per recent block, so a busy stretch is visible at
  a glance;
- **a live feed**: every event, newest on top, colour-coded by type.

And the payoff of the whole project: when a reorg happens, a **rollback** event
arrives and is highlighted in red in the feed, with the rolled-back block hashes.
You watch the chain change its mind, live. Chapter 17 triggers exactly that on
purpose.

## Why the plumbing is not unit-tested

The WebSocket handler and the combined follower-plus-server runner need a live
event loop and a real node, so they carry `# pragma: no cover`, like the Ogmios
and node clients. What *is* tested: the event bus (subscribe, publish, unsubscribe),
`describe_block` (every event type), the follower publishing through the bus
(including the rollback event), and that the `/live` page and the API serve
correctly. The logic is covered; only the socket plumbing is not.

## Test first (red), make it pass (green)

Tests cover the bus delivering and stopping delivery after unsubscribe,
`describe_block` on a rich block, a follower publishing a full event stream ending
in a rollback, and the `/live` page serving with the API still mounted. `make
check` stays green and fully covered.

## What we built

- `chainidx.event`: the `EventBus` and `describe_block` (the event seam).
- The follower publishing forward events and rollback retractions.
- `chainidx.live`: a `/stream` WebSocket and a `/live` dashboard page.

## Glossary

- **Event bus**: a publish/subscribe mechanism decoupling producers from
  consumers.
- **WebSocket**: a persistent two-way connection; the server can push at any time.
- **Retraction event**: a message saying earlier events were undone by a rollback.
- **Sparkline**: a tiny inline chart showing a trend.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch16): add the event bus and live WebSocket dashboard"
git tag ch16
```

## Next up

[Chapter 17 - A real cluster and forced reorgs](../17-a-real-cluster-and-reorgs/):
we bring up a cardonnay cluster, deliberately cause a reorg, and watch the indexer
and the live view roll back correctly - the hardest thing this project does,
proven against a real, misbehaving-on-purpose node.
