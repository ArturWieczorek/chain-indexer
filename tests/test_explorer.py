"""Tests for the explorer: the page serves, and the API still works under it."""

from fastapi.testclient import TestClient

from chainidx.explorer import create_explorer_app
from chainidx.store import SqliteStore


def test_explorer_serves_the_page_and_the_api() -> None:
    client = TestClient(create_explorer_app(SqliteStore()))

    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "chain-indexer explorer" in page.text
    assert "Latest blocks" in page.text

    # The API routes are still mounted alongside the page.
    assert client.get("/health").json()["status"] == "ok"
