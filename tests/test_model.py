"""Tests for the domain model: the small set of types that describe a chain."""

import dataclasses

import pytest

from chainidx.model import Asset, Block, Point, Tip, Tx, TxIn, TxOut


def make_block(block_no: int, block_hash: str, prev_hash: str) -> Block:
    """A tiny helper so the tests read clearly."""
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=(),
    )


def test_txout_holds_an_address_and_lovelace() -> None:
    out = TxOut(address="addr_test1abc", lovelace=1_000_000)
    assert out.address == "addr_test1abc"
    assert out.lovelace == 1_000_000
    assert out.assets == ()


def test_txout_can_carry_native_assets() -> None:
    token = Asset(policy_id="a1b2", asset_name="MyToken", quantity=5)
    out = TxOut(address="addr_test1abc", lovelace=1_000_000, assets=(token,))
    assert out.assets == (token,)
    assert out.assets[0].quantity == 5


def test_txin_points_at_a_previous_output() -> None:
    spent = TxIn(tx_id="deadbeef", index=0)
    assert spent.tx_id == "deadbeef"
    assert spent.index == 0


def test_tx_has_inputs_and_outputs() -> None:
    tx = Tx(
        tx_id="tx0",
        inputs=(TxIn(tx_id="prev", index=1),),
        outputs=(TxOut(address="addr", lovelace=42),),
    )
    assert tx.tx_id == "tx0"
    assert len(tx.inputs) == 1
    assert len(tx.outputs) == 1


def test_block_reports_its_point() -> None:
    block = make_block(block_no=7, block_hash="hhh", prev_hash="ggg")
    assert block.point == Point(slot_no=70, block_hash="hhh")


def test_a_block_links_onto_its_parent() -> None:
    parent = make_block(block_no=1, block_hash="b1", prev_hash="b0")
    child = make_block(block_no=2, block_hash="b2", prev_hash="b1")
    other = make_block(block_no=2, block_hash="b2x", prev_hash="somewhere_else")

    assert child.links_onto(parent) is True
    assert other.links_onto(parent) is False


def test_tip_pairs_a_point_with_a_block_height() -> None:
    tip = Tip(point=Point(slot_no=100, block_hash="tiphash"), block_no=9)
    assert tip.point.block_hash == "tiphash"
    assert tip.block_no == 9


def test_model_values_are_immutable() -> None:
    out = TxOut(address="addr", lovelace=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.lovelace = 2  # type: ignore[misc]


def test_model_values_are_hashable_and_comparable() -> None:
    a = Point(slot_no=1, block_hash="h")
    b = Point(slot_no=1, block_hash="h")
    c = Point(slot_no=2, block_hash="h")
    assert a == b
    assert a != c
    # Hashable means we can put points in a set - useful when we look for the
    # intersection between two chains in the next chapter.
    assert {a, b, c} == {a, c}
