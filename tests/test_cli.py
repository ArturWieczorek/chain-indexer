"""Tests for the chainidx CLI, driven by click's CliRunner."""

from pathlib import Path

from click.testing import CliRunner

from chainidx.cli import main
from chainidx.model import (
    Block,
    GovActionProposal,
    GovVote,
    PoolRegistration,
    StakeDelegation,
    StakeRegistration,
    Tx,
    TxIn,
    TxOut,
)
from chainidx.store import SqliteStore


def populate(db: str) -> None:
    store = SqliteStore(db)
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    outputs=(TxOut("alice", 5_000_000),),
                    certificates=(
                        PoolRegistration("pool1", 1000, 0.03, "stake_r"),
                        StakeRegistration("stake_alice"),
                        StakeDelegation("stake_alice", "pool1"),
                    ),
                ),
            ),
        )
    )
    store.apply_block(
        Block(
            2,
            20,
            "b2",
            "b1",
            txs=(
                Tx(
                    "tx2",
                    inputs=(TxIn("tx1", 0),),
                    outputs=(TxOut("bob", 5_000_000),),
                    proposals=(GovActionProposal("gov1", "InfoAction", 0, "stake_r"),),
                    votes=(GovVote("gov1", "DRep", "drep1", "Yes"),),
                ),
            ),
        )
    )
    store.close()


def run(tmp_path: Path, *args: str) -> tuple[int, str]:
    db = str(tmp_path / "c.db")
    if not (tmp_path / "c.db").exists():
        populate(db)
    result = CliRunner().invoke(main, ["--db", db, *args])
    return result.exit_code, result.output


def test_tip(tmp_path: Path) -> None:
    code, out = run(tmp_path, "tip")
    assert code == 0
    assert "block 2" in out


def test_tip_on_empty_db(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.db")
    SqliteStore(db).close()
    result = CliRunner().invoke(main, ["--db", db, "tip"])
    assert "no blocks" in result.output


def test_block_found_and_missing(tmp_path: Path) -> None:
    code, out = run(tmp_path, "block", "b1")
    assert code == 0
    assert "block 1" in out

    code, out = run(tmp_path, "block", "nope")
    assert code == 1
    assert "not found" in out


def test_tx_found_and_missing(tmp_path: Path) -> None:
    code, out = run(tmp_path, "tx", "tx2")
    assert code == 0
    assert "tx1#0" in out  # its input
    assert "bob" in out  # its output

    code, _ = run(tmp_path, "tx", "ghost")
    assert code == 1


def test_balance_pools_account_governance(tmp_path: Path) -> None:
    _, out = run(tmp_path, "balance", "bob")
    assert "5000000 lovelace" in out

    _, out = run(tmp_path, "pools")
    assert "pool1" in out

    _, out = run(tmp_path, "account", "stake_alice")
    assert "registered: True" in out
    assert "pool1" in out

    _, out = run(tmp_path, "governance")
    assert "gov1" in out
    assert "Yes" in out
