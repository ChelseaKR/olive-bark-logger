# Agent operating contract

Read [`README.md`](./README.md), [`docs/ROADMAP.md`](./docs/ROADMAP.md), and
[`docs/GAP-LEDGER.md`](./docs/GAP-LEDGER.md) before changing this repository.

## Non-negotiable guardrails

- Never write audio bytes to disk or transmit audio. Process raw frames in
  memory and retain only derived levels and event metadata.
- Keep the product local-only: no cloud dependency, telemetry, or hidden
  network path.
- State methodology and limits in every report. Uncalibrated dBFS is relative,
  not absolute SPL, and this device cannot prove the source of a sound.
- Never fabricate, omit, or selectively present data to manufacture a case.
- Preserve the accepted, time-boxed Python 3.9 device-floor decision in
  [`docs/adr/0002-python-39-floor.md`](./docs/adr/0002-python-39-floor.md).
  Do not call it conformant, and do not extend its review date without new
  compatibility and security evidence.

## Verification

```console
make dev
make verify
make a11y
make report
make pwa-test
```

The no-audio, local-only, report-honesty, and Python-floor-review gates are
part of the definition of done.
