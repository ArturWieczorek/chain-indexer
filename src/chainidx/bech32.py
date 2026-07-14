"""Bech32 encoding, so ids read the human way (``pool1...``, ``addr_test1...``).

Cardano shows ids in bech32, the same encoding Bitcoin uses for addresses: a
human-readable prefix (``pool``, ``addr``, ``stake``), a separator ``1``, then the
data and a 6-character checksum in a restricted alphabet. We have been storing raw
hex; this module converts it for display and back for lookups.

The algorithm is BIP-0173 (Cardano uses plain bech32, checksum constant 1). It is
pure and deterministic, so we test it against exact values produced by the
``cardano-cli`` / ``bech32`` tools - no guessing.

Note: Cardano ignores bech32's original 90-character length cap (a full base
address is longer), so we do not enforce it.
"""

from __future__ import annotations

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_GENERATOR = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]


def _polymod(values: list[int]) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            chk ^= _GENERATOR[i] if (top >> i) & 1 else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _create_checksum(hrp: str, data: list[int]) -> list[int]:
    polymod = _polymod(_hrp_expand(hrp) + data + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    result: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            result.append((acc >> bits) & maxv)
    if pad and bits:
        result.append((acc << (tobits - bits)) & maxv)
    return result


def encode(hrp: str, data: bytes) -> str:
    """Encode bytes as a bech32 string with the given human-readable prefix."""
    five_bit = _convertbits(list(data), 8, 5, pad=True)
    combined = five_bit + _create_checksum(hrp, five_bit)
    return hrp + "1" + "".join(_CHARSET[c] for c in combined)


def decode(text: str) -> tuple[str, bytes]:
    """Decode a bech32 string back to its prefix and bytes; raise if invalid."""
    text = text.lower()
    sep = text.rfind("1")
    if sep < 1:
        raise ValueError("not a bech32 string")
    hrp = text[:sep]
    try:
        data = [_CHARSET.index(c) for c in text[sep + 1 :]]
    except ValueError as exc:
        raise ValueError("invalid bech32 character") from exc
    if _polymod(_hrp_expand(hrp) + data) != 1:
        raise ValueError("bad bech32 checksum")
    return hrp, bytes(_convertbits(data[:-6], 5, 8, pad=False))


def pool_to_bech32(pool_id_hex: str) -> str:
    """A 28-byte pool id hash as ``pool1...``."""
    return encode("pool", bytes.fromhex(pool_id_hex))


def address_to_bech32(address_hex: str) -> str:
    """A raw address as ``addr...`` / ``addr_test...`` / ``stake...``.

    The prefix is chosen from the header byte: the high nibble is the address type
    (0-7 are payment addresses, 14-15 are stake addresses) and the low nibble is
    the network (0 = testnet, 1 = mainnet).
    """
    raw = bytes.fromhex(address_hex)
    header = raw[0]
    address_type = header >> 4
    is_testnet = (header & 0x0F) == 0
    kind = "stake" if address_type in (14, 15) else "addr"
    hrp = f"{kind}_test" if is_testnet else kind
    return encode(hrp, raw)
