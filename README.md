# Olive's Bark Logger

**A privacy-first, on-device noise monitor that timestamps barking events and sound-level spikes and turns them into a clean report** — so the next time a downstairs neighbor complains, you have objective data instead of a he-said-she-said. It measures sound *levels* and event metadata only. It never records, stores, or transmits audio. By design, there is no recording to leak, subpoena, or wiretap.

**Status:** `Beta` · **Track:** Personal (on-device monitor + report generator) · **License:** MIT (proposed) · **Data:** on-device/local

## Why it matters
You've been on the receiving end of vague noise complaints about Olive with nothing concrete to point to. A small device that runs in your apartment and logs *when* sound crossed a threshold and for *how long* gives you an honest, time-stamped record — useful for property management or just for understanding the real pattern — without the legal and ethical problems of recording your home (or your neighbors).

## What it does
- **Listens for levels, not content:** computes sound level (dBFS, with a documented calibration offset) frame-by-frame in memory and discards the audio immediately.
- **Detects events:** threshold + minimum-duration + debounce → a "bark/noise event" with start, duration, and peak/average level.
- **Logs to SQLite:** events only — timestamps and levels, no audio.
- **Generates reports:** daily/hourly distributions, quiet-hours summaries, and event counts as a clean PDF/HTML with charts and a methodology + limitations section.
- **Runs on-device:** a Raspberry Pi service (primary) or a browser PWA (zero-hardware alternative), no network required.

## For Claude Code
- **Build entrypoint:** [`docs/ROADMAP.md`](./docs/ROADMAP.md) → *Implementation Plan*.
- **Hard guardrails:** **never write audio bytes to disk and never transmit audio anywhere** — raw frames are processed in memory and discarded; only derived levels + event metadata are persisted (this is the central design gate and has a merge-blocking test); the report must state its **methodology and limitations honestly** (uncalibrated dBFS is relative, not absolute SPL unless calibrated; the device cannot prove a sound's source); the tool runs **local-only** (no cloud, no telemetry); data is presented to inform, never fabricated or cherry-picked to manufacture a case.
- **Commands:** `make dev` · `make verify` · `make a11y` · `make report` · `make pwa-test`.

## Quickstart
```bash
make dev                       # create .venv and install (dev extras)
make verify                    # run every merge-blocking gate locally
make report                    # render report.html from a demo session (no hardware)
# Live capture on a Pi/laptop (optional audio dependency):
.venv/bin/pip install -e ".[live]"
.venv/bin/olive-tune     --config config.sample.json    # live meter; suggests a threshold
.venv/bin/olive-calibrate --config config.sample.json --reference-db 70   # store SPL offset
.venv/bin/olive-monitor  --config config.sample.json    # logs events; Ctrl-C to stop
.venv/bin/olive-report   --config config.sample.json --out report.html --csv events.csv
```
The core (level math, detector, store, report) has **zero runtime dependencies** and runs
on any Python 3.9+ with no installs; only live microphone capture needs the `live` extra.

## CLIs
| Command | What it does |
|---------|--------------|
| `olive-monitor` | Run the monitor: capture → level → detect → SQLite. Creates a capture *session* (lineage), writes a heartbeat file, reconnects on device failure, prunes per `retention_days`. |
| `olive-tune` | Show the live level so you can pick a threshold by ear; prints a suggestion. |
| `olive-calibrate` | Measure mean level against a reference SPL reading and store the offset. |
| `olive-report` | Render the accessible HTML report (distributions + day×hour calendar heatmap + quiet-hours summary). Optional `--csv` event export, and `--violations-csv` / `--violations-html` for an honest quiet-hours report suitable for a neighbor/landlord/HOA submission. |

## Deployment & variants
- **Raspberry Pi service:** `scripts/setup-pi.sh` installs PortAudio + a venv and the
  `deploy/olive-monitor.service` systemd unit (auto-restart, network-isolated, sandboxed).
- **Browser PWA (zero hardware):** [`pwa/`](./pwa/) — Web Audio levels, IndexedDB events,
  same no-audio guarantee, works offline. See [`pwa/README.md`](./pwa/README.md).
- **Container:** `Dockerfile` builds the report/analysis side for reproducible CI.

- **Definition of done:** the monitor runs unattended, logs noise events (levels + timestamps, zero audio) to local SQLite, and produces an honest, accessible report with charts and a stated methodology — all `/STANDARDS` gates green and the no-audio test passing.

## Standards
Inherits [`/STANDARDS`](../STANDARDS/).
