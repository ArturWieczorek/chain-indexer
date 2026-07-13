"""The indexer pipeline: one small module per thing we index.

This is the project's second design seam. Instead of one giant function that
knows about every table, we have a list of **indexers**, each responsible for one
concern. The store walks each transaction in a block and hands it to every
indexer in turn. Adding a new kind of data later (staking in chapter 06,
governance in chapter 07) means writing a new indexer and adding it to the list;
nothing else changes.

An indexer only handles the *forward* direction (a new block arrived). It does
not need to know how to undo itself: because every row it writes carries a
``block_id``, the generic rollback engine in chapter 05 can delete a block's rows
without any per-indexer help.

The two indexers here handle the movement of value:

- ``OutputIndexer`` records each transaction output (who received what), plus any
  native assets on it.
- ``InputIndexer`` records each input and marks the output it consumes as spent,
  by stamping ``consumed_by_tx_id`` on it. An address's balance is then just the
  sum of its outputs that have not been consumed.

Order matters: outputs are indexed before inputs, so that a transaction which
spends an earlier transaction in the same block finds that output already
present.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from chainidx.model import (
    DRepRegistration,
    PoolRegistration,
    PoolRetirement,
    StakeDelegation,
    StakeDeregistration,
    StakeRegistration,
    Tx,
)


class Indexer(Protocol):
    """One concern's view of a transaction."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        """Write this concern's rows for one transaction."""
        ...


class OutputIndexer:
    """Records transaction outputs and their native assets."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for index_no, out in enumerate(tx.outputs):
            cur = conn.execute(
                "INSERT INTO tx_out (tx_id, block_id, index_no, address, lovelace) "
                "VALUES (?, ?, ?, ?, ?)",
                (tx_db_id, block_id, index_no, out.address, out.lovelace),
            )
            tx_out_id = cur.lastrowid
            for asset in out.assets:
                conn.execute(
                    "INSERT INTO ma_tx_out (tx_out_id, block_id, policy_id, asset_name, quantity) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (tx_out_id, block_id, asset.policy_id, asset.asset_name, asset.quantity),
                )


class InputIndexer:
    """Records transaction inputs and marks the outputs they consume as spent."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for txin in tx.inputs:
            conn.execute(
                "INSERT INTO tx_in (tx_in_id, block_id, tx_out_hash, tx_out_index) "
                "VALUES (?, ?, ?, ?)",
                (tx_db_id, block_id, txin.tx_id, txin.index),
            )
            # Mark the referenced output spent. If we never indexed that output
            # (for example a genesis output when syncing from mid-chain), this
            # affects zero rows, which is exactly what we want.
            conn.execute(
                "UPDATE tx_out SET consumed_by_tx_id = ? "
                "WHERE index_no = ? AND tx_id = (SELECT id FROM tx WHERE hash = ?)",
                (tx_db_id, txin.index, txin.tx_id),
            )


class CertIndexer:
    """Records Shelley staking and pool certificates found in a transaction.

    Each certificate kind lands in its own table. We dispatch on the certificate
    type; because the certificate classes are a closed union, the type checker
    makes sure we handle every one of them.
    """

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for cert in tx.certificates:
            if isinstance(cert, StakeRegistration):
                conn.execute(
                    "INSERT INTO stake_registration (block_id, tx_id, addr) VALUES (?, ?, ?)",
                    (block_id, tx_db_id, cert.stake_address),
                )
            elif isinstance(cert, StakeDeregistration):
                conn.execute(
                    "INSERT INTO stake_deregistration (block_id, tx_id, addr) VALUES (?, ?, ?)",
                    (block_id, tx_db_id, cert.stake_address),
                )
            elif isinstance(cert, StakeDelegation):
                conn.execute(
                    "INSERT INTO delegation (block_id, tx_id, addr, pool_id) VALUES (?, ?, ?, ?)",
                    (block_id, tx_db_id, cert.stake_address, cert.pool_id),
                )
            elif isinstance(cert, PoolRegistration):
                conn.execute(
                    "INSERT INTO pool_registration "
                    "(block_id, tx_id, pool_id, pledge, margin, reward_addr) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        block_id,
                        tx_db_id,
                        cert.pool_id,
                        cert.pledge,
                        cert.margin,
                        cert.reward_address,
                    ),
                )
            elif isinstance(cert, PoolRetirement):
                conn.execute(
                    "INSERT INTO pool_retirement (block_id, tx_id, pool_id, retiring_epoch) "
                    "VALUES (?, ?, ?, ?)",
                    (block_id, tx_db_id, cert.pool_id, cert.retiring_epoch),
                )
            elif isinstance(cert, DRepRegistration):
                conn.execute(
                    "INSERT INTO drep_registration (block_id, tx_id, drep_id, deposit) "
                    "VALUES (?, ?, ?, ?)",
                    (block_id, tx_db_id, cert.drep_id, cert.deposit),
                )
            else:  # DRepDeregistration - the type checker knows this is the last case
                conn.execute(
                    "INSERT INTO drep_deregistration (block_id, tx_id, drep_id) VALUES (?, ?, ?)",
                    (block_id, tx_db_id, cert.drep_id),
                )


class GovIndexer:
    """Records Conway governance: action proposals and votes.

    Proposals and votes are not certificates; they are their own fields in a
    Conway transaction body. So they get their own indexer, added to the
    pipeline alongside the others.
    """

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for proposal in tx.proposals:
            conn.execute(
                "INSERT INTO gov_action_proposal "
                "(block_id, tx_id, gov_action_id, action_type, deposit, return_addr) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    block_id,
                    tx_db_id,
                    proposal.gov_action_id,
                    proposal.action_type,
                    proposal.deposit,
                    proposal.return_address,
                ),
            )
        for vote in tx.votes:
            conn.execute(
                "INSERT INTO voting_procedure "
                "(block_id, tx_id, gov_action_id, voter_role, voter_id, vote) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    block_id,
                    tx_db_id,
                    vote.gov_action_id,
                    vote.voter_role,
                    vote.voter_id,
                    vote.vote,
                ),
            )


def default_indexers() -> tuple[Indexer, ...]:
    """The indexers a store runs by default, in the order they must run."""
    return (OutputIndexer(), InputIndexer(), CertIndexer(), GovIndexer())
