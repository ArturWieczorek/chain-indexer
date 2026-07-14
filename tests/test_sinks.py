"""Tests for the event sinks (chapter 76): log, file, and dispatch."""

import json
from pathlib import Path

import pytest

from chainidx.patterns import EventFilter
from chainidx.sinks import FileSink, LogSink, build_sink, build_sinks
from chainidx.webhook import WebhookSink


def test_log_sink_prints_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    LogSink(EventFilter()).emit({"type": "block", "block_no": 7})
    assert json.loads(capsys.readouterr().out.strip()) == {"type": "block", "block_no": 7}


def test_file_sink_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = FileSink(EventFilter(), str(path))
    sink.emit({"type": "block", "block_no": 1})
    sink.emit({"type": "rollback", "count": 2})
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert lines == [{"type": "block", "block_no": 1}, {"type": "rollback", "count": 2}]


def test_build_sink_dispatches_on_type() -> None:
    log = build_sink({"type": "log", "types": ["block"]})
    assert isinstance(log, LogSink)
    assert log.event_filter.types == frozenset({"block"})

    file_sink = build_sink({"type": "file", "target": "events.jsonl"})
    assert isinstance(file_sink, FileSink)
    assert file_sink.path == "events.jsonl"

    hook = build_sink({"type": "webhook", "target": "https://h", "addresses": ["addrA"]})
    assert isinstance(hook, WebhookSink)
    assert hook.url == "https://h"
    assert hook.event_filter.addresses == frozenset({"addrA"})

    # The default type is webhook, and the `url` shorthand still works.
    default_hook = build_sink({"url": "https://h2"})
    assert isinstance(default_hook, WebhookSink)
    assert default_hook.url == "https://h2"

    with pytest.raises(ValueError, match="unknown sink type"):
        build_sink({"type": "carrier-pigeon"})


def test_build_sinks_builds_each_entry() -> None:
    sinks = build_sinks(({"type": "log"}, {"type": "file", "target": "a.jsonl"}))
    assert isinstance(sinks[0], LogSink)
    assert isinstance(sinks[1], FileSink)
