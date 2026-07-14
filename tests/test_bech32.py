"""Tests for bech32 encoding, against values from cardano-cli / the bech32 tool."""

import pytest

from chainidx.bech32 import address_to_bech32, decode, encode, pool_to_bech32

POOL_HEX = "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"
POOL_B32 = "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9"
ADDR_HEX = (
    "00fe75e65309653a8a1e04833eff66807d265ee7b203db4426ffd505b9"
    "e9546949f50285fd15493fe5ba3ffc8bac4aef1c34f5a294d66be825"
)
ADDR_B32 = "addr_test1qrl8tejnp9jn4zs7qjpnalmxsp7jvhh8kgpak3pxll2stw0f2355nagzsh732jflukarllyt439w78p57k3ff4ntaqjspn3a7h"


def test_pool_encode_matches_cardano_cli() -> None:
    assert pool_to_bech32(POOL_HEX) == POOL_B32


def test_address_encode_matches_cardano_cli() -> None:
    assert address_to_bech32(ADDR_HEX) == ADDR_B32


def test_round_trip_decode() -> None:
    hrp, data = decode(POOL_B32)
    assert hrp == "pool"
    assert data.hex() == POOL_HEX
    hrp, data = decode(ADDR_B32)
    assert hrp == "addr_test"
    assert data.hex() == ADDR_HEX


def test_address_prefixes_by_header() -> None:
    # high nibble = type (0-7 payment, 14-15 stake), low nibble = network (0 test).
    assert address_to_bech32("00" + "00" * 56).startswith("addr_test1")
    assert address_to_bech32("01" + "00" * 56).startswith("addr1")
    assert address_to_bech32("e0" + "00" * 28).startswith("stake_test1")
    assert address_to_bech32("e1" + "00" * 28).startswith("stake1")


def test_encode_round_trips_arbitrary_bytes() -> None:
    hrp, data = decode(encode("test", b"\x00\x01\x02\xff"))
    assert hrp == "test"
    assert data == b"\x00\x01\x02\xff"


def test_decode_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="not a bech32"):
        decode("noseparator")
    with pytest.raises(ValueError, match="invalid bech32 character"):
        decode("pool1boi")  # 'b' and 'i' are not in the charset
    with pytest.raises(ValueError, match="checksum"):
        decode("pool1qqqqqqqq")  # valid charset, wrong checksum
