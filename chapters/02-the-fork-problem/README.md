# Chapter 02 - The fork problem

> **Goal:** hold a chain in memory, refuse a block that does not build on the tip
> (that refusal *is* fork detection), find where two chains diverge, and rewind
> the chain to a chosen point. All with synthetic blocks, no node in sight.

Chapter 01 gave us blocks that know how to link onto a parent. Now we put them in
order and answer the question that separates a real indexer from a naive copy
loop: **when a new block arrives, does it extend my chain, or does it belong to a
fork?** And if it is a fork, *where* do the two chains diverge, so I know how far
to rewind?

## Two chains at the same slot

Recall that the tip of a real chain is not final. Two producers can make blocks
at the same height, and the network briefly disagrees:

```
                                  ... common history ...
                                          |
                                        [ b1 ]
                                        /    \
                                    [ b2 ]   [ b2x ]     <-- a fork: two blocks
                                      |         |            both build on b1
                                    [ b3 ]   [ b3x ]
                                                |
                                             [ b4x ]     <-- the branch that wins
```

If our chain followed `b1 -> b2 -> b3` and the network settles on the right-hand
branch, we must: (1) notice that `b2x` does not build on `b3`, (2) find that both
branches share `b1`, (3) rewind to `b1`, and (4) apply `b2x, b3x, b4x`. This
chapter builds the machinery for exactly those four steps, in memory.

## The `Chain` object

A `Chain` is an ordered list of blocks (oldest first) with a few operations:

| Operation | What it does |
| --------- | ------------ |
| `add_block(b)` | Extend the chain, or raise `ForkError` if `b` does not build on the tip |
| `has_point(p)` | Is point `p` on this chain? |
| `find_intersection(points)` | The newest of `points` that we already have, or `None` |
| `rollback_to(p)` | Rewind to point `p`; return the removed blocks, newest-first |
| `points()` | All our points, newest-first |

### Fork detection is just a refusal

`add_block` does the smallest possible thing: if the chain is not empty and the
new block does not `links_onto` the tip, it raises `ForkError`. There is no
cleverness here on purpose. "This block does not fit on my tip" is the signal;
deciding what to do about it (roll back and switch branches) is the caller's job,
and later the node tells us directly via a rollback message.

### Finding the divergence point

`find_intersection` walks a list of candidate points and returns the first one it
recognizes. Because callers offer points newest-first, the first match is the
newest shared point - precisely where the two branches diverge. This is the same
question the chain-sync protocol asks in chapter 12, so we are building its
vocabulary now:

```python
def find_intersection(self, candidates):
    for point in candidates:
        if point in self._points:
            return point
    return None
```

### Rewinding, newest-first

`rollback_to(point)` keeps every block up to and including `point` and returns
the rest **newest-first**:

```python
removed = chain.rollback_to(b2_point)   # -> [b4, b3]  (not [b3, b4])
```

Why newest-first? Because a later block can depend on an earlier one, so the safe
way to undo their effects is to peel from the tip inwards. Right now "undo" just
means dropping items from a list, but in chapter 05 the removed blocks drive
*database* deletions, and that leaf-first order becomes essential.

`rollback_to(None)` means "back to the origin" and empties the chain.

## Test first (red)

The tests describe each behaviour, then a final one walks the whole fork
scenario end to end using only `Chain` methods:

```python
def test_a_block_that_does_not_link_onto_the_tip_is_rejected() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"))
    with pytest.raises(ForkError):
        chain.add_block(block(3, "b3", "does_not_match_b2"))


def test_rollback_to_a_point_drops_the_blocks_after_it() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"), ("b4", "b3"))
    removed = chain.rollback_to(block(2, "b2", "b1").point)
    assert [b.block_hash for b in removed] == ["b4", "b3"]   # newest-first
```

## Make it pass (green)

`src/chainidx/chain.py` keeps two things in sync: the ordered `_blocks` list and
a `_points` set for fast membership tests. Every method above is a few lines. Run
`make check`; it stays green and fully covered.

## What we built

- A `Chain` that extends, detects forks, finds intersections, and rewinds.
- A `ForkError` that names the moment a block does not fit.
- The newest-first rewind order that chapter 05 will depend on.

Notice what is *not* here: no database, no node, no async. Fork logic is subtle,
so we isolate it where it is trivial to test. When we meet a real, messy node in
chapter 08, this logic is already proven.

## Glossary

- **Fork / branch**: two different blocks built on the same parent; the chain
  temporarily has two possible futures.
- **Intersection**: the newest point two chains share; where they diverge.
- **Rollback / rewind**: dropping blocks from the tip back to a chosen point.
- **Origin**: the position before any block; rolling back to it empties the
  chain.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch02): add the in-memory chain and fork logic"
git tag ch02
```

## Next up

[Chapter 03 - SQLite schema and store](../03-sqlite-schema-and-store/): we give
the indexer a real place to keep data. We design a small relational schema
(modelled on cardano-db-sync) behind a `Store` interface, so the storage backend
can be swapped later without touching the rest of the code.
