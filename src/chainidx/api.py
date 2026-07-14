"""A read-only REST API over the indexed data.

The endpoint shapes take inspiration from Blockfrost, the Cardano data API most
people know: ``/blocks/latest``, ``/txs/{hash}``, ``/addresses/{addr}``, and so
on. The API is a thin translation from the store's query methods to JSON; it adds
no logic of its own, which keeps it easy to test.

We build the app with a factory, ``create_app(store)``, so tests can hand it a
store full of synthetic data and drive it with a test client - no server, no
network. ``create_default_app`` (used by ``make api``) opens a real database.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException

from chainidx import bech32
from chainidx.model import (
    Asset,
    AssetDetail,
    Block,
    CertificateRecord,
    CommitteeMember,
    DRepSummary,
    DRepVote,
    EpochSummary,
    GovActionProposal,
    GovActionSummary,
    GovVoteRecord,
    PoolSummary,
    ResolvedInput,
    TxDetail,
    TxOut,
    WithdrawalRecord,
)
from chainidx.network import NetworkParams
from chainidx.store import Store


def _pool_display(pool_id_hex: str) -> str:
    """Pool id as bech32 (pool1...), or unchanged if it is not a hex hash."""
    try:
        return bech32.pool_to_bech32(pool_id_hex)
    except ValueError:
        return pool_id_hex


def _address_display(address_hex: str) -> str:
    """Address as bech32, or unchanged if it is not raw hex (e.g. test data)."""
    try:
        return bech32.address_to_bech32(address_hex)
    except (ValueError, IndexError):
        return address_hex


def _to_hex(arg: str, *prefixes: str) -> str:
    """Decode a bech32 argument to hex if it has one of the prefixes."""
    if any(arg.startswith(p) for p in prefixes):
        try:
            return bech32.decode(arg)[1].hex()
        except ValueError:
            return arg
    return arg


def _stake_display(credential_hex: str) -> str:
    """A 28-byte stake credential as a ``stake_test1...`` address (testnet key)."""
    try:
        return bech32.address_to_bech32("e0" + credential_hex)
    except (ValueError, IndexError):
        return credential_hex


def _stake_credential(arg: str) -> str:
    """Turn a stake address (``stake...``) into its 28-byte credential hex.

    A stake address is a 1-byte header plus the credential, so we drop the
    header. A plain hex credential (or test id) passes through unchanged.
    """
    if arg.startswith("stake"):
        try:
            return bech32.decode(arg)[1][1:].hex()
        except ValueError:
            return arg
    return arg


def _asset_name_text(asset_name_hex: str) -> str:
    """The asset name decoded as printable UTF-8 text, or ``""`` if it is not."""
    try:
        text = bytes.fromhex(asset_name_hex).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""
    return text if text.isprintable() else ""


def _asset(asset: Asset) -> dict[str, Any]:
    return {
        "policy_id": asset.policy_id,
        "asset_name": asset.asset_name,
        "quantity": asset.quantity,
    }


def _asset_detail(detail: AssetDetail) -> dict[str, Any]:
    return {
        "policy_id": detail.policy_id,
        "asset_name": detail.asset_name,
        "asset_name_text": _asset_name_text(detail.asset_name),
        "quantity": detail.quantity,
        "holders": detail.holders,
    }


def _output(output: TxOut) -> dict[str, Any]:
    return {
        "address": _address_display(output.address),
        "lovelace": output.lovelace,
        "assets": [_asset(a) for a in output.assets],
    }


def _block(block: Block, network: NetworkParams | None = None) -> dict[str, Any]:
    out = {
        "hash": block.block_hash,
        "block_no": block.block_no,
        "slot_no": block.slot_no,
        "prev_hash": block.prev_hash,
        "tx_count": len(block.txs),
        "tx_hashes": [t.tx_id for t in block.txs],
    }
    if block.issuer:
        out["issuer"] = _pool_display(block.issuer)
    if network is not None:
        out["epoch_no"] = network.epoch_of(block.slot_no)
        out["time"] = network.slot_time(block.slot_no)
    return out


def _resolved_input(i: ResolvedInput) -> dict[str, Any]:
    return {
        "tx_id": i.tx_id,
        "index": i.index,
        "address": _address_display(i.address) if i.address else "",
        "lovelace": i.lovelace,
        "assets": [_asset(a) for a in i.assets],
        # False when the consumed output was never indexed (a genesis/faucet
        # UTxO): the explorer then shows the reference without a dead link.
        "resolved": i.address != "",
    }


def _tx(detail: TxDetail) -> dict[str, Any]:
    return {
        "tx_id": detail.tx_id,
        "block_hash": detail.block_hash,
        "fee": detail.fee,
        "metadata": json.loads(detail.metadata) if detail.metadata else None,
        "inputs": [_resolved_input(i) for i in detail.inputs],
        "outputs": [_output(o) for o in detail.outputs],
    }


def _pool(summary: PoolSummary) -> dict[str, Any]:
    return {
        "pool_id": _pool_display(summary.pool_id),
        "blocks_minted": summary.blocks_minted,
        "delegators": summary.delegators,
        "pledge": summary.pledge,
        "margin": summary.margin,
        "reward_address": _address_display(summary.reward_address),
        "live_stake": summary.live_stake,
        "saturation": summary.saturation,
    }


def _gov_action(summary: GovActionSummary) -> dict[str, Any]:
    return {
        "gov_action_id": summary.gov_action_id,
        "action_type": summary.action_type,
        "deposit": summary.deposit,
        "tally": {"yes": summary.yes, "no": summary.no, "abstain": summary.abstain},
    }


def _vote(record: GovVoteRecord) -> dict[str, Any]:
    return {
        "voter_role": record.voter_role,
        "voter_id": record.voter_id,
        "vote": record.vote,
        "gov_action_id": record.gov_action_id,
    }


def _proposal(proposal: GovActionProposal) -> dict[str, Any]:
    return {
        "gov_action_id": proposal.gov_action_id,
        "action_type": proposal.action_type,
        "deposit": proposal.deposit,
    }


def _committee_member(member: CommitteeMember) -> dict[str, Any]:
    return {
        "cold_credential": member.cold_credential,
        "hot_credential": member.hot_credential,
        "resigned": member.resigned,
    }


def _withdrawal(record: WithdrawalRecord) -> dict[str, Any]:
    return {
        "stake_address": _address_display(record.stake_address),
        "amount": record.amount,
        "tx_hash": record.tx_hash,
    }


def _drep(summary: DRepSummary) -> dict[str, Any]:
    return {
        "drep_id": summary.drep_id,
        "deposit": summary.deposit,
        "votes_cast": summary.votes_cast,
    }


def _drep_vote(vote: DRepVote) -> dict[str, Any]:
    return {
        "gov_action_id": vote.gov_action_id,
        "action_type": vote.action_type,
        "vote": vote.vote,
    }


def _cert_subject_display(cert_type: str, subject: str) -> str:
    """A friendlier subject: bech32 for pools and stake keys, hex otherwise."""
    if cert_type.startswith("Pool"):
        return _pool_display(subject)
    if cert_type.startswith(("Stake Key", "Delegation", "Vote Delegation")):
        return _stake_display(subject)
    return subject


def _certificate(record: CertificateRecord) -> dict[str, Any]:
    return {
        "cert_type": record.cert_type,
        "subject": record.subject,
        "subject_display": _cert_subject_display(record.cert_type, record.subject),
        "detail": record.detail,
        "tx_hash": record.tx_hash,
    }


def _epoch(summary: EpochSummary, network: NetworkParams | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "epoch_no": summary.epoch_no,
        "block_count": summary.block_count,
        "tx_count": summary.tx_count,
        "start_slot": summary.start_slot,
        "end_slot": summary.end_slot,
    }
    if network is not None:
        out["start_time"] = network.epoch_start_time(summary.epoch_no)
        out["end_time"] = network.slot_time(summary.end_slot)
    return out


def create_app(store: Store, network: NetworkParams | None = None) -> FastAPI:
    app = FastAPI(title="chain-indexer", description="A mini Cardano chain indexer API")

    @app.get("/health")
    def health() -> dict[str, Any]:
        tip = store.tip()
        return {"status": "ok", "tip_height": tip.block_no if tip is not None else None}

    @app.get("/blocks/latest")
    def blocks_latest() -> dict[str, Any]:
        tip = store.tip()
        if tip is None:
            raise HTTPException(status_code=404, detail="no blocks indexed yet")
        block = store.get_block(tip.point.block_hash)
        assert block is not None  # the tip block always exists
        return _block(block, network)

    @app.get("/blocks")
    def blocks(limit: int = 20) -> list[dict[str, Any]]:
        return [_block(b, network) for b in store.latest_blocks(limit)]

    @app.get("/blocks/height/{height}")
    def block_by_height(height: int) -> dict[str, Any]:
        found = store.get_block_by_number(height)
        if found is None:
            raise HTTPException(status_code=404, detail="no block at that height")
        return _block(found, network)

    @app.get("/blocks/slot/{slot}")
    def block_by_slot(slot: int) -> dict[str, Any]:
        found = store.get_block_by_slot(slot)
        if found is None:
            raise HTTPException(status_code=404, detail="no block at that slot")
        return _block(found, network)

    @app.get("/blocks/{block_hash}")
    def block(block_hash: str) -> dict[str, Any]:
        found = store.get_block(block_hash)
        if found is None:
            raise HTTPException(status_code=404, detail="block not found")
        return _block(found, network)

    @app.get("/txs/{tx_hash}")
    def tx(tx_hash: str) -> dict[str, Any]:
        detail = store.get_tx(tx_hash)
        if detail is None:
            raise HTTPException(status_code=404, detail="transaction not found")
        out = _tx(detail)
        out["certificates"] = [_certificate(c) for c in store.certificates_for_tx(tx_hash)]
        out["proposals"] = [_proposal(p) for p in store.proposals_for_tx(tx_hash)]
        out["votes"] = [_vote(v) for v in store.votes_for_tx(tx_hash)]
        out["withdrawals"] = [_withdrawal(w) for w in store.withdrawals_for_tx(tx_hash)]
        return out

    @app.get("/addresses/{address}")
    def address(address: str) -> dict[str, Any]:
        key = _to_hex(address, "addr", "stake")
        return {
            "address": address,
            "balance": store.balance(key),
            "utxos": [_output(o) for o in store.utxos(key)],
        }

    @app.get("/assets")
    def assets() -> list[dict[str, Any]]:
        return [_asset(a) for a in store.assets()]

    @app.get("/assets/{policy_id}/{asset_name}")
    def asset(policy_id: str, asset_name: str) -> dict[str, Any]:
        detail = store.asset_detail(policy_id, asset_name)
        if detail is None:
            raise HTTPException(status_code=404, detail="asset not found")
        return _asset_detail(detail)

    @app.get("/policies/{policy_id}")
    def policy(policy_id: str) -> dict[str, Any]:
        detail = store.policy_detail(policy_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="policy not found")
        return {
            "policy_id": detail.policy_id,
            "asset_count": detail.asset_count,
            "assets": [_asset_detail(a) for a in detail.assets],
        }

    @app.get("/pools")
    def pools() -> list[dict[str, Any]]:
        return [_pool(p) for p in store.pool_summaries()]

    @app.get("/pools/{pool_id}")
    def pool(pool_id: str) -> dict[str, Any]:
        key = _to_hex(pool_id, "pool")
        summary = store.pool_detail(key)
        if summary is None:
            raise HTTPException(status_code=404, detail="pool not found")
        out = _pool(summary)
        out["recent_blocks"] = store.recent_blocks_by_pool(key)
        out["delegators_list"] = [_stake_display(c) for c in store.pool_delegators(key)]
        return out

    @app.get("/accounts/{stake_address}")
    def account(stake_address: str) -> dict[str, Any]:
        cred = _stake_credential(stake_address)
        state = store.account_state(cred)
        delegated = state.delegated_pool if state and state.delegated_pool else None
        delegated = delegated or store.delegation_of(cred)
        return {
            "stake_address": stake_address,
            "credential": cred,
            "registered": store.is_stake_registered(cred),
            "delegated_to": _pool_display(delegated) if delegated else None,
            "reward": state.reward if state else 0,
            "controlled_stake": store.controlled_stake(cred),
        }

    @app.get("/governance/actions")
    def governance_actions() -> list[dict[str, Any]]:
        return [_gov_action(a) for a in store.governance_action_summaries()]

    @app.get("/governance/actions/{gov_action_id}")
    def governance_action(gov_action_id: str) -> dict[str, Any]:
        match = next(
            (a for a in store.governance_action_summaries() if a.gov_action_id == gov_action_id),
            None,
        )
        if match is None:
            raise HTTPException(status_code=404, detail="governance action not found")
        out = _gov_action(match)
        out["votes"] = [_vote(v) for v in store.governance_action_votes(gov_action_id)]
        return out

    @app.get("/governance/dreps")
    def dreps() -> list[dict[str, Any]]:
        return [_drep(d) for d in store.drep_summaries()]

    @app.get("/governance/dreps/{drep_id}")
    def drep(drep_id: str) -> dict[str, Any]:
        match = next((d for d in store.drep_summaries() if d.drep_id == drep_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="DRep not found")
        out = _drep(match)
        out["votes"] = [_drep_vote(v) for v in store.drep_votes(drep_id)]
        return out

    @app.get("/governance/committee")
    def committee() -> list[dict[str, Any]]:
        return [_committee_member(m) for m in store.committee_members()]

    @app.get("/governance/committee/{cold_credential}")
    def committee_member(cold_credential: str) -> dict[str, Any]:
        member = store.committee_member(cold_credential)
        if member is None:
            raise HTTPException(status_code=404, detail="committee member not found")
        return _committee_member(member)

    @app.get("/withdrawals")
    def withdrawals() -> list[dict[str, Any]]:
        return [_withdrawal(w) for w in store.withdrawals()]

    @app.get("/certificates")
    def certificates(cert_type: str | None = None) -> list[dict[str, Any]]:
        return [_certificate(c) for c in store.certificates(cert_type)]

    @app.get("/certificates/summary")
    def certificate_summary() -> list[dict[str, Any]]:
        return [{"cert_type": t, "count": n} for t, n in store.certificate_summary()]

    @app.get("/epochs")
    def epochs() -> list[dict[str, Any]]:
        if network is None:
            return []
        return [_epoch(s, network) for s in store.epoch_summaries(network.epoch_length)]

    @app.get("/epochs/{epoch_no}")
    def epoch(epoch_no: int) -> dict[str, Any]:
        if network is None:
            raise HTTPException(status_code=404, detail="network parameters not configured")
        summary = store.epoch_summary(epoch_no, network.epoch_length)
        if summary is None:
            raise HTTPException(status_code=404, detail="epoch not found")
        return _epoch(summary, network)

    @app.get("/epochs/{epoch_no}/blocks")
    def epoch_blocks(epoch_no: int) -> list[dict[str, Any]]:
        if network is None:
            raise HTTPException(status_code=404, detail="network parameters not configured")
        return [_block(b, network) for b in store.blocks_in_epoch(epoch_no, network.epoch_length)]

    @app.get("/analytics/summary")
    def analytics_summary() -> dict[str, Any]:
        return {
            "total_blocks": store.block_count(),
            "total_transactions": store.total_transactions(),
            "active_pools": len(store.pools()),
            "dreps": len(store.dreps()),
            "governance_actions": len(store.governance_actions()),
        }

    @app.get("/network")
    def network_state() -> dict[str, Any]:
        if network is None:
            return {"available": False}
        tip = store.tip()
        state: dict[str, Any] = {
            "available": True,
            "system_start": network.system_start,
            "slot_length": network.slot_length,
            "epoch_length": network.epoch_length,
        }
        if tip is not None:
            progress = network.progress(tip.point.slot_no)
            state.update(
                current_epoch=progress.epoch,
                slot_in_epoch=progress.slot_in_epoch,
                epoch_progress=round(progress.fraction, 4),
                tip_time=network.slot_time(tip.point.slot_no),
            )
        return state

    @app.get("/protocol-parameters")
    def protocol_parameters() -> dict[str, int]:
        return store.protocol_params()

    return app


def load_network() -> NetworkParams | None:  # pragma: no cover - reads a file
    """Load network params from ``CHAINIDX_GENESIS`` (a Shelley genesis), if set."""
    import os

    genesis = os.environ.get("CHAINIDX_GENESIS")
    return NetworkParams.from_genesis(genesis) if genesis else None


def create_default_app() -> FastAPI:  # pragma: no cover - needs a real database
    """Build an app over a real SQLite database (used by ``make api``)."""
    import os

    from chainidx.store import SqliteStore

    return create_app(SqliteStore(os.environ.get("CHAINIDX_DB", "chain.db")), load_network())
