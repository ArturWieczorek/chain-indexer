"""Tests for the network parameters and slot -> epoch -> time math."""

from pathlib import Path

from chainidx.network import NetworkParams

GENESIS = str(Path(__file__).parent / "fixtures" / "shelley_genesis.json")


def params() -> NetworkParams:
    return NetworkParams(system_start="2026-07-13T20:36:52Z", slot_length=0.2, epoch_length=1000)


def test_from_genesis_reads_the_params() -> None:
    p = NetworkParams.from_genesis(GENESIS)
    assert p.system_start == "2026-07-13T20:36:52Z"
    assert p.slot_length == 0.2
    assert p.epoch_length == 1000


def test_epoch_of() -> None:
    p = params()
    assert p.epoch_of(0) == 0
    assert p.epoch_of(999) == 0
    assert p.epoch_of(1000) == 1
    assert p.epoch_of(75125) == 75


def test_slot_time() -> None:
    p = params()
    assert p.slot_time(0) == "2026-07-13T20:36:52+00:00"
    # slot 5 at 0.2s per slot is 1 second after the start.
    assert p.slot_time(5) == "2026-07-13T20:36:53+00:00"


def test_epoch_start_time() -> None:
    p = params()
    # Epoch 1 begins at slot 1000 -> 200 seconds after the start.
    assert p.epoch_start_time(1) == "2026-07-13T20:40:12+00:00"


def test_progress() -> None:
    p = params()
    prog = p.progress(75125)
    assert prog.epoch == 75
    assert prog.slot_in_epoch == 125
    assert prog.fraction == 0.125
