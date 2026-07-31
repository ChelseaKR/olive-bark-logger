# CLAUDE.md — Olive's Bark Logger

Agent contract for this repo. Per DOCUMENTATION-STANDARD §7/§9, agent-facing
instructions live here, not in the README (moved from the README's former
"For Claude Code" section, 2026-07-19).

- **Build entrypoint:** [`docs/ROADMAP.md`](./docs/ROADMAP.md) → *Implementation Plan*.
- **Hard guardrails:** **never write audio bytes to disk and never transmit audio anywhere** — raw frames are processed in memory and discarded; only derived levels + event metadata are persisted (this is the central design gate and has a merge-blocking test); the report must state its **methodology and limitations honestly** (uncalibrated dBFS is relative, not absolute SPL unless calibrated; the device cannot prove a sound's source); the tool runs **local-only** (no cloud, no telemetry); data is presented to inform, never fabricated or cherry-picked to manufacture a case.
- **Commands:** `make dev` · `make verify` · `make a11y` · `make report` · `make pwa-test`.
- **Definition of done:** the monitor runs unattended, logs noise events (levels + timestamps, zero audio) to local SQLite, and produces an honest, accessible report — all applicable `/STANDARDS` gates green (see the README's Standards Conformance table) and the no-audio test passing. Full checklist: [`DEFINITION_OF_DONE.md`](./DEFINITION_OF_DONE.md).
