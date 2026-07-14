"""Tests for the REST query API, driven by an in-memory store and a test client."""

import json

import pytest
from fastapi.testclient import TestClient

from chainidx.api import create_app
from chainidx.model import (
    AccountState,
    Asset,
    Block,
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
    Withdrawal,
)
from chainidx.network import NetworkParams
from chainidx.store import SqliteStore


@pytest.fixture
def client() -> TestClient:
    store = SqliteStore()
    # Block 1: alice funded, a pool and a stake address registered.
    store.apply_block(
        Block(
            block_no=1,
            slot_no=10,
            block_hash="b1",
            prev_hash="genesis",
            txs=(
                Tx(
                    "tx1",
                    outputs=(TxOut("alice", 5_000_000, assets=(Asset("pol", "TOK", 3),)),),
                    certificates=(
                        PoolRegistration("pool1", 1000, 0.03, "stake_r"),
                        StakeRegistration("stake_alice"),
                        DRepRegistration("drep1", 500),
                    ),
                ),
            ),
        )
    )
    # Block 2: alice spends to bob, and a governance action is voted on.
    store.apply_block(
        Block(
            block_no=2,
            slot_no=20,
            block_hash="b2",
            prev_hash="b1",
            txs=(
                Tx(
                    "tx2",
                    inputs=(TxIn("tx1", 0),),
                    outputs=(TxOut("bob", 5_000_000, assets=(Asset("pol", "TOK", 3),)),),
                    proposals=(GovActionProposal("gov1", "InfoAction", 0, "stake_r"),),
                    votes=(GovVote("gov1", "DRep", "drep1", "Yes"),),
                ),
            ),
        )
    )
    return TestClient(create_app(store))


def test_account_with_delegation_and_rewards() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    certificates=(StakeRegistration("cred1"), StakeDelegation("cred1", "poolX")),
                ),
            ),
        )
    )
    store.record_account_states([AccountState("cred1", None, 500)])
    api = TestClient(create_app(store))

    account = api.get("/accounts/cred1").json()
    assert account["registered"] is True
    assert account["reward"] == 500
    assert "controlled_stake" in account
    # snapshot pool is None, so it falls back to the on-chain delegation.
    assert account["delegated_to"] == "poolX"


def test_pool_detail_links_reward_address_and_delegators() -> None:
    store = SqliteStore()
    reward_hex = "e0" + "11" * 28  # a 29-byte testnet reward/stake address
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    certificates=(
                        PoolRegistration("pool1", 1000, 0.03, reward_hex),
                        StakeDelegation("aa" * 28, "pool1"),
                    ),
                ),
            ),
            issuer="pool1",
        )
    )
    detail = TestClient(create_app(store)).get("/pools/pool1").json()
    assert detail["reward_address"].startswith("stake_test1")
    assert detail["delegators_list"][0].startswith("stake_test1")


def test_stake_display_helper() -> None:
    from chainidx.api import _stake_display

    assert _stake_display("aa" * 28).startswith("stake_test1")
    assert _stake_display("nothex") == "nothex"


def test_stake_credential_decoding() -> None:
    from chainidx.api import _stake_credential
    from chainidx.bech32 import encode

    cred = "aa" * 28
    stake_addr = encode("stake_test", bytes([0xE0]) + bytes.fromhex(cred))
    assert _stake_credential(stake_addr) == cred
    assert _stake_credential("plainhex") == "plainhex"
    # A "stake"-prefixed but invalid string is returned unchanged.
    assert _stake_credential("stake_not_valid") == "stake_not_valid"


def test_bech32_display_and_decode_helpers() -> None:
    from chainidx.api import _address_display, _pool_display, _to_hex

    pool_hex = "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"
    addr_hex = "00" + "11" * 56
    # Real hex encodes to bech32; non-hex test ids pass through unchanged.
    assert _pool_display(pool_hex).startswith("pool1")
    assert _pool_display("pool1") == "pool1"
    assert _address_display(addr_hex).startswith("addr_test1")
    assert _address_display("alice") == "alice"
    # Arguments decode back to hex when prefixed, else pass through.
    assert _to_hex(_pool_display(pool_hex), "pool") == pool_hex
    assert _to_hex("plainhex", "pool") == "plainhex"


