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
    CommitteeAuthHot,
    CommitteeResignCold,
    DRepDeregistration,
    DRepRegistration,
    DRepUpdate,
    GovActionProposal,
    GovVote,
    PoolRegistration,
    PoolRetirement,
    StakeDelegation,
    StakeDeregistration,
    StakeRegistration,
    Tx,
    TxIn,
    TxOut,
    VoteDelegation,
)

# Conway transaction-body map keys (a subset - the ones we index).
_INPUTS = 0
_OUTPUTS = 1
_CERTIFICATES = 4
_VOTING_PROCEDURES = 19
_PROPOSAL_PROCEDURES = 20

# Governance action types by their CBOR tag, and voter roles / votes.
_GOV_ACTION_TYPES = {
    0: "ParameterChange",
    1: "HardForkInitiation",
    2: "TreasuryWithdrawals",
    3: "NoConfidence",
    4: "UpdateCommittee",
    5: "NewConstitution",
    6: "InfoAction",
}
_VOTER_ROLES = {
    0: "ConstitutionalCommittee",
    1: "ConstitutionalCommittee",
    2: "DRep",
    3: "DRep",
    4: "SPO",
}
_VOTES = {0: "No", 1: "Yes", 2: "Abstain"}


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


def _decode_drep(drep: list[Any]) -> str:
    """A DRep target: a key/script credential (hex), or a special voting role.

    The Conway ``drep`` type is ``[0, keyhash] / [1, scripthash] / [2] / [3]``,
    where 2 is always-abstain and 3 is always-no-confidence.
    """
    kind = drep[0]
    if kind in (0, 1):
        return str(drep[1].hex())
    return "AlwaysAbstain" if kind == 2 else "AlwaysNoConfidence"


def _decode_certificates(certs: list[Any] | None) -> tuple[Certificate, ...]:
    """Decode the Conway certificate list (tx body key 4).

    Each certificate is ``[tag, ...]``. The tags below are the Conway set; we map
    each to a typed record. The variants that both register and delegate (11, 13)
    are indexed by their delegation, which is the part later pages care about.
    """
    out: list[Certificate] = []
    for cert in certs or ():
        tag = cert[0]
        if tag in (0, 7):  # stake registration (legacy / with deposit)
            out.append(StakeRegistration(stake_address=_credential_hash(cert[1])))
        elif tag in (1, 8):  # stake deregistration (legacy / with deposit)
            out.append(StakeDeregistration(stake_address=_credential_hash(cert[1])))
        elif tag in (2, 10, 11, 13):  # delegation to a pool: [tag, cred, pool, ...]
            out.append(
                StakeDelegation(stake_address=_credential_hash(cert[1]), pool_id=cert[2].hex())
            )
        elif tag in (9, 12):  # vote delegation to a DRep: [tag, cred, drep, ...]
            out.append(
                VoteDelegation(stake_address=_credential_hash(cert[1]), drep=_decode_drep(cert[2]))
            )
        elif tag == 3:  # pool registration
            out.append(
                PoolRegistration(
                    pool_id=cert[1].hex(),
                    pledge=cert[3],
                    margin=float(cert[5]),
                    reward_address=cert[6].hex(),
                )
            )
        elif tag == 4:  # pool retirement: [4, pool_keyhash, epoch]
            out.append(PoolRetirement(pool_id=cert[1].hex(), retiring_epoch=cert[2]))
        elif tag == 14:  # committee hot key authorization: [14, cold_cred, hot_cred]
            out.append(
                CommitteeAuthHot(
                    cold_credential=_credential_hash(cert[1]),
                    hot_credential=_credential_hash(cert[2]),
                )
            )
        elif tag == 15:  # committee cold key resignation: [15, cold_cred, anchor/null]
            out.append(CommitteeResignCold(cold_credential=_credential_hash(cert[1])))
        elif tag == 16:  # DRep registration: [16, cred, deposit, anchor/null]
            out.append(DRepRegistration(drep_id=_credential_hash(cert[1]), deposit=cert[2]))
        elif tag == 17:  # DRep deregistration: [17, cred, deposit]
            out.append(DRepDeregistration(drep_id=_credential_hash(cert[1])))
        elif tag == 18:  # DRep update: [18, cred, anchor/null]
            out.append(DRepUpdate(drep_id=_credential_hash(cert[1])))
        # Unknown tags are skipped rather than guessed at.
    return tuple(out)


def _decode_proposals(body: dict[int, Any], tx_id: str) -> tuple[GovActionProposal, ...]:
    """Decode governance action proposals (tx body key 20).

    A proposal is ``(deposit, reward_account, gov_action, anchor)``; its id is this
    transaction's id plus the proposal's index (``txid#index``), which is how votes
    later refer to it.
    """
    out: list[GovActionProposal] = []
    for index, proposal in enumerate(body.get(_PROPOSAL_PROCEDURES, ()) or ()):
        deposit, reward_account, gov_action, _anchor = proposal
        out.append(
            GovActionProposal(
                gov_action_id=f"{tx_id}#{index}",
                action_type=_GOV_ACTION_TYPES.get(gov_action[0], f"Unknown({gov_action[0]})"),
                deposit=deposit,
                return_address=reward_account.hex(),
            )
        )
    return tuple(out)


def _decode_votes(body: dict[int, Any]) -> tuple[GovVote, ...]:
    """Decode votes (tx body key 19): ``{voter: {gov_action_id: [vote, anchor]}}``."""
    out: list[GovVote] = []
    for voter, actions in (body.get(_VOTING_PROCEDURES) or {}).items():
        voter_type, voter_cred = voter
        role = _VOTER_ROLES.get(voter_type, "Unknown")
        for (gov_txid, gov_index), procedure in actions.items():
            out.append(
                GovVote(
                    gov_action_id=f"{gov_txid.hex()}#{gov_index}",
                    voter_role=role,
                    voter_id=voter_cred.hex(),
                    vote=_VOTES.get(procedure[0], "Unknown"),
                )
            )
    return tuple(out)


def _decode_tx(tx_id: str, body: dict[int, Any]) -> Tx:
    inputs = tuple(TxIn(tx_id=i[0].hex(), index=i[1]) for i in body.get(_INPUTS, ()))
    outputs = tuple(_decode_output(o) for o in body.get(_OUTPUTS, ()))
    certificates = _decode_certificates(body.get(_CERTIFICATES))
    return Tx(
        tx_id=tx_id,
        inputs=inputs,
        outputs=outputs,
        certificates=certificates,
        proposals=_decode_proposals(body, tx_id),
        votes=_decode_votes(body),
    )


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
    # The issuer verification key (header_body[3]) hashes to the pool id that
    # minted the block (chapter 22). Pool ids are 28-byte (blake2b-224) hashes.
    issuer = hashlib.blake2b(header_body[3], digest_size=28).hexdigest()

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
        issuer=issuer,
    )
