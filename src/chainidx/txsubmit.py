"""The local-tx-submission mini-protocol codec (submitting transactions).

This is the node-to-client mini-protocol (id 6) a client uses to hand a signed
transaction to the node. With it, we submit transactions over our own protocol
instead of shelling out to the cli. The wire shapes were confirmed against a live
node before this code was written:

- ``MsgSubmitTx = [0, [era, CBORTag(24, txBytes)]]``  (client submits)
- ``MsgAcceptTx = [1]``                                (node accepted)
- ``MsgRejectTx = [2, reason]``                        (node rejected)
- ``MsgDone     = [3]``

The rejection reason is a nested ledger-error structure; we pull the human-readable
text out of it for display.

This module is pure and fully unit-tested; the socket-bound client that uses it,
``TxSubmitClient``, is excluded from the coverage gate like the other integration
clients.
"""

from __future__ import annotations

from typing import Any

import cbor2

from chainidx.model import SubmitResult

_CONWAY_ERA = 6


def submit_message(tx_bytes: bytes, era: int = _CONWAY_ERA) -> list[Any]:
    """MsgSubmitTx carrying a raw signed transaction (era-wrapped, tag 24)."""
    return [0, [era, cbor2.CBORTag(24, tx_bytes)]]


def done_message() -> list[Any]:
    """MsgDone: end the mini-protocol."""
    return [3]


def _reason_text(reason: Any) -> str:
    """Collect the human-readable strings out of a nested rejection reason."""
    texts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            texts.append(node)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(reason)
    return "; ".join(texts) if texts else repr(reason)


def parse_reply(reply: list[Any]) -> SubmitResult:
    """Turn a MsgAcceptTx / MsgRejectTx into a `SubmitResult`."""
    if reply[0] == 1:
        return SubmitResult(accepted=True, reason="")
    if reply[0] == 2:
        return SubmitResult(accepted=False, reason=_reason_text(reply[1]))
    raise RuntimeError(f"unexpected tx-submission reply: {reply!r}")