def test_block_shows_minting_pool() -> None:
    store = SqliteStore()
    pool_hex = "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"
    store.apply_block(Block(1, 10, "b1", "genesis", txs=(), issuer=pool_hex))
    api = TestClient(create_app(store))
    assert api.get("/blocks/b1").json()["issuer"].startswith("pool1")


def test_blocks_latest_is_404_on_an_empty_store() -> None:
    empty = TestClient(create_app(SqliteStore()))
    assert empty.get("/blocks/latest").status_code == 404
    assert empty.get("/health").json()["tip_height"] is None


def test_health_reports_the_tip(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["tip_height"] == 2


def test_blocks_latest_and_by_hash(client: TestClient) -> None:
    latest = client.get("/blocks/latest").json()
    assert latest["hash"] == "b2"

    one = client.get("/blocks/b1").json()
    assert one["block_no"] == 1
    assert one["tx_hashes"] == ["tx1"]

    assert client.get("/blocks/nope").status_code == 404


def test_epochs_are_empty_without_network(client: TestClient) -> None:
    assert client.get("/epochs").json() == []
    assert client.get("/epochs/0").status_code == 404
    assert client.get("/epochs/0/blocks").status_code == 404
    assert client.get("/network").json()["available"] is False


def test_certificates_browser_lists_every_category() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    certificates=(
                        StakeRegistration("s1"),
                        StakeDeregistration("s2"),
                        StakeDelegation("s3", "poolA"),
                        VoteDelegation("s4", "drepX"),
                        PoolRegistration("poolB", 1000, 0.02, "r1"),
                        PoolRetirement("poolC", 300),
                        DRepRegistration("d1", 500),
                        DRepDeregistration("d2"),
                        DRepUpdate("d3"),
                        CommitteeAuthHot("cold1", "hot1"),
                        CommitteeResignCold("cold2"),
                    ),
                ),
            ),
        )
    )
    api = TestClient(create_app(store))

    summary = {c["cert_type"]: c["count"] for c in api.get("/certificates/summary").json()}
    assert summary["Delegation"] == 1
    assert summary["Vote Delegation"] == 1
    assert summary["Committee Hot Key Authorization"] == 1
    assert summary["Committee Cold Key Resignation"] == 1
    assert summary["DRep Update"] == 1
    assert len(summary) == 11  # every category present

    all_certs = api.get("/certificates").json()
    assert len(all_certs) == 11
    assert all(c["tx_hash"] == "tx1" for c in all_certs)

    # Filtering by category returns just that category, with its detail field.
    retire = api.get("/certificates", params={"cert_type": "Pool Deregistration"}).json()
    assert len(retire) == 1
    assert retire[0]["subject"] == "poolC"
    assert retire[0]["detail"] == "epoch 300"

    # An empty category simply returns nothing.
    assert api.get("/certificates", params={"cert_type": "Nonexistent"}).json() == []


def test_epochs_and_network_with_params() -> None:
    store = SqliteStore()
    for i in range(1, 13):  # block i at slot i*10
        store.apply_block(Block(i, i * 10, f"b{i}", "p", txs=()))
    network = NetworkParams(system_start="2026-07-13T20:36:52Z", slot_length=0.2, epoch_length=100)
    api = TestClient(create_app(store, network))

    epochs = api.get("/epochs").json()
    assert epochs[0]["epoch_no"] == 1  # newest first
    assert any(e["epoch_no"] == 0 and e["block_count"] == 9 for e in epochs)
    assert "start_time" in epochs[0]

    assert api.get("/epochs/0").json()["block_count"] == 9
    assert api.get("/epochs/999").status_code == 404

    # The epoch's blocks are listed and each is a clickable-shaped block record.
    blocks0 = api.get("/epochs/0/blocks").json()
    assert len(blocks0) == 9
    assert blocks0[0]["block_no"] == 9  # newest first
    assert all("hash" in b and "tx_count" in b for b in blocks0)
    assert api.get("/epochs/1/blocks").json()[0]["block_no"] == 12
    assert api.get("/epochs/999/blocks").json() == []

    net = api.get("/network").json()
    assert net["available"] is True
    assert net["current_epoch"] == 1  # tip at slot 120

    block1 = api.get("/blocks/height/1").json()
    assert block1["epoch_no"] == 0
    assert "time" in block1


