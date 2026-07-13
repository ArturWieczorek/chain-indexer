"""Tests for Conway governance: DReps, proposals, votes, and rollback."""

from chainidx.model import (
    Block,
    DRepDeregistration,
    DRepRegistration,
    GovActionProposal,
    GovVote,
    Tx,
)
from chainidx.store import SqliteStore


def blk(block_no: int, block_hash: str, prev_hash: str, txs: tuple[Tx, ...]) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=txs,
    )


def test_dreps_register_and_retire() -> None:
    store = SqliteStore()
    store.apply_block(
        blk(1, "b1", "genesis", (Tx("tx1", certificates=(DRepRegistration("drep1", 500),)),))
    )
    assert store.dreps() == ("drep1",)

    store.apply_block(blk(2, "b2", "b1", (Tx("tx2", certificates=(DRepDeregistration("drep1"),)),)))
    assert store.dreps() == ()
    store.close()


def test_a_governance_action_is_recorded() -> None:
    store = SqliteStore()
    proposal = GovActionProposal(
        gov_action_id="gov1",
        action_type="TreasuryWithdrawals",
        deposit=100_000,
        return_address="stake_x",
    )
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", proposals=(proposal,)),)))
    assert store.governance_actions() == ("gov1",)
    store.close()


def test_votes_are_tallied() -> None:
    store = SqliteStore()
    proposal = GovActionProposal("gov1", "InfoAction", 0, "stake_x")
    votes = (
        GovVote("gov1", "DRep", "drep1", "Yes"),
        GovVote("gov1", "DRep", "drep2", "Yes"),
        GovVote("gov1", "SPO", "pool1", "No"),
        GovVote("gov1", "ConstitutionalCommittee", "cc1", "Abstain"),
    )
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", proposals=(proposal,), votes=votes),)))

    assert store.vote_tally("gov1") == {"Yes": 2, "No": 1, "Abstain": 1}
    assert store.vote_tally("unknown") == {}
    store.close()


def test_governance_rolls_back_with_its_block() -> None:
    store = SqliteStore()
    store.apply_block(
        blk(1, "b1", "genesis", (Tx("tx1", certificates=(DRepRegistration("drep1", 500),)),))
    )
    proposal = GovActionProposal("gov1", "InfoAction", 0, "stake_x")
    store.apply_block(
        blk(
            2,
            "b2",
            "b1",
            (Tx("tx2", proposals=(proposal,), votes=(GovVote("gov1", "DRep", "drep1", "Yes"),)),),
        )
    )
    assert store.governance_actions() == ("gov1",)
    assert store.vote_tally("gov1") == {"Yes": 1}

    # Roll back the proposal's block. The proposal, its votes disappear; the
    # DRep registered in block 1 stays.
    store.rollback_to(blk(1, "b1", "genesis", ()).point)

    assert store.governance_actions() == ()
    assert store.vote_tally("gov1") == {}
    assert store.dreps() == ("drep1",)
    store.close()
