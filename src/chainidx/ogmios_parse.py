"""Pure functions that turn Ogmios JSON into our domain model.

Ogmios speaks Cardano's mini-protocols for us and reports the results as JSON.
This module is the translation layer: given the JSON of a block, an input, an
output, or a chain-sync reply, produce the corresponding ``Block``, ``TxIn``,
``TxOut``, or ``ChainEvent``.

These functions are deliberately kept apart from the WebSocket client (in
``ogmios.py``) so that they are pure and fully unit-testable against saved,
real Ogmios responses - no live server needed. The JSON shapes here were
captured from Ogmios v6 talking to a live node, not guessed.

What Ogmios gives us, by example:

- a block is ``{"id", "ancestor", "height", "slot", "transactions": [...]}``;
- an output's value is ``{"ada": {"lovelace": N}, "<policy>": {"<asset>": N}}``;
- an input is ``{"transaction": {"id": ...}, "index": N}``;
- a certificate is a tagged object, e.g. ``{"type": "stakePoolRegistration", ...}``.

Certificate coverage note: we map the staking and DRep *registration* and
*delegation* certificates that a running cluster produces. Deregistration and
retirement certificates are handled by the from-scratch node path (chapter 12),
which decodes the full transaction body; the Ogmios path is our bootstrap.
"""

from __future__ import annotations

import hashlib
from typing import Any

from chainidx.model import (
    Asset,
    Block,
    Certificate,
    DRepRegistration,
    Origin,
    Point,
    PoolRegistration,
    StakeDelegation,
    StakeRegistration,
    Tx,
    TxIn,
    TxOut,
)
from chainidx.source import ChainEvent, RollBackward, RollForward

Json = dict[str, Any]


def parse_margin(text: str) -> float:
    """Turn a pool margin like ``"7/20"`` into a float (0.35)."""
    numerator, denominator = text.split("/")
    return int(numerator) / int(denominator)


def parse_value(value: Json) -> tuple[int, tuple[Asset, ...]]:
    """Split an Ogmios value into lovelace and a tuple of native assets."""
    lovelace = int(value.get("ada", {}).get("lovelace", 0))
    assets: list[Asset] = []
    for policy_id, names in value.items():
        if policy_id == "ada":
            continue
        for asset_name, quantity in names.items():
            assets.append(Asset(policy_id=policy_id, asset_name=asset_name, quantity=int(quantity)))
    return lovelace, tuple(assets)


def parse_output(output: Json) -> TxOut:
    lovelace, assets = parse_value(output.get("value", {}))
    return TxOut(address=output["address"], lovelace=lovelace, assets=assets)


def parse_input(input_: Json) -> TxIn:
    return TxIn(tx_id=input_["transaction"]["id"], index=int(input_["index"]))


def parse_certificates(certs: list[Json] | None) -> tuple[Certificate, ...]:
    out: list[Certificate] = []
    for cert in certs or ():
        kind = cert["type"]
        if kind == "stakeCredentialRegistration":
            out.append(StakeRegistration(stake_address=cert["credential"]))
        elif kind == "stakeDelegation":
            pool = cert.get("stakePool")
            # A Conway stakeDelegation may target a pool, a DRep, or both. We
            # index the pool delegation; DRep vote-delegation is out of scope.
            if pool is not None:
                out.append(StakeDelegation(stake_address=cert["credential"], pool_id=pool["id"]))
        elif kind == "stakePoolRegistration":
            pool = cert["stakePool"]
            out.append(
                PoolRegistration(
                    pool_id=pool["id"],
                    pledge=int(pool["pledge"]["ada"]["lovelace"]),
                    margin=parse_margin(pool["margin"]),
                    reward_address=pool["rewardAccount"],
                )
            )
        elif kind == "delegateRepresentativeRegistration":
            out.append(
                DRepRegistration(
                    drep_id=cert["delegateRepresentative"]["id"],
                    deposit=int(cert["deposit"]["ada"]["lovelace"]),
                )
            )
        # Other certificate types (committee delegation, and so on) are not
        # indexed on the Ogmios bootstrap path.
    return tuple(out)


def parse_tx(tx: Json) -> Tx:
    return Tx(
        tx_id=tx["id"],
        inputs=tuple(parse_input(i) for i in tx.get("inputs", [])),
        outputs=tuple(parse_output(o) for o in tx.get("outputs", [])),
        certificates=parse_certificates(tx.get("certificates")),
    )


def _issuer_pool_id(block: Json) -> str:
    """The pool id that minted the block: blake2b-224 of the issuer vkey."""
    vkey = block.get("issuer", {}).get("verificationKey")
    if vkey is None:
        return ""
    return hashlib.blake2b(bytes.fromhex(vkey), digest_size=28).hexdigest()


def parse_block(block: Json) -> Block:
    return Block(
        block_no=int(block["height"]),
        slot_no=int(block["slot"]),
        block_hash=block["id"],
        prev_hash=block.get("ancestor", ""),
        txs=tuple(parse_tx(t) for t in block.get("transactions", [])),
        issuer=_issuer_pool_id(block),
    )


def parse_point(point: Json | str) -> Point | Origin:
    """Turn an Ogmios point (``"origin"`` or ``{"slot", "id"}``) into ours."""
    if isinstance(point, str):
        return Origin()
    return Point(slot_no=int(point["slot"]), block_hash=point["id"])


def to_ogmios_point(point: Point | Origin) -> Json | str:
    """The reverse: our point to the JSON Ogmios expects for findIntersection."""
    if isinstance(point, Origin):
        return "origin"
    return {"slot": point.slot_no, "id": point.block_hash}


def parse_next_block(result: Json) -> ChainEvent:
    """Turn a chain-sync ``nextBlock`` reply into a roll-forward or roll-back."""
    if result["direction"] == "forward":
        return RollForward(block=parse_block(result["block"]))
    return RollBackward(point=parse_point(result["point"]))
