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

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from chainidx.event import EventBus
from chainidx.explorer import create_explorer_app
from chainidx.network import NetworkParams
from chainidx.store import Store

_LIVE_HTML = (Path(__file__).parent / "web" / "live.html").read_text()


def create_live_app(store: Store, bus: EventBus, network: NetworkParams | None = None) -> FastAPI:
    """The explorer app plus a ``/live`` page and a ``/stream`` WebSocket."""
    app = create_explorer_app(store, network)

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


async def _snapshot_loop(store: Store, socket_path: str, magic: int) -> None:  # pragma: no cover
    """Periodically refresh the live-stake snapshot via local-state-query."""
    import asyncio

    from chainidx.localstate import LocalStateClient

    client = LocalStateClient(socket_path, magic)
    while True:
        try:
            snap = await client.snapshot()
            store.record_stake_distribution(
                {p.pool_id: p.stake for p in snap.stake_distribution},
                int(snap.protocol_params.get("n_opt", 0)),
            )
            credentials = store.registered_stake_credentials()
            if credentials:
                states = await client.account_states(credentials)
                store.record_account_states(list(states.values()))
        except Exception:
            pass
        await asyncio.sleep(20)


async def _run_live(socket_path: str, magic: int, db: str) -> None:  # pragma: no cover
    import asyncio

    import uvicorn

    from chainidx.api import load_network
    from chainidx.follow import Follower
    from chainidx.node import NodeSource
    from chainidx.store import SqliteStore

    store = SqliteStore(db)
    bus = EventBus()
    source = NodeSource(socket_path, magic)
    follower = Follower(source, store, bus=bus)
    app = create_live_app(store, bus, load_network())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
    print("live view on http://127.0.0.1:8000/live")
    await asyncio.gather(server.serve(), follower.run(), _snapshot_loop(store, socket_path, magic))


def _main() -> None:  # pragma: no cover
    import asyncio
    import os

    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH", "")
    asyncio.run(_run_live(socket_path, 42, os.environ.get("CHAINIDX_DB", "chain.db")))


if __name__ == "__main__":  # pragma: no cover
    _main()
