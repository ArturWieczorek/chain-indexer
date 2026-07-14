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

from typing import Any

from fastapi import FastAPI, HTTPException

from chainidx.model import Asset, Block, EpochSummary, PoolSummary, TxDetail, TxOut
from chainidx.network import NetworkParams
from chainidx.store import Store


def _asset(asset: Asset) -> dict[str, Any]:
    return {
        "policy_id": asset.policy_id,
        "asset_name": asset.asset_name,
        "quantity": asset.quantity,
    }


def _output(output: TxOut) -> dict[str, Any]:
    return {
        "address": output.address,
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
    if network is not None:
        out["epoch_no"] = network.epoch_of(block.slot_no)
        out["time"] = network.slot_time(block.slot_no)
    return out


def _tx(detail: TxDetail) -> dict[str, Any]:
    return {
        "tx_id": detail.tx_id,
        "block_hash": detail.block_hash,
        "inputs": [{"tx_id": i.tx_id, "index": i.index} for i in detail.inputs],
        "outputs": [_output(o) for o in detail.outputs],
    }


def _pool(summary: PoolSummary) -> dict[str, Any]:
    return {
        "pool_id": summary.pool_id,
        "blocks_minted": summary.blocks_minted,
        "delegators": summary.delegators,
        "pledge": summary.pledge,
        "margin": summary.margin,
        "reward_address": summary.reward_address,
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
        return _tx(detail)

    @app.get("/addresses/{address}")
    def address(address: str) -> dict[str, Any]:
        return {
            "address": address,
            "balance": store.balance(address),
            "utxos": [_output(o) for o in store.utxos(address)],
        }

    @app.get("/assets")
    def assets() -> list[dict[str, Any]]:
        return [_asset(a) for a in store.assets()]

    @app.get("/pools")
    def pools() -> list[dict[str, Any]]:
        return [_pool(p) for p in store.pool_summaries()]

    @app.get("/pools/{pool_id}")
    def pool(pool_id: str) -> dict[str, Any]:
        summary = store.pool_detail(pool_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="pool not found")
        out = _pool(summary)
        out["recent_blocks"] = store.recent_blocks_by_pool(pool_id)
        return out

    @app.get("/accounts/{stake_address}")
    def account(stake_address: str) -> dict[str, Any]:
        return {
            "stake_address": stake_address,
            "registered": store.is_stake_registered(stake_address),
            "delegated_to": store.delegation_of(stake_address),
        }

    @app.get("/governance/actions")
    def governance_actions() -> list[dict[str, Any]]:
        return [
            {"gov_action_id": g, "tally": store.vote_tally(g)} for g in store.governance_actions()
        ]

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
