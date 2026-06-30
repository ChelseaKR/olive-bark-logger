# Residual-Risk Register

**Last verified: 2026-06-05 · Recheck cadence: per release.**

STRIDE-style threat model for a local-only device with no network and no audio. The
attack surface is intentionally tiny.

## Threat model summary

Data flows: mic → in-memory level → local SQLite → local HTML report. No network, no
audio at rest, single user, single machine. The classic remote-attacker surface is
absent by design.

| # | Risk | Category | Likelihood | Impact | Mitigation | Residual | Owner |
|---|------|----------|-----------|--------|------------|----------|-------|
| 1 | Tampering with the event log to misrepresent the pattern | Tampering | Low | Med | Append-only writes; report is reproducible from the log (snapshot test); methodology states limits | Accept — single-user local tool; integrity is the user's own | — |
| 2 | Vulnerable dependency | Elevation | Low | Med | Core has **zero** runtime deps; `pip-audit` merge-blocking; only optional `sounddevice` for live capture | Low | — |
| 3 | Secret committed to repo | Info disclosure | Low | Low | `gitleaks` merge-blocking; project needs no secrets | Low | — |
| 4 | Misleading evidence (bare numbers over-trusted) | Misuse | Med | Med | Mandatory Methodology + Limitations; no source-attribution claims; informational framing | Accept (documented) | — |
| 5 | Audio accidentally persisted by a future change | Info disclosure | Low | High | No-audio static + schema gates merge-blocking; no write API exists | Low | — |
| 6 | Network egress added by a future change | Info disclosure | Low | High | No-egress static gate merge-blocking | Low | — |
| 7 | Miscalibration / bad placement skews counts | Bias | Med | Med | Calibration + placement documented in report; eval against labeled session | Accept (documented) | — |

## Enforcement

Rows 2, 3, 5, 6 are auto-gated (scanners + the no-audio/no-egress tests). Rows 1, 4, 7
are review-gated and depend on honest operation and the mandatory report disclosures.
There are no high/critical residual risks open.
