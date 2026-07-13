"""The domain model: the small set of types that describe a Cardano chain.

Everything else in this project reads or writes these types, so we keep them
simple, immutable, and free of behaviour that does not belong to the data
itself. They are ordinary Python dataclasses.

Why immutable (``frozen=True``)? A block that has been produced never changes -
if the chain wants a different block, it produces a new one with a new hash. By
freezing these values we get three things for free: they cannot be mutated by
accident, they compare by value (two blocks with the same fields are equal), and
they are hashable (so we can put points in a set when we compare two chains).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Asset:
    """A quantity of a native token (anything that is not ada/lovelace).

    A native asset is identified by the ``policy_id`` (the script that governs
    it) together with the ``asset_name``. On Cardano, ada itself is measured in
    ``lovelace`` (1 ada = 1,000,000 lovelace) and lives directly on the output;
    everything else is a native asset and lives in this list.
    """

    policy_id: str
    asset_name: str
    quantity: int


@dataclass(frozen=True)
class TxOut:
    """A transaction output: value sent to an address.

    An output is a parcel of value (some lovelace, plus zero or more native
    assets) addressed to someone. Until it is spent by a later transaction it is
    "unspent" - part of the UTxO set we will track from chapter 04.
    """

    address: str
    lovelace: int
    assets: tuple[Asset, ...] = ()


@dataclass(frozen=True)
class TxIn:
    """A transaction input: a reference to an earlier output being spent.

    An input does not carry value itself. It names an output to consume by the
    transaction that created it (``tx_id``) and that output's position within
    that transaction (``index``). Following these references backwards is how we
    know an address's balance.
    """

    tx_id: str
    index: int


@dataclass(frozen=True)
class Tx:
    """A transaction: it consumes some inputs and creates some outputs.

    This is a deliberately small view of a Cardano transaction. Real
    transactions also carry certificates, governance votes, metadata, and more;
    we add those fields in later chapters as we start to index them.
    """

    tx_id: str
    inputs: tuple[TxIn, ...] = ()
    outputs: tuple[TxOut, ...] = ()


@dataclass(frozen=True)
class Point:
    """A position on the chain: a slot number plus the block hash at that slot.

    A slot number alone is not enough to name a position, because a fork can put
    two different blocks at the same slot. Pairing the slot with the block hash
    makes a point unambiguous. Points are how the chain-sync protocol says "I am
    here" and "back up to here".
    """

    slot_no: int
    block_hash: str


@dataclass(frozen=True)
class Tip:
    """The newest block the node knows about: its point and its height.

    The node reports its tip alongside every message so a follower can tell how
    far behind it is.
    """

    point: Point
    block_no: int


@dataclass(frozen=True)
class Block:
    """One block in the chain.

    A block has a height (``block_no``), a ``slot_no`` (when it was made), its own
    ``block_hash``, the ``prev_hash`` of the block it builds on, and the
    transactions it carries. The ``prev_hash`` link is what turns a pile of
    blocks into a chain.
    """

    block_no: int
    slot_no: int
    block_hash: str
    prev_hash: str
    txs: tuple[Tx, ...] = field(default=())

    @property
    def point(self) -> Point:
        """Where this block sits on the chain."""
        return Point(slot_no=self.slot_no, block_hash=self.block_hash)

    def links_onto(self, parent: Block) -> bool:
        """True if this block builds directly on ``parent``.

        A block builds on another when its ``prev_hash`` equals the parent's
        ``block_hash``. This one check is the seed of fork detection in the next
        chapter: a block that does not link onto our current tip belongs to a
        different branch.
        """
        return self.prev_hash == parent.block_hash
