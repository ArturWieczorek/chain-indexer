"""Tests for watch-pattern parsing (chapter 64)."""

from chainidx import bech32
from chainidx.patterns import Pattern, parse_pattern


def test_star_matches_everything() -> None:
    assert parse_pattern("*") == Pattern("all")


def test_a_bech32_address_decodes_to_its_raw_hex() -> None:
    raw = "00" + "11" * 28 + "22" * 28  # a 57-byte base address
    text = bech32.encode("addr_test", bytes.fromhex(raw))
    assert parse_pattern(text) == Pattern("address", raw)


def test_a_bech32_stake_address_becomes_its_credential() -> None:
    # A stake address is a 1-byte header plus the 28-byte credential.
    text = bech32.encode("stake_test", bytes.fromhex("e0" + "33" * 28))
    assert parse_pattern(text) == Pattern("stake", "33" * 28)


def test_an_undecodable_address_pattern_is_kept_verbatim() -> None:
    assert parse_pattern("addrbad") == Pattern("address", "addrbad")
    assert parse_pattern("stakebad") == Pattern("stake", "stakebad")


def test_a_policy_id_is_56_hex_characters() -> None:
    policy = "ab" * 28
    assert parse_pattern(policy.upper()) == Pattern("policy", policy)


def test_a_dotted_pattern_is_a_single_asset() -> None:
    assert parse_pattern("ABcd.4869") == Pattern("asset", "abcd", "4869")


def test_a_raw_hex_address_is_lowercased() -> None:
    raw = "00" + "AB" * 56
    assert parse_pattern(raw) == Pattern("address", raw.lower())


def test_a_non_hex_string_is_an_address_verbatim() -> None:
    assert parse_pattern("addrA") == Pattern("address", "addrA")
