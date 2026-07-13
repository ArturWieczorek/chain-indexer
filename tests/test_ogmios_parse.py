"""Tests for the Ogmios JSON parser, run against saved real responses."""

import json
from pathlib import Path
from typing import Any

from chainidx.model import (
    ORIGIN,
    DRepRegistration,
    Point,
    PoolRegistration,
    StakeDelegation,
    StakeRegistration,
)
from chainidx.ogmios_parse import (
    parse_block,
    parse_certificates,
    parse_margin,
    parse_next_block,
    parse_point,
    parse_value,
    to_ogmios_point,
)
from chainidx.source import RollBackward, RollForward

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_parse_margin_reads_a_fraction() -> None:
    assert parse_margin("7/20") == 0.35
    assert parse_margin("0/1") == 0.0


def test_parse_value_splits_ada_from_native_assets() -> None:
    lovelace, assets = parse_value(
        {"ada": {"lovelace": 5_000_000}, "policyabc": {"TOKEN": 42, "OTHER": 7}}
    )
    assert lovelace == 5_000_000
    names = {(a.policy_id, a.asset_name, a.quantity) for a in assets}
    assert names == {("policyabc", "TOKEN", 42), ("policyabc", "OTHER", 7)}


def test_parse_value_handles_ada_only() -> None:
    lovelace, assets = parse_value({"ada": {"lovelace": 1_000_000}})
    assert lovelace == 1_000_000
    assert assets == ()


def test_parse_block_maps_a_real_conway_block() -> None:
    block = parse_block(load("ogmios_block.json"))
    assert len(block.block_hash) == 64
    assert block.block_no > 0
    assert block.prev_hash != ""
    assert len(block.txs) == 1
    tx = block.txs[0]
    assert tx.tx_id
    assert len(tx.outputs) >= 1
    assert tx.outputs[0].lovelace > 0


def test_parse_certificates_maps_each_kind() -> None:
    block = load("ogmios_block.json")
    certs = parse_certificates(block["transactions"][0]["certificates"])
    kinds = {type(c) for c in certs}
    # The fixture was chosen to contain each kind we map.
    assert StakeRegistration in kinds
    assert StakeDelegation in kinds
    assert PoolRegistration in kinds
    assert DRepRegistration in kinds
    # A pool registration carries the parsed margin and pledge.
    pool = next(c for c in certs if isinstance(c, PoolRegistration))
    assert 0.0 <= pool.margin <= 1.0
    assert pool.pledge > 0


def test_parse_point_and_back() -> None:
    assert parse_point("origin") == ORIGIN
    point = parse_point({"slot": 100, "id": "abc"})
    assert point == Point(slot_no=100, block_hash="abc")
    # Round-trips.
    assert to_ogmios_point(ORIGIN) == "origin"
    assert to_ogmios_point(point) == {"slot": 100, "id": "abc"}


def test_parse_next_block_forward_and_backward() -> None:
    forward = parse_next_block(load("ogmios_forward.json")["result"])
    assert isinstance(forward, RollForward)
    assert forward.block.block_no > 0

    backward = parse_next_block(load("ogmios_backward.json")["result"])
    assert isinstance(backward, RollBackward)
    assert backward.point == ORIGIN
