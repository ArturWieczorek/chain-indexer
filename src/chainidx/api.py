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

from chainidx.model import Asset, Block, TxDetail, TxOut
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


def _block(block: Block) -> dict[str, Any]:
    return {
        "hash": block.block_hash,
        "block_no": block.block_no,
        "slot_no": block.slot_no,
        "prev_hash": block.prev_hash,
        "tx_count": len(block.txs),
        "tx_hashes": [t.tx_id for t in block.txs],
    }


def _tx(detail: TxDetail) -> dict[str, Any]:
    return {
        "tx_id": detail.tx_id,
        "block_hash": detail.block_hash,
        "inputs": [{"tx_id": i.tx_id, "index": i.index} for i in detail.inputs],
        "outputs": [_output(o) for o in detail.outputs],
    }


def create_app(store: Store) -> FastAPI:
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
        return _block(block)

    @app.get("/blocks")
    def blocks(limit: int = 20) -> list[dict[str, Any]]:
        return [_block(b) for b in store.latest_blocks(limit)]

    @app.get("/blocks/{block_hash}")
    def block(block_hash: str) -> dict[str, Any]:
        found = store.get_block(block_hash)
        if found is None:
            raise HTTPException(status_code=404, detail="block not found")
        return _block(found)

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
    def pools() -> list[str]:
        return list(store.pools())

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

    return app


def create_default_app() -> FastAPI:  # pragma: no cover - needs a real database
    """Build an app over a real SQLite database (used by ``make api``)."""
    import os

    from chainidx.store import SqliteStore

    return create_app(SqliteStore(os.environ.get("CHAINIDX_DB", "chain.db")))