def test_analytics_summary(client: TestClient) -> None:
    summary = client.get("/analytics/summary").json()
    assert summary["total_blocks"] == 2
    assert summary["total_transactions"] == 2  # one tx in each block
    assert summary["active_pools"] == 1
    assert summary["dreps"] == 1
    assert summary["governance_actions"] == 1


def test_blocks_by_height_and_slot(client: TestClient) -> None:
    by_height = client.get("/blocks/height/1").json()
    assert by_height["hash"] == "b1"
    by_slot = client.get("/blocks/slot/10").json()  # block 1 is at slot 10
    assert by_slot["hash"] == "b1"
    assert client.get("/blocks/height/999").status_code == 404
    assert client.get("/blocks/slot/999").status_code == 404


def test_blocks_list(client: TestClient) -> None:
    blocks = client.get("/blocks", params={"limit": 5}).json()
    assert [b["hash"] for b in blocks] == ["b2", "b1"]


def test_tx_detail(client: TestClient) -> None:
    tx = client.get("/txs/tx2").json()
    assert tx["block_hash"] == "b2"
    assert tx["fee"] == 0
    assert tx["metadata"] is None
    # The input is resolved to the value it spends (alice's output from block 1).
    inp = tx["inputs"][0]
    assert inp["tx_id"] == "tx1"
    assert inp["index"] == 0
    assert inp["resolved"] is True
    assert inp["address"] == "alice"
    assert inp["lovelace"] == 5_000_000
    assert inp["assets"] == [{"policy_id": "pol", "asset_name": "TOK", "quantity": 3}]
    assert tx["outputs"][0]["address"] == "bob"
    assert tx["outputs"][0]["assets"][0]["asset_name"] == "TOK"
    # Proposals and votes are structured now, each linking to its governance action.
    assert tx["proposals"] == [{"gov_action_id": "gov1", "action_type": "InfoAction", "deposit": 0}]
    assert tx["votes"] == [
        {"voter_role": "DRep", "voter_id": "drep1", "vote": "Yes", "gov_action_id": "gov1"}
    ]
    assert tx["withdrawals"] == []  # tx2 made no reward withdrawals
    assert client.get("/txs/missing").status_code == 404

    # tx1 carried the staking and DRep certificates, now as structured records.
    tx1 = client.get("/txs/tx1").json()
    assert any(c["cert_type"] == "Pool Registration" for c in tx1["certificates"])


def test_tx_detail_fee_metadata_and_unresolved_input() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "txA",
                    inputs=(TxIn("genesisUtxo", 0),),  # a source output we never indexed
                    outputs=(TxOut("addr1", 1_000_000),),
                    fee=170_000,
                    metadata='{"674": {"msg": "hello"}}',
                ),
            ),
        )
    )
    t = TestClient(create_app(store)).get("/txs/txA").json()
    assert t["fee"] == 170_000
    assert t["metadata"] == {"674": {"msg": "hello"}}
    assert t["inputs"][0]["resolved"] is False
    assert t["inputs"][0]["address"] == ""
    assert t["inputs"][0]["lovelace"] == 0


def test_address_balance_and_utxos(client: TestClient) -> None:
    alice = client.get("/addresses/alice").json()
    assert alice["balance"] == 0  # spent in block 2
    bob = client.get("/addresses/bob").json()
    assert bob["balance"] == 5_000_000


def test_mempool_endpoint() -> None:
    from chainidx.model import MempoolStatus

    store = SqliteStore()
    # No mempool source wired in -> unavailable.
    assert TestClient(create_app(store)).get("/mempool").json() == {"available": False}

    # With a source (in production the local-tx-monitor client), it reports status.
    status = MempoolStatus(slot=100, capacity=178176, size_bytes=232, tx_count=1, tx_ids=("abc",))
    api = TestClient(create_app(store, None, lambda: status))
    body = api.get("/mempool").json()
    assert body["available"] is True
    assert body["tx_count"] == 1
    assert body["tx_ids"] == ["abc"]
    assert body["capacity"] == 178176


