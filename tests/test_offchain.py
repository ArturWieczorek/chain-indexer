"""Tests for off-chain pool metadata parsing (the pure part)."""

from chainidx.offchain import parse_pool_metadata


def test_parse_pool_metadata_keeps_known_fields() -> None:
    raw = b'{"name":"My Pool","ticker":"MINE","homepage":"https://x","description":"d","extra":9}'
    assert parse_pool_metadata(raw) == {
        "name": "My Pool",
        "ticker": "MINE",
        "homepage": "https://x",
        "description": "d",
    }


def test_parse_pool_metadata_rejects_unusable_input() -> None:
    assert parse_pool_metadata(b'{"other": 1}') is None  # no known fields
    assert parse_pool_metadata(b"not json") is None
    assert parse_pool_metadata(b"[1, 2]") is None  # not an object
