# Chapter 09 - The sync loop

> **Goal:** connect a source to the store. The follower resumes from where it left
> off, then loops: roll forward means index a block, roll backward means run the
> reorg engine. This small loop is what turns eight chapters of parts into a
> working indexer.

Every previous chapter built a piece. This chapter assembles them. And because
each piece was made correct and testable on its own, the assembly is about forty
lines.

## What the follower does

```
   +----------------------------------------------------------+
   |  Follower(source, store)                                 |
   |                                                          |
   |  1. resume():  offer our recent points -> intersection   |
   |                                                          |
   |  2. loop:      event = await source.next_event()         |
   |                  RollForward(block) -> store.apply_block  |
   |                  RollBackward(point) -> store.rollback_to |
   |                                                          |
   |  3. stats:     applied, rolled_back, events              |
   +----------------------------------------------------------+
```

That is the entire indexer. The reorg handling that took the whole of chapter 05
is one line here: `store.rollback_to(...)`. The staking and governance indexing
from chapters 06 and 07 happen automatically inside `apply_block`. The follower
just routes events.

## Resuming: the intersection handshake

When the follower starts, the database may already hold thousands of blocks. We
must not re-index from scratch. So we ask the source to agree on a resume point:

```python
async def resume(self):
    candidates = [*self._store.recent_points(), ORIGIN]
    return await self._source.find_intersection(candidates)
```

We offer our most recent points, newest first, with `ORIGIN` as the fallback for
an empty database. The source replies with the newest point we both have. Then
the very first event the source sends is a `RollBackward` to that point - the
protocol resets us there - and the loop handles it like any other roll-back. A
fresh database resumes at the origin and rolls forward from block zero; a
populated one resumes at its tip and only indexes what is new.

## Translating "origin"

The source speaks of the pre-genesis position with an `Origin` marker; the store
speaks of it as `rollback_to(None)`. The follower is where the two vocabularies
meet, so it does the one-line translation:

```python
target = None if isinstance(event.point, Origin) else event.point
removed = self._store.rollback_to(target)
```

Keeping each layer's vocabulary natural, and translating at the boundary, is
cleaner than forcing one convention through the whole stack.

## It does not know what a source is

The follower's type is `ChainSource` - the interface. It never mentions Ogmios.
That means the exact same follower will drive our from-scratch wire-protocol
client in chapter 12 with no changes. It also means the tests drive it with a
`FakeSource`: a scripted list of events, no network, fully deterministic. The
reorg test literally scripts "forward, forward, forward, back up to b1, forward
on a new branch" and checks that balances end up correct - the whole reorg story,
exercised through the real loop, in memory.

## Proven on a real chain

The integration test points a `Follower` at live Ogmios and a real `SqliteStore`
and follows a few hundred events. Run against a cardonnay cluster, this indexer
reproduced the cluster's real state exactly: it found the **three** stake pools
the cluster runs, the DReps registered at genesis, and the full ada supply sitting
in unspent outputs. Everything Phase 1 built, working against a real node.

## Running it

`make run` follows a live chain via Ogmios into `chain.db`, printing progress. The
entry point (`chainidx/follow.py`'s `_main`) is marked `# pragma: no cover`
because it needs a live server; the `Follower` logic it calls is fully unit-tested.

## What we built

- `Follower`: resume, loop, and keep stats.
- `Store.recent_points`, so resuming offers the source real candidates.
- A reorg driven end to end through the loop, tested with a `FakeSource`.
- An integration test that follows a real chain into the store.

## Glossary

- **Follower / sync loop**: the component that pulls chain events and applies
  them to the store.
- **Resume / intersection handshake**: agreeing with the source on where to pick
  up, so we do not re-index from scratch.
- **`FakeSource`**: a scripted source for deterministic, offline tests.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch09): add the sync loop (Follower)"
git tag ch09
```

## Next up

[Chapter 10 - CBOR and real blocks](../10-cbor-and-real-blocks/): we begin the
from-scratch wire protocol. Ogmios handed us JSON; the node itself speaks CBOR, a
compact binary format. We learn what CBOR is and decode real Cardano blocks from
their raw bytes, so that in chapters 11 and 12 we can drop Ogmios entirely.
