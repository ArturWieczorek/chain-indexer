"""Tests for the CBOR block decoder, run against real captured node blocks.

The fixtures under tests/fixtures/node_block_*.cbor were captured from a live
cardano-node over its socket. The expected hashes below are the real on-chain
hashes, so these tests prove we decode identity correctly, not just plausibly.
"""

import io
import json
from pathlib import Path
from typing import cast

import cbor2

from chainidx.cbor_blocks import (
    _decode_certificates,
    _read_array_header,
    decode_block,
    decode_value,
)
from chainidx.model import (
    CommitteeAuthHot,
    CommitteeResignCold,
    DRepDeregistration,
    DRepRegistration,
    DRepUpdate,
    PoolRegistration,
    PoolRetirement,
    StakeDelegation,
    StakeDeregistration,
    StakeRegistration,
    VoteDelegation,
)
from chainidx.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"

# Real values for the captured block at height 33.
BLOCK_HASH = "7058a7c4d6faf83b7f563ade99f38a30c021c8701aad16f6f51d6bb5865d8608"
TX0_ID = "d97b618ecd7c2c9f804015547805bae59b6367566d81baf9a439f5f5fc744269"


def load_tag(name: str) -> cbor2.CBORTag:
    return cast(cbor2.CBORTag, cbor2.loads((FIXTURES / name).read_bytes()))


def test_decode_a_real_block_reproduces_the_on_chain_hashes() -> None:
    block = decode_block(load_tag("node_block_txs.cbor"))
    assert block.block_hash == BLOCK_HASH
    assert block.block_no == 33
    assert block.slot_no == 349
    assert block.prev_hash.startswith("7a41eb8cf2d6c991")
    assert len(block.txs) >= 1
    assert block.txs[0].tx_id == TX0_ID


def test_decoded_transaction_has_inputs_outputs_and_certificates() -> None:
    tx = decode_block(load_tag("node_block_txs.cbor")).txs[0]
    assert len(tx.inputs) >= 1
    assert len(tx.outputs) >= 1
    assert tx.outputs[0].lovelace > 0
    # An address is 57 raw bytes -> 114 hex characters.
    assert len(tx.outputs[0].address) == 114

    kinds = {type(c) for c in tx.certificates}
    assert PoolRegistration in kinds
    assert StakeRegistration in kinds
    assert StakeDelegation in kinds
    assert DRepRegistration in kinds
    pool = next(c for c in tx.certificates if isinstance(c, PoolRegistration))
    assert 0.0 <= pool.margin <= 1.0
    assert pool.pledge > 0


def test_decoded_block_records_its_issuer_pool() -> None:
    block = decode_block(load_tag("node_block_txs.cbor"))
    # blake2b-224 of the header issuer vkey = the pool id that minted the block.
    assert block.issuer == "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"


def test_decode_an_empty_block() -> None:
    block = decode_block(load_tag("node_block_empty.cbor"))
    assert len(block.block_hash) == 64
    assert block.txs == ()
    # The very first block builds on nothing, so prev_hash is empty.
    assert block.prev_hash == ""


def test_decoded_block_flows_into_the_store() -> None:
    block = decode_block(load_tag("node_block_txs.cbor"))
    store = SqliteStore()
    store.apply_block(block)
    assert store.block_count() == 1
    # The pools registered in this genesis-setup block show up.
    assert len(store.pools()) >= 1
    store.close()


def test_decode_all_conway_certificate_tags() -> None:
    cred = [0, bytes.fromhex("11" * 28)]  # a key credential
    cold = [0, bytes.fromhex("22" * 28)]
    hot = [0, bytes.fromhex("33" * 28)]
    pool = bytes.fromhex("44" * 28)
    drep_key = [0, bytes.fromhex("55" * 28)]
    certs = [
        [0, cred],  # stake registration (legacy)
        [7, cred, 2_000_000],  # stake registration (with deposit)
        [1, cred],  # stake deregistration (legacy)
        [8, cred, 2_000_000],  # stake deregistration (with deposit)
        [2, cred, pool],  # stake delegation
        [9, cred, drep_key],  # vote delegation to a DRep key
        [12, cred, [2]],  # vote delegation to always-abstain
        [4, pool, 300],  # pool retirement at epoch 300
        [14, cold, hot],  # committee hot key authorization
        [15, cold, None],  # committee cold key resignation
        [17, cred, 500_000],  # DRep deregistration
        [18, cred, None],  # DRep update
    ]
    decoded = _decode_certificates(certs)
    kinds = [type(c) for c in decoded]
    assert kinds == [
        StakeRegistration,
        StakeRegistration,
        StakeDeregistration,
        StakeDeregistration,
        StakeDelegation,
        VoteDelegation,
        VoteDelegation,
        PoolRetirement,
        CommitteeAuthHot,
        CommitteeResignCold,
        DRepDeregistration,
        DRepUpdate,
    ]
    vote_to_key = next(c for c in decoded if isinstance(c, VoteDelegation))
    assert vote_to_key.drep == "55" * 28
    abstain = [c for c in decoded if isinstance(c, VoteDelegation)][1]
    assert abstain.drep == "AlwaysAbstain"
    retire = next(c for c in decoded if isinstance(c, PoolRetirement))
    assert retire.retiring_epoch == 300
    auth = next(c for c in decoded if isinstance(c, CommitteeAuthHot))
    assert auth.hot_credential == "33" * 28
    # An unknown tag is skipped, not guessed at.
    assert _decode_certificates([[99, cred]]) == ()


