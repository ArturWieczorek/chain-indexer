"""The block explorer: a browsable web UI over the query API.

The explorer is a single static HTML page (``web/index.html``) that talks to the
chapter 13 REST API from the browser with ``fetch``. This module wires the two
together: it takes the API app and adds one route, ``GET /``, that serves the
page. Everything else the page needs (blocks, transactions, addresses) is already
an API endpoint.

Keeping the UI as one static file with vanilla JavaScript is deliberate: no build
step, no framework, nothing to learn beyond the page itself. ``make explorer``
serves it over a real database.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from chainidx.api import create_app
from chainidx.network import NetworkParams
from chainidx.store import Store

_INDEX_HTML = (Path(__file__).parent / "web" / "index.html").read_text()


def create_explorer_app(store: Store, network: NetworkParams | None = None) -> FastAPI:
    """The API app plus the explorer page served at ``/``."""
    app = create_app(store, network)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _INDEX_HTML

    return app


def create_default_explorer_app() -> FastAPI:  # pragma: no cover - needs a database
    import os

    from chainidx.api import load_network
    from chainidx.store import SqliteStore

    return create_explorer_app(SqliteStore(os.environ.get("CHAINIDX_DB", "chain.db")), load_network())


def _main() -> None:  # pragma: no cover - starts a server
    import uvicorn

    uvicorn.run(create_default_explorer_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":  # pragma: no cover
    _main()
