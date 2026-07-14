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

import json
import sqlite3
from typing import Protocol

from chainidx.model import (
    Certificate,
    CommitteeAuthHot,
    DRepDeregistration,
    DRepRegistration,
    DRepUpdate,
    PoolRegistration,
    PoolRetirement,
    StakeDelegation,
    StakeDeregistration,
    StakeRegistration,
    Tx,
    VoteDelegation,
)


class Indexer(Protocol):
    """One concern's view of a transaction."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        """Write this concern's rows for one transaction."""
        ...


def stake_credential_of(address: str) -> str | None:
    """The 28-byte stake credential embedded in a base address, or ``None``.

    A base address is a 57-byte value: a 1-byte header, a 28-byte payment
    credential, then a 28-byte stake credential (bytes 29..57). Enterprise and
    pointer addresses, and non-hex test ids, have no stake part.
    """
    try:
        raw = bytes.fromhex(address)
    except ValueError:
        return None
    if len(raw) == 57 and (raw[0] >> 4) in (0, 1, 2, 3):
        return raw[29:57].hex()
    return None


class OutputIndexer:
    """Records transaction outputs and their native assets."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for index_no, out in enumerate(tx.outputs):
            cur = conn.execute(
                "INSERT INTO tx_out (tx_id, block_id, index_no, address, lovelace, stake_cred) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tx_db_id,
                    block_id,
                    index_no,
                    out.address,
                    out.lovelace,
                    stake_credential_of(out.address),
                ),
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


def certificate_fields(cert: Certificate) -> tuple[str, str, str]:
    """Map a certificate to ``(category label, subject id, detail)``.

    The label is the human category the Certificates browser groups by; the
    subject is the primary id the certificate acts on; the detail is a secondary
    field worth showing (the pool for a delegation, the epoch for a retirement).
    """
    if isinstance(cert, StakeRegistration):
        return "Stake Key Registration", cert.stake_address, ""
    if isinstance(cert, StakeDeregistration):
        return "Stake Key Deregistration", cert.stake_address, ""
    if isinstance(cert, StakeDelegation):
        return "Delegation", cert.stake_address, cert.pool_id
    if isinstance(cert, VoteDelegation):
        return "Vote Delegation", cert.stake_address, cert.drep
    if isinstance(cert, PoolRegistration):
        return "Pool Registration", cert.pool_id, f"pledge {cert.pledge}, margin {cert.margin}"
    if isinstance(cert, PoolRetirement):
        return "Pool Deregistration", cert.pool_id, f"epoch {cert.retiring_epoch}"
    if isinstance(cert, DRepRegistration):
        return "DRep Registration", cert.drep_id, f"deposit {cert.deposit}"
    if isinstance(cert, DRepDeregistration):
        return "DRep Deregistration", cert.drep_id, ""
    if isinstance(cert, DRepUpdate):
        return "DRep Update", cert.drep_id, ""
    if isinstance(cert, CommitteeAuthHot):
        return "Committee Hot Key Authorization", cert.cold_credential, cert.hot_credential
    return "Committee Cold Key Resignation", cert.cold_credential, ""


class CertIndexer:
    """Records certificates found in a transaction.

    Every certificate is recorded in the flat ``certificate`` table (so the
    Certificates browser can list them by category). The kinds that also back
    other pages - pools, DReps, accounts - additionally land in their own typed
    table. The four Conway-only kinds without a dedicated page (vote delegation,
    DRep update, and the two committee certificates) live only in the flat table.
    """

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for cert in tx.certificates:
            cert_type, subject, detail = certificate_fields(cert)
            conn.execute(
                "INSERT INTO certificate (block_id, tx_id, cert_type, subject, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (block_id, tx_db_id, cert_type, subject, detail),
            )
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
            elif isinstance(cert, DRepDeregistration):
                conn.execute(
                    "INSERT INTO drep_deregistration (block_id, tx_id, drep_id) VALUES (?, ?, ?)",
                    (block_id, tx_db_id, cert.drep_id),
                )
            # Vote delegation, DRep update, and the committee certificates have no
            # dedicated table yet; the flat certificate row above is enough.


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


class WithdrawalIndexer:
    """Records reward withdrawals found in a transaction."""

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        for w in tx.withdrawals:
            conn.execute(
                "INSERT INTO withdrawal (block_id, tx_id, stake_address, amount) "
                "VALUES (?, ?, ?, ?)",
                (block_id, tx_db_id, w.stake_address, w.amount),
            )


class AssetMetadataIndexer:
    """Records CIP-25 asset metadata from a mint transaction's metadata.

    CIP-25 puts NFT metadata under transaction-metadata label 721, as
    ``{policy_id: {asset_name: {name, image, ...}}}`` (plus an optional
    ``version``). We already decode transaction metadata to JSON (chapter 35), so
    here we read label 721 out of it and store one row per asset, keyed by the
    asset name in hex to match how asset names are stored elsewhere.
    """

    def index_tx(self, conn: sqlite3.Connection, block_id: int, tx_db_id: int, tx: Tx) -> None:
        if not tx.metadata:
            return
        cip25 = json.loads(tx.metadata).get("721")
        if not isinstance(cip25, dict):
            return
        for policy_id, assets in cip25.items():
            if not isinstance(assets, dict):
                continue  # skips the optional "version" entry
            for name_key, fields in assets.items():
                conn.execute(
                    "INSERT INTO asset_metadata "
                    "(block_id, tx_id, policy_id, asset_name, metadata) VALUES (?, ?, ?, ?, ?)",
                    (
                        block_id,
                        tx_db_id,
                        policy_id,
                        name_key.encode("utf-8").hex(),
                        json.dumps(fields),
                    ),
                )


def default_indexers() -> tuple[Indexer, ...]:
    """The indexers a store runs by default, in the order they must run."""
    return (
        OutputIndexer(),
        InputIndexer(),
        CertIndexer(),
        GovIndexer(),
        WithdrawalIndexer(),
        AssetMetadataIndexer(),
    )