def test_analytics_timeseries() -> None:
    store = SqliteStore()
    # No network configured -> no time-series.
    assert TestClient(create_app(store)).get("/analytics/timeseries").json() == []

    store.apply_block(Block(1, 10, "b1", "genesis", txs=(Tx("t1", fee=100),)))
    net = NetworkParams(system_start="2026-07-13T20:36:52Z", slot_length=0.2, epoch_length=100)
    ts = TestClient(create_app(store, net)).get("/analytics/timeseries").json()
    assert ts[0]["epoch_no"] == 0
    assert ts[0]["tx_count"] == 1
    assert ts[0]["fee_total"] == 100
    assert "time" in ts[0]


def test_recent_transactions(client: TestClient) -> None:
    txs = client.get("/transactions").json()
    # Newest first: tx2 (block 2), then tx1 (block 1).
    assert [t["tx_id"] for t in txs] == ["tx2", "tx1"]
    assert txs[0]["block_no"] == 2
    assert txs[0]["output_count"] == 1
    assert txs[0]["total_output"] == 5_000_000
    assert "time" not in txs[0]  # no network configured on the default client


def test_recent_transactions_include_time_with_network() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(1, 10, "b1", "genesis", txs=(Tx("tx1", outputs=(TxOut("a", 1_000_000),)),))
    )
    net = NetworkParams(system_start="2026-07-13T20:36:52Z", slot_length=0.2, epoch_length=100)
    txs = TestClient(create_app(store, net)).get("/transactions").json()
    assert txs[0]["tx_id"] == "tx1"
    assert "time" in txs[0]


def test_top_addresses_and_accounts() -> None:
    store = SqliteStore()
    # addr1 holds a base address (with a stake credential) worth more than addr2.
    base = "00" + "aa" * 28 + "bb" * 28  # header + payment + stake credential
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx("t1", outputs=(TxOut(base, 9_000_000), TxOut("addr2", 4_000_000))),
                Tx("t2", outputs=(TxOut("addr2", 1_000_000),)),
            ),
        )
    )
    api = TestClient(create_app(store))
    addrs = api.get("/top/addresses").json()
    # The base address is richest; balances are summed per address.
    assert addrs[0]["balance"] == 9_000_000
    assert {a["balance"] for a in addrs} == {9_000_000, 5_000_000}

    accts = api.get("/top/accounts").json()
    # Only the base address carries a stake credential, so one account, 9 ADA.
    assert len(accts) == 1
    assert accts[0]["controlled_stake"] == 9_000_000
    assert accts[0]["stake_address"].startswith("stake_test1")


def test_withdrawals() -> None:
    assert TestClient(create_app(SqliteStore())).get("/withdrawals").json() == []

    store = SqliteStore()
    account = "e0" + "11" * 28
    store.apply_block(
        Block(
            1, 10, "b1", "genesis", txs=(Tx("txw", withdrawals=(Withdrawal(account, 2_000_000),)),)
        )
    )
    api = TestClient(create_app(store))
    ws = api.get("/withdrawals").json()
    assert len(ws) == 1
    assert ws[0]["amount"] == 2_000_000
    assert ws[0]["stake_address"].startswith("stake_test1")
    assert ws[0]["tx_hash"] == "txw"
    # The withdrawal also shows on the transaction page.
    assert api.get("/txs/txw").json()["withdrawals"][0]["amount"] == 2_000_000


def test_protocol_updates_filters_governance_actions() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    proposals=(
                        GovActionProposal("pc", "ParameterChange", 0, "r"),
                        GovActionProposal("hf", "HardForkInitiation", 0, "r"),
                        GovActionProposal("info", "InfoAction", 0, "r"),
                    ),
                ),
            ),
        )
    )
    api = TestClient(create_app(store))
    updates = api.get("/governance/protocol-updates").json()
    types = {u["action_type"] for u in updates}
    assert types == {"ParameterChange", "HardForkInitiation"}  # InfoAction excluded
    # The full governance list still has all three.
    assert len(api.get("/governance/actions").json()) == 3


