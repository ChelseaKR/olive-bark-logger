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
broken.* The quiet-hours CSV names its recorded monitoring gaps, since a gap removes
events and would otherwise make an unmonitored stretch read as a quiet one. This edition
has no calibration step, so its report says plainly that its readings are relative dBFS
and never dB(A).

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
**Download quiet-hours CSV** (every event flagged within/outside quiet hours — an honest
export for a neighbor/landlord/HOA submission). **Clear events** resets. Install it as an
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
