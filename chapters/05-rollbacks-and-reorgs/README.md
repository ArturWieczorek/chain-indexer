# Chapter 05 - Rollbacks and reorgs

> **Goal:** make the database obey when the node says "back up to block X".
> Delete exactly the rows that belonged to the discarded blocks, in an order the
> database will accept, and restore the outputs those blocks had spent - all in
> one transaction. This is the chapter the whole project was built around.

Every chapter so far was, in a sense, preparation for this one. We isolated fork
logic in memory (chapter 02), gave every table a `block_id` (chapters 03 and 04),
and tracked spends by setting a column instead of deleting a row (chapter 04).
Because of those choices, the reorg engine is short. That is the point: correct
rollback is hard, so we spent four chapters making it easy.

## Why rollbacks happen (and why they are normal)

The tip of a Cardano chain is not final. Two block producers can forge a block at
the same height at nearly the same time - a **slot battle** - and the network
briefly holds two versions of history. Consensus soon picks one and discards the
other. When the block you copied turns out to be on the losing side, the node
tells you: *"back up to block X and follow this other version instead."*

```
                       ... common history ...
                               |
                             [ b1 ]  <--- roll back to here
                             /    \
                         [ b2 ]   [ b2x ]
                           |         |
                         [ b3 ]   [ b3x ]      the node switches us
                        (we had     |          from the left branch
                         these)   [ b4x ]      to the right one
```

A rollback is **not an error**. Near the tip it happens routinely, usually only 0
or 1 block deep. A block becomes practically permanent only once about 2160 more
blocks sit on top of it (Cardano's security parameter `k`). Until then, any block
can be replaced, and a faithful follower must be ready to undo it.

## The two hard sub-problems are one problem

Here is the elegant bit that makes this a good portfolio project. The message
that triggers a rollback (`RollBackward`, which we meet for real in chapters 08
and 12) and the machinery that undoes the database are the *same problem viewed
from two ends*. The protocol hands you a point; the storage engine rewinds to it.
Get both right and you have written the interesting half of a chain indexer.

## What "undo a block" actually means

Two things must happen, and their order is forced by the foreign keys we turned on
in chapter 03.

**1. Restore the outputs the removed blocks spent.** Suppose block 1 gave Alice 5
ada and block 2 spent it. If we roll back block 2, Alice's output must become
unspent again. Because we recorded a spend by setting `consumed_by_tx_id` (not by
deleting anything), undoing it is a single update:

```sql
UPDATE tx_out SET consumed_by_tx_id = NULL
WHERE consumed_by_tx_id IN (SELECT id FROM tx WHERE block_id > :target)
```

This has to run *first*. Those surviving outputs point at transactions we are
about to delete; if we deleted the transactions first, the foreign key would
refuse (or, worse, without foreign keys, leave a dangling reference).

**2. Delete the removed blocks' rows, leaf-first.** A child row must go before its
parent, or the foreign key blocks the delete:

```
  ma_tx_out   ->   tx_out   ->   tx   ->   block
  tx_in       ------------------/
  (delete in this order: children before parents)
```

```python
for table in ("ma_tx_out", "tx_out", "tx_in", "tx"):
    conn.execute(f"DELETE FROM {table} WHERE block_id > :target")
conn.execute("DELETE FROM block WHERE id > :target")
```

> **The foreign keys are a feature, not a nuisance.** If you get the order wrong,
> SQLite raises instead of silently corrupting the database. The delete order is
> not something you have to remember; the schema enforces it. This is exactly why
> chapter 03 turned foreign keys on.

Everything runs inside one `with self._conn:` transaction, so a crash halfway
through leaves the database exactly as it was, not half-rewound.

## Generic by design

Notice what the engine does *not* mention: staking, governance, or any specific
table beyond a hardcoded list. It deletes "everything with `block_id` greater than
the target". When we add stake and governance tables in chapters 06 and 07, they
will carry a `block_id` like everything else, and rolling them back is a matter of
adding their names to that delete loop. New data rolls back almost for free. That
is the first design seam paying off.

## The test that matters

Any single deletion is easy to get right. The property that actually proves
correctness is this: **after a reorg, the database must be identical to one that
only ever saw the winning branch.** No leftover rows, no stale spends, no
leaked balances. So the headline test builds two stores:

```python
# Store A: sees the losing branch, then reorgs to the winning branch.
reorged.apply_block(b1)
for b in losing:  reorged.apply_block(b)
reorged.rollback_to(b1.point)
for b in winning: reorged.apply_block(b)

# Store B: only ever saw the winning branch.
clean.apply_block(b1)
for b in winning: clean.apply_block(b)

# They must agree on every balance and on the tip.
for who in ["alice", "bob", "carol", "dave", "erin"]:
    assert reorged.balance(who) == clean.balance(who)
assert reorged.block_count() == clean.block_count()
```

If the rollback left any residue behind, these two would disagree. They do not.

## Test first (red), make it pass (green)

The other tests pin down each behaviour individually: blocks after the point
disappear, a spent output is restored, rolling back to the origin empties
everything, rolling back to an unknown point is an error, and a removed block's
native assets are deleted. `rollback_to` is about twenty lines. `make check`
stays green and fully covered.

## What we built

- `SqliteStore.rollback_to(point)`: the reorg engine, in one transaction.
- Un-consume-then-delete-leaf-first, an order the foreign keys enforce for us.
- A generic design that new index tables plug into.
- A property test proving a reorg leaves no trace of the losing branch.

## Glossary

- **Reorg / rollback**: the node discarding recent blocks and switching branches.
- **Slot battle**: two blocks forged at the same height; one is later discarded.
- **`k` (security parameter)**: about 2160 blocks; how deep a block must be buried
  to be considered final on Cardano.
- **Leaf-first deletion**: deleting child rows before parent rows so foreign keys
  stay satisfied.
- **Un-consume**: clearing `consumed_by_tx_id` so a previously spent output counts
  as unspent again.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch05): add the reorg engine (reorg-aware rollback)"
git tag ch05
```

## Next up

[Chapter 06 - Shelley staking](../06-shelley-staking/): the first new indexer to
ride on this engine. We index stake address and pool certificates from
transaction bodies, they roll back for free, and we draw the honest line between
what is on-chain (certificates) and what needs ledger state (reward amounts).
