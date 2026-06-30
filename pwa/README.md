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

## Run it

It must be served over `http(s)://` (microphone access and service workers don't work on
`file://`). Any static server works:

```bash
cd pwa
python3 -m http.server 8000
# open http://localhost:8000
```

Click **Start monitoring**, grant microphone permission, and adjust the threshold while
watching the live level. Use **Download report** / **Download CSV** to export, and
**Clear events** to reset. Install it as an app from your browser's "Install" option.

## Test

```bash
node --test pwa/*.test.mjs
```

Covers the detector port and the aggregation/report/CSV logic (including that the report
always contains the methodology + limitations + no-audio statements).
