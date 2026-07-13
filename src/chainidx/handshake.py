"""The node-to-client handshake mini-protocol (version negotiation).

Before any real work, a client and the node must agree on a protocol version.
The client proposes a table of versions it supports; the node replies by either
accepting one or refusing. This is the first mini-protocol to run over a fresh
connection, and it is small: one message each way.

The wire messages (CBOR):

- propose:  ``[0, {version: versionData}]``  (MsgProposeVersions)
- accept:   ``[1, version, versionData]``     (MsgAcceptVersion)
- refuse:   ``[2, reason]``                    (MsgRefuse)

Two node-to-client quirks, both confirmed against a live node:

- version numbers carry a flag: the number on the wire is ``0x8000 | version``;
- the version data is ``[networkMagic, queryFlag]`` (we send ``query = False``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import cbor2

from chainidx.mux import PROTOCOL_HANDSHAKE, MuxConnection

_VERSION_FLAG = 0x8000
# The node-to-client versions we are willing to speak. The node picks the
# highest it also supports.
_DEFAULT_VERSIONS = range(9, 21)


class HandshakeError(Exception):
    """Raised when the node refuses every version we proposed."""


def propose_message(network_magic: int, versions: Iterable[int] = _DEFAULT_VERSIONS) -> list[Any]:
    """Build a MsgProposeVersions offering ``versions`` for ``network_magic``."""
    table = {(_VERSION_FLAG | v): [network_magic, False] for v in versions}
    return [0, table]


def parse_reply(reply: list[Any]) -> int:
    """Return the accepted version number, or raise on refusal."""
    tag = reply[0]
    if tag == 1:  # MsgAcceptVersion [1, version, versionData]
        return int(reply[1]) & ~_VERSION_FLAG
    raise HandshakeError(f"node refused the handshake: {reply!r}")


async def negotiate(mux: MuxConnection, network_magic: int) -> int:
    """Run the handshake and return the agreed version number."""
    await mux.send(PROTOCOL_HANDSHAKE, cbor2.dumps(propose_message(network_magic)))
    reply = await mux.receive(PROTOCOL_HANDSHAKE)
    return parse_reply(reply)
