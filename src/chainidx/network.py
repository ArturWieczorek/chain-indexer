"""Network parameters and the slot -> epoch -> wall-clock math.

The chain measures time in **slots**, not dates, and it groups slots into
**epochs**. To show human times and epoch numbers like a real explorer we need
three numbers from the network's Shelley genesis:

- ``system_start`` - the wall-clock time of slot 0;
- ``slot_length`` - how many seconds a slot lasts;
- ``epoch_length`` - how many slots make an epoch.

From those, a slot's time is ``system_start + slot * slot_length``, and its epoch
is ``slot // epoch_length``. That is all this module does, and it is pure, so it
is easy to test exactly.

> **Simplification.** This assumes one uniform slot length for the whole chain,
> which is true for a Shelley-and-later (Conway) network like our cluster. A chain
> that includes the Byron era (which used a different slot length) would need
> per-era arithmetic; chapter 18's "known limitations" spirit applies here too.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class EpochProgress:
    """Where a slot sits within its epoch."""

    epoch: int
    slot_in_epoch: int
    epoch_length: int

    @property
    def fraction(self) -> float:
        """How far through the epoch, in [0, 1)."""
        return self.slot_in_epoch / self.epoch_length


@dataclass(frozen=True)
class NetworkParams:
    """The genesis numbers needed to turn slots into epochs and times."""

    system_start: str  # ISO-8601, the time of slot 0
    slot_length: float  # seconds per slot
    epoch_length: int  # slots per epoch
    active_slot_coeff: float = 0.05  # fraction of slots that make a block (f)

    @classmethod
    def from_genesis(cls, shelley_genesis_path: str) -> NetworkParams:
        """Load the parameters from a Shelley genesis JSON file."""
        data = json.loads(Path(shelley_genesis_path).read_text())
        return cls(
            system_start=data["systemStart"],
            slot_length=float(data["slotLength"]),
            epoch_length=int(data["epochLength"]),
            active_slot_coeff=float(data.get("activeSlotsCoeff", 0.05)),
        )

    def expected_blocks(self, stake_fraction: float) -> float:
        """A pool's expected blocks in an epoch for a given active-stake share.

        Roughly ``f * epoch_length * stake_fraction``: of the slots in an epoch, a
        fraction ``f`` produce a block, and a pool wins them in proportion to its
        active stake.
        """
        return self.active_slot_coeff * self.epoch_length * stake_fraction

    def _start(self) -> datetime:
        return datetime.fromisoformat(self.system_start)

    def epoch_of(self, slot: int) -> int:
        """The epoch a slot belongs to."""
        return slot // self.epoch_length

    def slot_time(self, slot: int) -> str:
        """The wall-clock time of a slot, as ISO-8601."""
        return (self._start() + timedelta(seconds=slot * self.slot_length)).isoformat()

    def epoch_start_time(self, epoch: int) -> str:
        """The wall-clock time an epoch began."""
        return self.slot_time(epoch * self.epoch_length)

    def progress(self, tip_slot: int) -> EpochProgress:
        """Which epoch the tip is in and how far through it is."""
        return EpochProgress(
            epoch=self.epoch_of(tip_slot),
            slot_in_epoch=tip_slot % self.epoch_length,
            epoch_length=self.epoch_length,
        )