def test_cip68_datum_and_inline_datum_decoding() -> None:
    from chainidx.cbor_blocks import _decode_output, decode_cip68_datum, reference_asset_name

    # The reference token name for a (222) user token, and a non-CIP-68 name.
    user = "000de140" + "6d796e6674"
    assert reference_asset_name(user) == "000643b0" + "6d796e6674"
    assert reference_asset_name("ffff00") is None

    # A metadata map exercising every leaf kind: text bytes, non-UTF-8 bytes
    # (hex), a non-printable control byte (hex), a list, and a nested map.
    meta = {
        b"name": b"CIP68 NFT",
        b"blob": b"\xff\xfe",
        b"ctrl": b"\x01",
        b"files": [b"a", 1],
        b"props": {b"k": b"v"},
    }
    datum_hex = cbor2.dumps(cbor2.CBORTag(121, [meta, 1])).hex()
    md = decode_cip68_datum(datum_hex)
    assert md["name"] == "CIP68 NFT"
    assert md["blob"] == "fffe"  # not UTF-8 -> hex
    assert md["ctrl"] == "01"  # not printable -> hex
    assert md["files"] == ["a", 1]
    assert md["props"] == {"k": "v"}
    # A datum that is not a constructor-with-map decodes to an empty map.
    assert decode_cip68_datum(cbor2.dumps([]).hex()) == {}

    # An inline datum on a Conway map output (key 2 = [1, tag24(datum)]).
    out = {0: b"\x00" * 29, 1: 2_000_000, 2: [1, cbor2.CBORTag(24, bytes.fromhex(datum_hex))]}
    assert _decode_output(out).datum == datum_hex
    # A datum hash (tag 0), no datum option, and the legacy list form: no datum.
    assert _decode_output({0: b"\x00" * 29, 1: 5, 2: [0, b"\xaa" * 32]}).datum == ""
    assert _decode_output({0: b"\x00" * 29, 1: 5}).datum == ""
    assert _decode_output([b"\x00" * 29, 5]).datum == ""


def test_decode_mint_field() -> None:
    from chainidx.cbor_blocks import _decode_mint

    body = {9: {b"\xaa" * 28: {b"TOK": 5, b"BRN": -2}}}
    mints = {(m.asset_name, m.quantity) for m in _decode_mint(body)}
    assert mints == {("544f4b", 5), ("42524e", -2)}  # a mint and a burn
    assert _decode_mint({}) == ()


def test_decode_pool_registration_cost_and_metadata() -> None:
    from chainidx.cbor_blocks import _decode_certificates

    # [3, pool, vrf, pledge, cost, margin, reward, owners, relays, [url, hash]]
    cert = [
        3,
        b"\x11" * 28,
        b"\x22" * 32,
        1000,
        340_000_000,
        0.03,
        b"\xe0" + b"\x33" * 28,
        [],
        [],
        ["https://example/pool.json", b"\x44" * 32],
    ]
    cert[7] = [b"\x55" * 28, b"\x66" * 28]  # two owners
    cert[8] = [[0, 3001, bytes([1, 2, 3, 4]), None], [1, 3001, "relay.example"], [2, "srv.example"]]
    (pool,) = _decode_certificates([cert])
    assert isinstance(pool, PoolRegistration)
    assert pool.cost == 340_000_000
    assert pool.metadata_url == "https://example/pool.json"
    assert pool.vrf_hash == "22" * 32
    assert pool.metadata_hash == "44" * 32
    assert pool.owners == ("55" * 28, "66" * 28)
    assert pool.relays == ("1.2.3.4:3001", "relay.example:3001", "srv.example")
    # A pool with no metadata anchor (null) has an empty url and hash.
    cert[9] = None
    reg = _decode_certificates([cert])[0]
    assert reg.metadata_url == ""
    assert reg.metadata_hash == ""


