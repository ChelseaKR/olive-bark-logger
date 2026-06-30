# No-Audio Guarantee — design proof

**Last verified: 2026-06-05 · Recheck cadence: per audio-stack change.**

The central guarantee of this project is: **no audio is ever captured to disk or
transmitted.** This document shows *why that is true by construction*, not by promise,
and points at the tests that fail the build if it stops being true.

## The data path, end to end

```
mic / synthetic source            monitor.level.dbfs(frame)        store.add_event(Event)
  -> (t, frame)            ->      -> float (dBFS)          ->      -> SQLite (6 numbers)
       ^ in-memory list                ^ frame dropped here            ^ no audio column exists
```

1. **Capture** (`monitor/capture.py`, `monitor/capture_live.py`) yields a short
   in-memory list of float samples per frame. The live callback copies the device
   buffer into a Python list, enqueues it, and lets the buffer be reused. There is no
   file handle and no socket in this path.
2. **Level computation** (`monitor/level.py`) reduces a frame to a single dBFS number.
   The frame is a local; it is not returned, stored, or referenced again.
3. **Detection** (`monitor/detector.py`) sees only `(timestamp, level)` numbers.
4. **Persistence** (`store/db.py`) writes an `Event` of six numbers plus an optional
   short tag string. **No column in the schema can hold audio.**

There is deliberately **no API anywhere that writes a frame**. Building the no-audio
guarantee first, and designing so the write simply does not exist, is the approach the
roadmap mandates (§8, "Claude Code approach").

## How the build enforces it (merge-blocking)

`tests/test_no_audio.py`:
- `test_event_has_no_audio_field` — the `Event` dataclass has exactly the six metadata
  fields and nothing else.
- `test_db_schema_has_no_audio_column` — introspects the live SQLite schema and rejects
  any column whose name suggests audio/samples/frames/blobs.
- `test_no_source_file_uses_audio_write_api` — static scan: no `wave`, `soundfile`,
  `scipy.io.wavfile`, `aifc`, `sunau`, `audioop`, or `.tobytes(` anywhere in the code.
- `test_no_file_open_in_write_binary_mode` — AST scan: nothing opens a file `"wb"`.
- `test_capture_live_only_sinks_frames_to_memory` — the live frame is only enqueued.

`tests/test_no_egress.py`:
- `test_no_first_party_module_imports_network` — AST scan: no first-party module
  imports a networking library, so nothing can transmit anything (audio included).

If any future change adds a way to persist or send audio, one of these tests fails and
the merge is blocked.