def test_committee_page() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    certificates=(
                        CommitteeAuthHot("cold1", "hot1"),
                        CommitteeAuthHot("cold2", "hot2"),
                        CommitteeResignCold("cold2"),
                    ),
                ),
            ),
        )
    )
    api = TestClient(create_app(store))
    members = {m["cold_credential"]: m for m in api.get("/governance/committee").json()}
    assert members["cold1"]["hot_credential"] == "hot1"
    assert members["cold1"]["resigned"] is False
    assert members["cold2"]["resigned"] is True

    assert api.get("/governance/committee/cold1").json()["hot_credential"] == "hot1"
    assert api.get("/governance/committee/nope").status_code == 404


def test_protocol_parameters_endpoint() -> None:
    store = SqliteStore()
    api = TestClient(create_app(store))
    assert api.get("/protocol-parameters").json() == {}
    store.record_protocol_params({"min_fee_a": 44, "pool_deposit": 500_000_000})
    assert api.get("/protocol-parameters").json() == {"min_fee_a": 44, "pool_deposit": 500_000_000}
    # A later snapshot replaces the previous parameters.
    store.record_protocol_params({"min_fee_a": 45})
    assert api.get("/protocol-parameters").json() == {"min_fee_a": 45}


def test_cip25_asset_metadata() -> None:
    store = SqliteStore()
    policy = "aa" * 28
    name_hex = "4d794e4654"  # "MyNFT"
    md = json.dumps(
        {
            "721": {
                policy: {"MyNFT": {"name": "My NFT", "image": "ipfs://abc", "files": [1, 2]}},
                "version": 2,
            }
        }
    )
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "mint",
                    outputs=(TxOut("a", 2_000_000, assets=(Asset(policy, name_hex, 1),)),),
                    metadata=md,
                ),
                Tx("plain", metadata='{"674": {"msg": "hi"}}'),  # metadata, but no 721
                Tx("bare"),  # no metadata at all
            ),
        )
    )
    api = TestClient(create_app(store))
    a = api.get(f"/assets/{policy}/{name_hex}").json()
    assert a["metadata"]["name"] == "My NFT"
    assert a["metadata"]["image"] == "ipfs://abc"
    assert a["metadata"]["files"] == [1, 2]

    # An asset minted without CIP-25 metadata reports null.
    store2 = SqliteStore()
    store2.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(Tx("t", outputs=(TxOut("a", 1_000, assets=(Asset("bb" * 28, "01", 1),)),)),),
        )
    )
    b = TestClient(create_app(store2)).get(f"/assets/{'bb' * 28}/01").json()
    assert b["metadata"] is None


def test_cip68_metadata_from_reference_token() -> None:
    import cbor2

    store = SqliteStore()
    policy = "cc" * 28
    user = "000de140" + "6d796e6674"  # (222) user token
    ref = "000643b0" + "6d796e6674"  # (100) reference token
    empty_user = "000de140" + "6161"  # a user token whose reference is missing
    bad_user = "0014df10" + "6262"  # a (333) user token whose reference datum is junk
    bad_ref = "000643b0" + "6262"
    datum = cbor2.dumps(
        cbor2.CBORTag(121, [{b"name": b"CIP68 NFT", b"image": b"ipfs://z"}, 1])
    ).hex()
    junk = cbor2.dumps([]).hex()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "mint",
                    outputs=(
                        TxOut("u", 2_000_000, assets=(Asset(policy, user, 1),)),
                        TxOut("r", 2_000_000, assets=(Asset(policy, ref, 1),), datum=datum),
                        TxOut("e", 2_000_000, assets=(Asset(policy, empty_user, 1),)),
                        TxOut("b", 2_000_000, assets=(Asset(policy, bad_user, 1),)),
                        TxOut("br", 2_000_000, assets=(Asset(policy, bad_ref, 1),), datum=junk),
                    ),
                ),
            ),
        )
    )
    api = TestClient(create_app(store))
    # A user token resolves its CIP-68 metadata from the reference token's datum.
    a = api.get(f"/assets/{policy}/{user}").json()
    assert a["metadata_standard"] == "CIP-68"
    assert a["metadata"]["name"] == "CIP68 NFT"
    # The reference token itself is not a user token -> no metadata.
    assert api.get(f"/assets/{policy}/{ref}").json()["metadata"] is None
    # A user token with no reference token on-chain -> no metadata.
    assert api.get(f"/assets/{policy}/{empty_user}").json()["metadata"] is None
    # A reference datum that carries no metadata map -> no metadata.
    assert api.get(f"/assets/{policy}/{bad_user}").json()["metadata"] is None


