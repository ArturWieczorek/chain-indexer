# Chapter 01 - The block and chain model

> **Goal:** write the small set of Python types that represent a block, a
> transaction, and a position on the chain. By the end you can build a block in
> code, ask it for its "point", and check whether one block links onto another.

Everything in this project reads or writes a handful of data types. Before we can
index anything, follow a node, or handle a rollback, we need those types. This
chapter is pure data modelling: no I/O, no database, no network. That makes it
the easiest chapter to test, so it is a good place to get comfortable with the
test-first rhythm.

## The shapes we need

Recall the picture from chapter 00: a chain is a list of blocks, each pointing
back at the previous one, and each block holds transactions that move value
between addresses. Let us turn each noun in that sentence into a type.

```
  Block
  +-- block_no   (height: 0, 1, 2, ...)
  +-- slot_no    (when it was made)
  +-- block_hash (this block's fingerprint)
  +-- prev_hash  (the parent's fingerprint)  <--- the link that makes a chain
  +-- txs
        +-- Tx
              +-- inputs   (TxIn: "spend output #i of transaction X")
              +-- outputs  (TxOut: "send this value to this address")
                              +-- lovelace  (ada, in millionths)
                              +-- assets    (Asset: native tokens)
```

Two more types describe *positions* rather than contents:

- **Point** = `(slot_no, block_hash)`. A slot number is not enough on its own,
  because a fork can place two blocks at the same slot; adding the hash makes a
  position unambiguous. Points are the vocabulary the chain-sync protocol uses.
- **Tip** = the newest block the node has: a `Point` plus a height. The node
  tells us its tip so we can see how far behind we are.

## Why frozen dataclasses

A Python `dataclass` turns a class into a plain record: you declare the fields
and it writes the boilerplate (constructor, equality, `repr`) for you. If you
know Python's `namedtuple`, it is the same idea with types and defaults.

We mark them `frozen=True`, meaning immutable - you cannot change a field after
the value is created. That matches reality (a produced block never changes) and
buys us three things:

1. **Safety**: nothing can mutate a block by accident deep inside the indexer.
2. **Value equality**: two blocks with identical fields are equal, which makes
   tests read naturally.
3. **Hashability**: immutable values can go in a `set` or be dict keys. We rely
   on this in chapter 02, where we find the common point between two chains by
   putting points in a set.

> **Python note.** `from __future__ import annotations` at the top lets a method
> mention its own class (`Block`) in a type hint without quoting it. `tuple[Asset,
> ...]` means "a tuple of any number of `Asset` values"; we use tuples, not
> lists, because tuples are immutable and so keep the whole value frozen.

## Test first (red)

We write the tests before the module exists. A few representative ones:

```python
def test_block_reports_its_point() -> None:
    block = make_block(block_no=7, block_hash="hhh", prev_hash="ggg")
    assert block.point == Point(slot_no=70, block_hash="hhh")


def test_a_block_links_onto_its_parent() -> None:
    parent = make_block(block_no=1, block_hash="b1", prev_hash="b0")
    child = make_block(block_no=2, block_hash="b2", prev_hash="b1")
    assert child.links_onto(parent) is True


def test_model_values_are_immutable() -> None:
    out = TxOut(address="addr", lovelace=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.lovelace = 2  # type: ignore[misc]
```

`from chainidx.model import ...` fails first, because the module does not exist.
That is red.

## Make it pass (green)

Create `src/chainidx/model.py` with the dataclasses. The only real behaviour is
two tiny methods on `Block`:

```python
@property
def point(self) -> Point:
    return Point(slot_no=self.slot_no, block_hash=self.block_hash)

def links_onto(self, parent: Block) -> bool:
    return self.prev_hash == parent.block_hash
```

`point` is a convenience so the rest of the code never rebuilds a point by hand.
`links_onto` is the seed of everything to come: fork detection in chapter 02 is
just "the new block does not link onto the block I thought was the tip".

Run the suite:

```bash
make check
```

All green, and coverage stays at 100 percent because the module is small and
every line has a test.

## What we built

- `Asset`, `TxOut`, `TxIn`, `Tx`, `Block`, `Point`, and `Tip`: the whole
  vocabulary of the project, as immutable records.
- `Block.point` and `Block.links_onto`, the only two behaviours a block needs so
  far.

These types will grow (transactions will gain certificates and votes in chapters
06 and 07), but the core stays this small and this boring, which is exactly what
you want from a data model.

## Glossary

- **Dataclass**: a Python class that is mostly just typed fields; the standard
  library writes the constructor and comparisons for you.
- **Frozen / immutable**: cannot be changed after creation.
- **Hashable**: usable as a set member or dict key; immutable values are.
- **Lovelace**: the smallest unit of ada; 1 ada = 1,000,000 lovelace.
- **Native asset**: any on-chain token other than ada, named by its policy id
  and asset name.
- **Point**: a `(slot_no, block_hash)` pair naming a position on the chain.
- **UTxO**: an unspent transaction output; the set of these is an address's
  spendable balance (chapter 04).

## Commit and tag

```bash
git add -A
git commit -m "feat(ch01): add the block and chain domain model"
git tag ch01
```

## Next up

[Chapter 02 - The fork problem](../02-the-fork-problem/): we put blocks in order,
represent a chain in memory, and answer the question every indexer must answer -
when a new block arrives, does it extend our chain, or does it belong to a fork
that means we have to roll back?
