"""Decode real Cardano blocks from their raw CBOR bytes.

The node does not speak JSON. Over its socket it sends blocks as **CBOR**
(Concise Binary Object Representation, RFC 8949) - a compact binary cousin of
JSON. This module turns those bytes into our ``Block`` model, so that in chapters
11 and 12 we can drop Ogmios and read the node directly.

A Cardano block, once you peel back the wrappers, is a CBOR array:

    block = [ header, [tx_body, ...], [witnesses, ...], {aux_data}, [invalid] ]

We only need the header (for identity) and the transaction bodies (for content).

## The one subtlety worth its own paragraph

A block's hash is the blake2b-256 of the **header's exact original bytes**, and a
transaction's id is the blake2b-256 of the **tx body's exact original bytes**. You
cannot decode a structure into Python and re-encode it to recompute the hash: the
re-encoding may reorder map keys or encode a set differently, and the hash comes
out wrong (we checked - it does). The reference we index against, and the inputs
that later transactions use to point back at outputs, all use the *real* hash. So
we must hash the original bytes.

To do that we decode element by element while tracking byte offsets: read a CBOR
array header ourselves (to learn how many elements follow), then decode each
element with cbor2 and record where it started and ended. The slice between those
offsets is the exact bytes to hash. This is the only place we touch CBOR at the
byte level; everything else defers to cbor2.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

import cbor2

from chainidx.model import (
    Asset,
    Block,
    Certificate,
    DRepRegistration,
    PoolRegistration,
    StakeDelegation,
    StakeRegistration,
    Tx,
    TxIn,
    TxOut,
)

# Conway transaction-body map keys (a subset - the ones we index).
_INPUTS = 0
_OUTPUTS = 1
_CERTIFICATES = 4


def _blake2b_256(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def _read_array_header(reader: io.BytesIO) -> int:
    """Read a CBOR array header and return the element count.

    CBOR encodes an array as one head byte (major type 4) whose low 5 bits are
    either the length directly (0-23) or a code saying how many following bytes
    hold the length. We read just enough to learn the count, leaving the reader
    positioned at the first element - so the caller can decode elements one at a
    time and measure each one's byte span.
    """
    head = reader.read(1)[0]
    if head >> 5 != 4:  # pragma: no cover - our blocks are always arrays here
        raise ValueError(f"expected a CBOR array, got head byte {head:#x}")
    info = head & 0x1F
    if info < 24:
        return info
    return int.from_bytes(reader.read({24: 1, 25: 2, 26: 4, 27: 8}[info]), "big")


def _credential_hash(credential: list[Any]) -> str:
    """A credential is ``[key_type, hash_bytes]``; we want the hash as hex."""
    return str(credential[1].hex())


def decode_value(value: int | list[Any]) -> tuple[int, tuple[Asset, ...]]:
    """Decode an output value: either plain lovelace, or ``[lovelace, assets]``.

    The multi-asset form nests as ``{policy_bytes: {asset_name_bytes: qty}}``.
    """
    if isinstance(value, int):
        return value, ()
    lovelace = value[0]
    assets: list[Asset] = []
    for policy_id, names in value[1].items():
        for asset_name, quantity in names.items():
            assets.append(
                Asset(policy_id=policy_id.hex(), asset_name=asset_name.hex(), quantity=quantity)
            )
    return lovelace, tuple(assets)


def _decode_output(output: list[Any]) -> TxOut:
    # Works for both the legacy list form [addr, value] and the Conway map form
    # {0: addr, 1: value, ...}, because both are indexed by 0 and 1.
    lovelace, assets = decode_value(output[1])
    return TxOut(address=output[0].hex(), lovelace=lovelace, assets=assets)


def _decode_certificates(certs: list[Any] | None) -> tuple[Certificate, ...]:
    out: list[Certificate] = []
    for cert in certs or ():
        tag = cert[0]
        if tag == 3:  # pool registration
            out.append(
                PoolRegistration(
                    pool_id=cert[1].hex(),
                    pledge=cert[3],
                    margin=float(cert[5]),
                    reward_address=cert[6].hex(),
                )
            )
        elif tag == 7:  # stake registration (Conway, with deposit)
            out.append(StakeRegistration(stake_address=_credential_hash(cert[1])))
        elif tag == 10:  # stake-and-vote delegation: [10, cred, pool, drep]
            out.append(
                StakeDelegation(stake_address=_credential_hash(cert[1]), pool_id=cert[2].hex())
            )
        elif tag == 16:  # DRep registration
            out.append(DRepRegistration(drep_id=_credential_hash(cert[1]), deposit=cert[2]))
        # Other certificate tags follow the same shape and can be added here.
    return tuple(out)


def _decode_tx(tx_id: str, body: dict[int, Any]) -> Tx:
    inputs = tuple(TxIn(tx_id=i[0].hex(), index=i[1]) for i in body.get(_INPUTS, ()))
    outputs = tuple(_decode_output(o) for o in body.get(_OUTPUTS, ()))
    certificates = _decode_certificates(body.get(_CERTIFICATES))
    return Tx(tx_id=tx_id, inputs=inputs, outputs=outputs, certificates=certificates)


def decode_block(block: cbor2.CBORTag) -> Block:
    """Decode a node block (a tag-24 wrapper around the block bytes).

    Chain-sync (chapter 12) hands us each block as ``CBORTag(24, <bytes>)``. We
    decode the wrapped bytes element by element, hashing the header and each tx
    body from their exact original bytes.
    """
    inner: bytes = block.value
    reader = io.BytesIO(inner)
    decoder = cbor2.CBORDecoder(reader)

    _read_array_header(reader)  # outer [era, block]
    decoder.decode()  # the era tag (an int); we do not need it
    _read_array_header(reader)  # the block array [header, tx_bodies, ...]

    header_start = reader.tell()
    header = decoder.decode()
    block_hash = _blake2b_256(inner[header_start : reader.tell()])

    header_body = header[0]
    block_no = header_body[0]
    slot_no = header_body[1]
    prev = header_body[2]
    prev_hash = prev.hex() if prev is not None else ""

    txs: list[Tx] = []
    for _ in range(_read_array_header(reader)):
        body_start = reader.tell()
        body = decoder.decode()
        tx_id = _blake2b_256(inner[body_start : reader.tell()])
        txs.append(_decode_tx(tx_id, body))

    return Block(
        block_no=block_no,
        slot_no=slot_no,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=tuple(txs),
    )
