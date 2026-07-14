"""The live view: stream indexer events to the browser over a WebSocket.

This ties the event bus (chapter 16) to a web page. The follower publishes events
to a shared ``EventBus``; the ``/stream`` WebSocket endpoint subscribes to the bus
and forwards each event to the connected browser; the ``/live`` page renders them
as they arrive - new blocks scrolling in, and a reorg visibly rolling state back.

Follower and web server share one process and one asyncio event loop, so the
follower's ``publish`` and the endpoint's ``queue.get`` are on the same loop -
which is what makes the hand-off simple. ``make live`` starts both together.

The WebSocket handler and the combined runner need a live loop and a real node,
so they are excluded from the coverage gate, like the other live-only code; the
event bus, the block-to-events mapping, and the ``/live`` route are all tested.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from chainidx.event import EventBus
from chainidx.explorer import create_explorer_app
from chainidx.model import MempoolStatus
from chainidx.network import NetworkParams
from chainidx.store import Store

_LIVE_HTML = (Path(__file__).parent / "web" / "live.html").read_text()


def create_live_app(
    store: Store,
    bus: EventBus,
    network: NetworkParams | None = None,
    mempool_source: Callable[[], MempoolStatus] | None = None,
    metadata_fetcher: Callable[[str], dict[str, object] | None] | None = None,
    ipfs_gateway: str | None = None,
) -> FastAPI:
    """The explorer app plus a ``/live`` page and a ``/stream`` WebSocket."""
    app = create_explorer_app(store, network, mempool_source, metadata_fetcher, ipfs_gateway)

    @app.get("/live", response_class=HTMLResponse)
    def live_page() -> str:
        return _LIVE_HTML

    @app.websocket("/stream")
    async def stream(websocket: WebSocket) -> None:  # pragma: no cover - needs a live loop
        await websocket.accept()
        queue = bus.subscribe()
        try:
            while True:
                await websocket.send_json(await queue.get())
        except WebSocketDisconnect:
            bus.unsubscribe(queue)

    return app


async def _snapshot_loop(  # pragma: no cover
    store: Store, socket_path: str, magic: int, keep_history: bool = False
) -> None:
    """Periodically refresh the live-stake snapshot via local-state-query."""
    import asyncio

    from chainidx.localstate import LocalStateClient

    client = LocalStateClient(socket_path, magic)
    while True:
        try:
            snap = await client.snapshot()
            stakes = {p.pool_id: p.stake for p in snap.stake_distribution}
            store.record_stake_distribution(stakes, int(snap.protocol_params.get("n_opt", 0)))
            store.record_protocol_params(snap.protocol_params)
            if keep_history:
                store.record_stake_history(snap.epoch, stakes)
            credentials = store.registered_stake_credentials()
            if credentials:
                states = await client.account_states(credentials)
                store.record_account_states(list(states.values()))
        except Exception:
            pass
        await asyncio.sleep(20)


async def _run_live(cfg: object) -> None:  # pragma: no cover
    import asyncio

    import uvicorn

    from chainidx.config import Config
    from chainidx.follow import Follower
    from chainidx.indexers import indexers_for
    from chainidx.mempoolclient import MempoolClient
    from chainidx.network import NetworkParams
    from chainidx.node import NodeSource
    from chainidx.offchain import fetch_pool_metadata
    from chainidx.postgresstore import PostgresStore
    from chainidx.store import SqliteStore

    assert isinstance(cfg, Config)
    indexers = indexers_for(cfg.features)
    # Postgres backend when a DSN is configured (chapter 63), else SQLite. Importing
    # PostgresStore does not load psycopg; that happens only on instantiation.
    store = (
        PostgresStore(cfg.postgres_dsn, indexers=indexers)
        if cfg.postgres_dsn
        else SqliteStore(cfg.db_path, indexers=indexers)
    )
    bus = EventBus()
    source = NodeSource(cfg.socket_path, cfg.network_magic)
    follower = Follower(source, store, bus=bus)
    mempool_client = MempoolClient(cfg.socket_path, cfg.network_magic)
    network = NetworkParams.from_genesis(cfg.genesis_path) if cfg.genesis_path else None
    fetcher = fetch_pool_metadata if cfg.fetch_metadata else None
    gateway = cfg.ipfs_gateway or None
    app = create_live_app(store, bus, network, mempool_client.status_sync, fetcher, gateway)
    server = uvicorn.Server(
        uvicorn.Config(app, host=cfg.host, port=cfg.port, log_level="warning")
    )
    print(f"live view on http://{cfg.host}:{cfg.port}/live")
    await asyncio.gather(
        server.serve(),
        follower.run(),
        _snapshot_loop(store, cfg.socket_path, cfg.network_magic, cfg.stake_history),
    )


def _main() -> None:  # pragma: no cover
    import asyncio

    from chainidx import config

    asyncio.run(_run_live(config.load()))


if __name__ == "__main__":  # pragma: no cover
    _main()
