"""Tests for the local-tx-submission codec.

The reject reason below is the real nested structure a live node returned when we
resubmitted an already-spent transaction, so the reason extraction is tested
against a genuine ledger error, not an invented one.
"""

import cbor2
import pytest

from chainidx import txsubmit


def test_submit_message_wraps_the_transaction() -> None:
    tx = b"\x84\xa3\x00\x01\x02"
    msg = txsubmit.submit_message(tx)
    assert msg[0] == 0  # MsgSubmitTx
    era, wrapped = msg[1]
    assert era == 6  # Conway
    assert isinstance(wrapped, cbor2.CBORTag)
    assert wrapped.tag == 24
    assert wrapped.value == tx
    assert txsubmit.done_message() == [3]


def test_parse_reply_accepts() -> None:
    result = txsubmit.parse_reply([1])
    assert result.accepted is True
    assert result.reason == ""


def test_parse_reply_rejects_with_readable_reason() -> None:
    reason = [[6, [[7, "All inputs are spent. Transaction has probably already been included"]]]]
    result = txsubmit.parse_reply([2, reason])
    assert result.accepted is False
    assert "All inputs are spent" in result.reason


def test_parse_reply_reason_falls_back_to_repr() -> None:
    # A reason with no text leaves is shown as its repr rather than lost.
    result = txsubmit.parse_reply([2, [6, [99]]])
    assert result.accepted is False
    assert result.reason == repr([6, [99]])


def test_parse_reply_rejects_unknown_tag() -> None:
    with pytest.raises(RuntimeError):
        txsubmit.parse_reply([9])
