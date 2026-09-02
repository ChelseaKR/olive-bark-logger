# Olive's Bark Logger — PWA (zero-hardware variant)

A browser version of the monitor for when you don't have a Raspberry Pi. It uses the Web
Audio API to measure sound **levels** and logs events to IndexedDB. **Audio is processed
in memory and never recorded, stored, or uploaded** — the same guarantee as the Python
service. It works fully offline after first load.

This is a parallel implementation of the same idea; it shares the detection semantics and
the honest methodology/limitations framing with the Python core:

| Concern | Python (`monitor/`, `report/`) | PWA (`pwa/`) |
|---------|--------------------------------|--------------|
| Level math | `level.py` | `level.js` |
| Detector (threshold/min-dur/debounce) | `detector.py` | `detector.js` |
| Aggregation + report + CSV | `aggregate.py`, `render.py`, `export.py` | `report.js` |
| Storage (events only, no audio) | SQLite | IndexedDB |
| Cover block + no-verdict line | `render.py` (`cover_html`, `cover_text_lines`) | `report.js` (`coverHtml`, `coverTextLines`, `csvPreamble`) |

**The caveats travel with every file this page produces.** The report HTML and both CSV
downloads carry the same "what this can and cannot prove" cover block as the Python
exports — in the CSVs as a leading `#` comment preamble, so the caveat travels with a file
that gets emailed on while the data rows below it still parse. Anything reporting a
quiet-hours count also carries the no-verdict line: *being within quiet hours is not the
same as a violation, and only the relevant authority can decide whether a rule was
broken.* This edition has no calibration step, so its report says plainly that its
readings are relative dBFS and never dB(A).

**Every export states how much of the window it observed.** Monitored versus wall-clock
hours lead the quiet-hours CSV, the event CSV, and the report, because a count is only
readable against the time it was counted over: an outage during quiet hours removes
events, so a device that dropped out for most of the night produces a low count that
reads as a quiet night. Recorded monitoring gaps are still named individually, but as a
numerator with a denominator above it rather than the bare *"37s of gap"* a reader cannot
place against a half-hour test or a ten-hour night. Hours outside a monitoring run are
reported as **not monitored, not quiet**.

That figure needs a record of when observation began and ended, which this edition did
not keep until now: a gap is written by the *running* app on a `visibilitychange`, so the
most ordinary outage of all — the tab closed, the browser restarted, the laptop shut —
left no trace at all. Each run now writes a session record, checkpointed as it goes. The
error that leaves is one-directional and stated on every export: a tab killed outright
ends its run at the last checkpoint, so up to 30 seconds of real observation goes
unclaimed. Under-claiming is the safe direction. Where the record carries no sessions at
all — data captured before this existed — the export says the figure assumes the app was
listening whenever no gap was recorded, rather than presenting an assumption as a
measurement.

The exact strings live in [`spec/report/cover.json`](../spec/report/cover.json) and are
replayed against **both** implementations, the way `spec/detector/*.json` keeps the two
detectors from drifting — see [`spec/SEMANTICS.md`](../spec/SEMANTICS.md).

## Run it

It must be served over `http(s)://` (microphone access and service workers don't work on
`file://`). Any static server works:

```bash
cd pwa
python3 -m http.server 8000
# open http://localhost:8000
```

Click **Start monitoring**, grant microphone permission, and adjust the threshold and the
quiet-hours window while watching the live level. Use **Download report** (HTML, with a
day×hour calendar heatmap and a quiet-hours summary), **Download CSV** (the event log), or
**Download quiet-hours CSV** (every event flagged within/outside quiet hours, led by how
much of the window was monitored — an honest export for a neighbor/landlord/HOA
submission). **Clear events** resets. Install it as an
app from your browser's "Install" option.

## Test

```bash
node --test pwa/*.test.mjs
```

Covers the detector port and the aggregation/report/CSV logic, including the export
caveat gate: every export path this module has must carry every string in
`spec/report/cover.json`, and `tests/test_export_caveats.py` discovers the module's export
paths from source so a new one fails the gate until it is exercised here too. The report
must still contain the methodology + limitations + no-audio statements.
