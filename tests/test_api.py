"""Tests for the REST query API, driven by an in-memory store and a test client."""

import pytest
from fastapi.testclient import TestClient

from chainidx.api import create_app
from chainidx.model import (
    Asset,
    Block,
    DRepRegistration,
    GovActionProposal,
    GovVote,
    PoolRegistration,
    StakeRegistration,
    Tx,
    TxIn,
    TxOut,
)
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
    assert tx["inputs"] == [{"tx_id": "tx1", "index": 0}]
    assert tx["outputs"][0]["address"] == "bob"
    assert client.get("/txs/missing").status_code == 404


def test_address_balance_and_utxos(client: TestClient) -> None:
    alice = client.get("/addresses/alice").json()
    assert alice["balance"] == 0  # spent in block 2
    bob = client.get("/addresses/bob").json()
    assert bob["balance"] == 5_000_000


def test_assets_pools_accounts_governance(client: TestClient) -> None:
    assets = client.get("/assets").json()
    assert assets == [{"policy_id": "pol", "asset_name": "TOK", "quantity": 3}]

    assert client.get("/pools").json() == ["pool1"]

    account = client.get("/accounts/stake_alice").json()
    assert account["registered"] is True

    gov = client.get("/governance/actions").json()
    assert gov == [{"gov_action_id": "gov1", "tally": {"Yes": 1}}]
