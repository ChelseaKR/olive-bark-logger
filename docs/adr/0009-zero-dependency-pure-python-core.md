# 0009. Zero-dependency, pure-Python core

**Status:** Accepted · **Date:** 2026-06-05 · **Migrated:** 2026-09-05 from `docs/ROADMAP.md` §6 (GAP-DOC-1)

## Context
The always-run path — level math, event detection, the SQLite store, and report
rendering — is what has to keep working unattended on a Raspberry Pi for weeks, and
what `make verify` has to be able to check on any machine. Every dependency on that
path is a thing that can fail to install on an ARM board, drift a wheel, ship a CVE
that has to be waived or fixed, or need a compiler at the worst moment.

The obvious candidate was numpy, for RMS. RMS over a frame is a sum of squares and a
square root.

## Decision
`monitor/`, `store/` and `report/` use only the **Python standard library**. The gate
set runs with no installs. The only optional extras are capture-side and export-side,
never on the always-run path: `live` (`sounddevice`) for real microphone capture, and
later `pdf` (`weasyprint`, [ADR-0004](./0004-weasyprint-for-tagged-pdf-a-export.md))
for the tagged PDF/A export.

**Rejected: numpy in the core** — unnecessary for RMS, and it adds a dependency to the
path that always runs.

## Consequences
- **Easier:** installation on a Pi is a checkout; the runtime attack surface and the
  supply-chain surface are the standard library; `pip-audit` findings are confined to
  the dev toolchain.
- **Easier:** this is the constraint that makes several later decisions the right ones
  rather than merely acceptable — JSON config
  ([ADR-0010](./0010-json-config-not-toml.md)) and hand-rendered SVG charts
  ([ADR-0011](./0011-hand-rendered-inline-svg-charts.md)) both follow from it.
- **Harder / accepted:** anything a library would have given for free is written here
  and tested here.
- **Revisit trigger:** a new dependency on the always-run path needs its own ADR, and
  has to argue against this one rather than around it.
