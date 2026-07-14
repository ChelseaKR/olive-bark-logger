"""Operator log lines in either human text or newline-delimited JSON.

GAP-OBS-1 / control OBS-22: the monitor's operator output can be emitted as one
JSON object per line for a log shipper, without pulling in a third-party logging
dependency — the runtime core stays standard-library only (ADR-0001). ``text``
is the default and is byte-for-byte what the monitor printed before this flag
existed; ``json`` wraps the same human message plus its structured fields.

This is intentionally not a general logging framework: the monitor emits a small,
fixed set of operator lines (startup, retention, detected event, clock anomaly,
status-page failure, shutdown), and each call site passes both the human message
and the fields a machine consumer wants. Audio is never a field — the monitor
logs sound-*level* events, never audio, and that invariant is unchanged here.
"""

from __future__ import annotations

import json

#: The accepted ``--log-format`` / ``log_format`` values.
LOG_FORMATS = ("text", "json")


def emit(fmt: str, event: str, message: str, **fields: object) -> None:
    """Print one operator log line.

    In ``text`` mode this prints ``message`` exactly (the pre-flag behavior). In
    ``json`` mode it prints a single JSON object ``{"event", "message", ...fields}``
    on one line, flushed so a shipper sees each line promptly. ``event`` is a stable
    machine key (e.g. ``"event_detected"``); ``message`` is the human sentence.
    """
    if fmt == "json":
        record: dict[str, object] = {"event": event, "message": message}
        record.update(fields)
        print(json.dumps(record, sort_keys=True, ensure_ascii=False), flush=True)
    else:
        print(message)
