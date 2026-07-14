"""Tests for the webhook sinks (chapter 69): pure config and payload."""

import json

from chainidx import bech32
from chainidx.webhook import encode_payload, sink_from_dict, sinks_from_config


def test_sink_from_dict_builds_filter_and_normalises_addresses() -> None:
    addr_hex = "00" + "11" * 28 + "22" * 28
    addr_bech = bech32.encode("addr_test", bytes.fromhex(addr_hex))
    policy_hex = "ab" * 28  # a 56-hex value is not an address, so it is kept verbatim
    sink = sink_from_dict(
        {
            "url": "https://hook",
            "addresses": [addr_bech, policy_hex],
            "policies": ["ABcd"],
            "assets": ["PolX.4869"],
            "types": ["rollback"],
        }
    )
    assert sink.url == "https://hook"
    assert sink.event_filter.addresses == frozenset({addr_hex, policy_hex})
    assert sink.event_filter.policies == frozenset({"abcd"})  # lower-cased
    assert sink.event_filter.assets == frozenset({"polx.4869"})
    assert sink.event_filter.types == frozenset({"rollback"})


def test_sinks_from_config_builds_each_entry() -> None:
    sinks = sinks_from_config(({"url": "a"}, {"url": "b", "types": ["transaction"]}))
    assert [s.url for s in sinks] == ["a", "b"]
    assert sinks[0].event_filter == sink_from_dict({"url": "a"}).event_filter  # empty = all
    assert sinks[1].event_filter.matches({"type": "transaction"}) is True
    assert sinks[1].event_filter.matches({"type": "block"}) is False


def test_encode_payload_round_trips_as_json() -> None:
    assert json.loads(encode_payload({"type": "block", "block_no": 7})) == {
        "type": "block",
        "block_no": 7,
    }
