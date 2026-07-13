"""The event bus: how the indexer tells the outside world what just happened.

This is the fourth design seam. As the follower applies blocks, it publishes small
typed events - a block arrived, a pool registered, a vote was cast, the chain
rolled back - and any number of consumers subscribe. In this project the live
dashboard (chapter 16) is the consumer, streaming events to browsers over a
WebSocket; a webhook notifier would be another.

The bus is deliberately tiny: each subscriber gets an ``asyncio.Queue``, and
``publish`` drops the event into every queue. Publishing is synchronous and
non-blocking (``put_nowait``), so the follower can call it from its normal
apply path without awaiting.

``describe_block`` turns a block into the list of events it implies. It is a pure
function, so it is easy to test that a governance-heavy block produces the right
stream of events.
"""

from __future__ import annotations

import asyncio
from typing import Any

from chainidx.model import (
    Block,
    DRepRegistration,
    PoolRegistration,
    StakeDelegation,
)

Event = dict[str, Any]


class EventBus:
    """A minimal publish/subscribe bus over asyncio queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: Event) -> None:
        for queue in self._subscribers:
            queue.put_nowait(event)


def describe_block(block: Block) -> list[Event]:
    """The stream of events a block implies: the block itself, then its contents."""
    events: list[Event] = [
        {
            "type": "block",
            "block_no": block.block_no,
            "hash": block.block_hash,
            "slot": block.slot_no,
            "tx_count": len(block.txs),
        }
    ]
    for tx in block.txs:
        for cert in tx.certificates:
            if isinstance(cert, PoolRegistration):
                events.append(
                    {"type": "pool_registered", "pool_id": cert.pool_id, "block_no": block.block_no}
                )
            elif isinstance(cert, StakeDelegation):
                events.append(
                    {
                        "type": "stake_delegated",
                        "stake_address": cert.stake_address,
                        "pool_id": cert.pool_id,
                    }
                )
            elif isinstance(cert, DRepRegistration):
                events.append({"type": "drep_registered", "drep_id": cert.drep_id})
        for proposal in tx.proposals:
            events.append(
                {
                    "type": "gov_action_proposed",
                    "gov_action_id": proposal.gov_action_id,
                    "action_type": proposal.action_type,
                }
            )
        for vote in tx.votes:
            events.append(
                {
                    "type": "vote_cast",
                    "gov_action_id": vote.gov_action_id,
                    "vote": vote.vote,
                    "voter_role": vote.voter_role,
                }
            )
    return events