def test_decode_withdrawals() -> None:
    from chainidx.cbor_blocks import _decode_withdrawals

    account = bytes.fromhex("e0" + "11" * 28)
    (w,) = _decode_withdrawals({5: {account: 1_500_000}})
    assert w.stake_address == "e0" + "11" * 28
    assert w.amount == 1_500_000
    assert _decode_withdrawals({}) == ()


def test_decode_drep_no_confidence_target() -> None:
    cred = [0, bytes.fromhex("11" * 28)]
    (vote,) = _decode_certificates([[9, cred, [3]]])
    assert isinstance(vote, VoteDelegation)
    assert vote.drep == "AlwaysNoConfidence"


def test_decode_governance_proposals_and_votes() -> None:
    from chainidx.cbor_blocks import _decode_proposals, _decode_votes

    reward = bytes.fromhex("e0" + "11" * 28)
    # An InfoAction proposal (gov_action tag 6).
    body_prop = {20: {(100000000, reward, (6,), ("http://x/info", b"\x00" * 32))}}
    proposals = _decode_proposals(body_prop, "abc123")
    assert len(proposals) == 1
    assert proposals[0].gov_action_id == "abc123#0"
    assert proposals[0].action_type == "InfoAction"
    assert proposals[0].deposit == 100000000

    gov_txid = bytes.fromhex("cc" * 32)
    drep = bytes.fromhex("dd" * 28)
    pool = bytes.fromhex("ee" * 28)
    body_votes = {
        19: {
            (2, drep): {(gov_txid, 0): [1, None]},  # DRep Yes
            (4, pool): {(gov_txid, 0): [0, None]},  # SPO No
        }
    }
    votes = _decode_votes(body_votes)
    by_role = {v.voter_role: v.vote for v in votes}
    assert by_role["DRep"] == "Yes"
    assert by_role["SPO"] == "No"
    assert votes[0].gov_action_id == f"{'cc' * 32}#0"


def test_metadata_helpers_across_eras() -> None:
    from chainidx.cbor_blocks import _metadata_json, _metadatum_to_json

    # bytes -> hex, nested list/map recurse, and map keys are stringified.
    assert _metadatum_to_json(b"\xab\xcd") == "abcd"
    assert _metadatum_to_json([1, b"\x01"]) == [1, "01"]
    assert _metadatum_to_json({1: "a"}) == {"1": "a"}

    # Alonzo+ tag-259 auxiliary data keeps the metadata under key 0.
    tag = cbor2.CBORTag(259, {0: {674: {"msg": "hi"}}, 1: []})
    assert json.loads(_metadata_json(tag)) == {"674": {"msg": "hi"}}
    # Shelley: a bare metadata map. Shelley-MA: [metadata, scripts].
    assert json.loads(_metadata_json({1: 2})) == {"1": 2}
    assert json.loads(_metadata_json([{5: "x"}, []])) == {"5": "x"}
    # Nothing to show.
    assert _metadata_json({}) == ""
    assert _metadata_json(None) == ""
    assert _metadata_json([]) == ""
    assert _metadata_json(cbor2.CBORTag(259, [])) == ""


def test_decode_block_reads_fee_and_transaction_metadata() -> None:
    header_body = [7, 100, None, b"\x11" * 32]
    header = [header_body]
    body = {0: [], 1: [], 2: 5}  # no inputs/outputs, fee 5
    aux = cbor2.CBORTag(259, {0: {674: {"msg": "hi"}}})
    block_array = [header, [body], [{}], {0: aux}]
    inner = cbor2.dumps([6, block_array])
    blk = decode_block(cbor2.CBORTag(24, inner))
    assert blk.block_no == 7
    assert blk.txs[0].fee == 5
    assert json.loads(blk.txs[0].metadata) == {"674": {"msg": "hi"}}


def test_decode_value_handles_ada_and_multi_asset() -> None:
    lovelace, assets = decode_value(1_500_000)
    assert lovelace == 1_500_000
    assert assets == ()

    coin, assets = decode_value([2_000_000, {b"\xaa\xbb": {b"TOK": 5, b"OTH": 9}}])
    assert coin == 2_000_000
    quantities = {(a.policy_id, a.asset_name, a.quantity) for a in assets}
    assert quantities == {("aabb", "544f4b", 5), ("aabb", "4f5448", 9)}


def test_read_array_header_reads_short_and_long_forms() -> None:
    # 0x83 -> an array of 3 (length in the head byte).
    assert _read_array_header(io.BytesIO(bytes([0x83]))) == 3
    # 0x98 0x1e -> an array of 30 (one following length byte).
    assert _read_array_header(io.BytesIO(bytes([0x98, 30]))) == 30
