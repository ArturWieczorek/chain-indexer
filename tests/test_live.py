"""Tests for the live app: the /live page serves and the API stays mounted."""

from fastapi.testclient import TestClient

from chainidx.event import EventBus
from chainidx.live import create_live_app
from chainidx.store import SqliteStore


def test_live_page_and_api() -> None:
    client = TestClient(create_live_app(SqliteStore(), EventBus()))

    page = client.get("/live")
    assert page.status_code == 200
    assert "chain-indexer" in page.text
    assert "Live feed" in page.text

    # The explorer page and API are still available under the live app.
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
