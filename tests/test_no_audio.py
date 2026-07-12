"""Merge-blocking: prove no code path persists or transmits audio.

This is the central design gate from the README. It works three ways:

  1. The data model carries no audio field (introspection of Event + DB schema).
  2. No source file uses an audio file/serialization API (static scan).
  3. The live capture module's only sink for a frame is the in-memory queue/yield.

If someone adds a way to write audio, one of these fails before merge.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import fields
from pathlib import Path

from monitor.detector import Event
from store import EventStore

from conftest import source_files
from gates import scan_audio_write_apis, scan_binary_write

ALLOWED_EVENT_FIELDS = {
    "start",
    "end",
    "duration",
    "peak_level",
    "avg_level",
    "coarse_tag",
    # Envelope anatomy: bounded shape descriptors (seconds), never audio. Added
    # deliberately here so the no-audio gate keeps pace with the data model.
    "rise_time_s",
    "loud6_s",
    "longest_run_s",
}

# The optional report exporter is the sole reviewed binary artifact sink. It writes
# already-rendered PDF bytes supplied by WeasyPrint; no capture frame or audio value
# reaches this module. Keep this allowlist exact so any second sink still blocks merge.
ALLOWED_BINARY_WRITES = {"report/pdf_export.py": ["write_bytes"]}


def test_event_has_no_audio_field():
    names = {f.name for f in fields(Event)}
    assert names == ALLOWED_EVENT_FIELDS, f"unexpected Event fields: {names}"


def test_db_schema_has_no_audio_column():
    """No table has a BLOB column or a column whose name implies raw audio content."""
    with tempfile.TemporaryDirectory() as d:
        store = EventStore(Path(d) / "t.db")
        store.close()
        conn = sqlite3.connect(Path(d) / "t.db")
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        cols: dict[str, str] = {}  # column name -> declared type
        for table in tables:
            for row in conn.execute(f"PRAGMA table_info({table})"):
                cols[row[1].lower()] = (row[2] or "").upper()
        conn.close()
    # A BLOB column is the only way to stash binary audio; assert there are none.
    blobs = {c for c, t in cols.items() if "BLOB" in t}
    assert not blobs, f"BLOB columns could hold audio: {blobs}"
    # Names that would imply raw audio content (counters like frames_seen are fine).
    audio_words = ("audio", "wav", "pcm", "waveform", "samples", "recording")
    offenders = {c for c in cols if any(w in c for w in audio_words)}
    assert not offenders, f"schema columns look audio-bearing: {offenders}"


def test_no_source_file_uses_audio_write_api():
    offenders: dict[str, list[str]] = {}
    for path in source_files():
        hits = scan_audio_write_apis(path.read_text(encoding="utf-8"))
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"forbidden audio APIs present: {offenders}"


def test_no_file_open_in_write_binary_mode():
    """No source dumps bytes except the exact reviewed PDF artifact sink.

    Covers the obvious `open('x','wb')` plus the bypasses: `io.open('x','wb')`,
    `Path(...).write_bytes(...)`, and a low-level
    `os.open(..., O_WRONLY/O_RDWR/O_CREAT)` writable descriptor.
    """
    offenders: dict[str, list[str]] = {}
    root = Path(__file__).resolve().parent.parent
    for path in source_files():
        hits = scan_binary_write(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()
        unexpected = [hit for hit in hits if hit not in ALLOWED_BINARY_WRITES.get(relative, [])]
        if unexpected:
            offenders[relative] = unexpected
    assert not offenders, f"binary-write sinks found in: {offenders}"

    observed_allowlisted = {
        path.relative_to(root).as_posix(): scan_binary_write(path.read_text(encoding="utf-8"))
        for path in source_files()
        if path.relative_to(root).as_posix() in ALLOWED_BINARY_WRITES
    }
    assert observed_allowlisted == ALLOWED_BINARY_WRITES


def test_capture_live_only_sinks_frames_to_memory():
    """The live capture frame buffer is only enqueued/yielded — never written out."""
    src = (Path(__file__).resolve().parent.parent / "monitor" / "capture_live.py").read_text()
    # The mono frame must be handed to the in-memory queue and nowhere else.
    assert "frames.put_nowait(mono)" in src
    for bad in ("open(", "socket", "requests", "urllib", "wave"):
        assert bad not in src, f"capture_live unexpectedly references {bad!r}"