def test_asset_name_decoding_and_policy_page() -> None:
    from chainidx.api import _asset_name_text

    assert _asset_name_text("436861696e4964784e4654") == "ChainIdxNFT"
    assert _asset_name_text("ff") == ""  # not valid UTF-8
    assert _asset_name_text("00") == ""  # a control byte is not printable
    assert _asset_name_text("TOK") == ""  # not valid hex

    store = SqliteStore()
    hexname = "436861696e4964784e4654"  # "ChainIdxNFT"
    nft = TxOut("addrA", 2_000_000, assets=(Asset("polX", hexname, 1),))
    store.apply_block(Block(1, 10, "b1", "genesis", txs=(Tx("tx1", outputs=(nft,)),)))
    api = TestClient(create_app(store))
    a = api.get(f"/assets/polX/{hexname}").json()
    assert a["asset_name_text"] == "ChainIdxNFT"
    pol = api.get("/policies/polX").json()
    assert pol["policy_id"] == "polX"
    assert pol["asset_count"] == 1
    assert pol["assets"][0]["asset_name_text"] == "ChainIdxNFT"


def test_assets_pools_accounts_governance(client: TestClient) -> None:
    assets = client.get("/assets").json()
    assert assets == [{"policy_id": "pol", "asset_name": "TOK", "quantity": 3}]

    detail = client.get("/assets/pol/TOK").json()
    assert detail["quantity"] == 3
    assert detail["holders"] == 1
    assert detail["asset_name_text"] == ""  # "TOK" is not valid hex
    assert client.get("/assets/pol/MISSING").status_code == 404

    pol = client.get("/policies/pol").json()
    assert pol["asset_count"] == 1
    assert pol["assets"][0]["asset_name"] == "TOK"
    assert client.get("/policies/unknown").status_code == 404

    pools = client.get("/pools").json()
    assert len(pools) == 1
    assert pools[0]["pool_id"] == "pool1"
    assert "blocks_minted" in pools[0]
    assert "delegators" in pools[0]

    detail = client.get("/pools/pool1").json()
    assert detail["pool_id"] == "pool1"
    assert "recent_blocks" in detail
    assert "live_stake" in detail
    assert "saturation" in detail
    assert client.get("/pools/unknown").status_code == 404

    account = client.get("/accounts/stake_alice").json()
    assert account["registered"] is True

    gov = client.get("/governance/actions").json()
    assert gov[0]["gov_action_id"] == "gov1"
    assert gov[0]["action_type"] == "InfoAction"
    assert gov[0]["tally"] == {"yes": 1, "no": 0, "abstain": 0}

    detail = client.get("/governance/actions/gov1").json()
    assert detail["votes"][0]["vote"] == "Yes"
    assert client.get("/governance/actions/missing").status_code == 404

    dreps = client.get("/governance/dreps").json()
    assert dreps[0]["drep_id"] == "drep1"
    assert dreps[0]["deposit"] == 500
    drep = client.get("/governance/dreps/drep1").json()
    assert drep["votes_cast"] == 1
    # The detail page shows which actions the DRep voted on and how.
    assert drep["votes"] == [{"gov_action_id": "gov1", "action_type": "InfoAction", "vote": "Yes"}]
    assert client.get("/governance/dreps/nope").status_code == 404
