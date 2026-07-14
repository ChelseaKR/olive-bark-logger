"""Operator log lines: text passthrough and JSON-per-line (GAP-OBS-1)."""

from __future__ import annotations

import json

from monitor.log import emit


def test_text_mode_prints_the_message_verbatim(capsys):
    emit("text", "event_detected", "event @ 5  dur 1.0s  peak -20.0 dBFS", start=5.0)
    assert capsys.readouterr().out == "event @ 5  dur 1.0s  peak -20.0 dBFS\n"


def test_json_mode_emits_one_object_per_line_with_its_fields(capsys):
    emit("json", "event_detected", "event @ 5", start=5.0, peak_level=-20.0)
    record = json.loads(capsys.readouterr().out)
    assert record == {
        "event": "event_detected",
        "message": "event @ 5",
        "peak_level": -20.0,
        "start": 5.0,
    }


def test_json_mode_keeps_an_embedded_newline_on_a_single_line(capsys):
    emit("json", "stopped", "\nStopped.")
    out = capsys.readouterr().out
    # Only the print's own trailing newline is a real line break; the message's
    # \n is JSON-escaped, so the record stays one line for a line-based shipper.
    assert out.count("\n") == 1
    assert json.loads(out)["message"] == "\nStopped."
