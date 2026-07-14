"""Watch patterns - kupo-style matching of outputs (chapter 64).

`kupo <https://github.com/CardanoSolutions/kupo>`_ indexes only the outputs that
match configured **patterns** and lets you look them up. We already index every
output, so we do not need kupo's storage engine; we only need to turn a pattern
string into a query over the index we have.

A pattern is one of:

- ``*`` - everything;
- an **address**, either bech32 (``addr...`` / ``addr_test...``) or raw hex - the
  full payment address of the output;
- a **stake address** (``stake...`` / ``stake_test...``) - matches every output
  whose base address delegates to that stake credential;
- a **policy id** (56 hex characters) - outputs holding any asset of that policy;
- ``<policyid>.<assetname>`` - outputs holding that one asset.

This module is pure (it only parses; the query lives in the store), so it is unit
tested directly. bech32 decoding is reused from :mod:`chainidx.bech32`.
"""

from __future__ import annotations

from dataclasses import dataclass

from chainidx import bech32

_HEX = set("0123456789abcdef")


def _is_hex(text: str) -> bool:
    return bool(text) and all(c in _HEX for c in text.lower())


@dataclass(frozen=True)
class Pattern:
    """A parsed watch pattern.

    ``kind`` is one of ``all``, ``address``, ``stake``, ``policy``, ``asset``.
    ``value`` holds the address/credential/policy hex; ``asset_name`` the asset
    name hex (only for ``asset``).
    """

    kind: str
    value: str = ""
    asset_name: str = ""


def parse_pattern(text: str) -> Pattern:
    """Classify a pattern string into a :class:`Pattern`.

    Address and stake bech32 strings are decoded to the raw hex the store holds
    (``tx_out.address`` and ``tx_out.stake_cred``); everything else is matched by
    length and shape. A stake address is a 1-byte header plus the 28-byte
    credential, so we drop the header.
    """
    if text == "*":
        return Pattern("all")
    if text.startswith("stake"):
        try:
            return Pattern("stake", bech32.decode(text)[1][1:].hex())
        except ValueError:
            return Pattern("stake", text)
    if text.startswith("addr"):
        try:
            return Pattern("address", bech32.decode(text)[1].hex())
        except ValueError:
            return Pattern("address", text)
    if "." in text:
        policy, _, name = text.partition(".")
        return Pattern("asset", policy.lower(), name.lower())
    if len(text) == 56 and _is_hex(text):
        return Pattern("policy", text.lower())
    return Pattern("address", text.lower() if _is_hex(text) else text)
