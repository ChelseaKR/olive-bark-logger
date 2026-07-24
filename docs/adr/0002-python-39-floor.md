# 0002. Python ≥3.9 floor (divergence from the ≥3.12 standard)

**Status:** Accepted (time-boxed divergence, not a pass) · **Date:** 2026-07-05

**Revisit-by:** 2026-10-05

## Context
`STANDARDS/CODE-QUALITY-STANDARD.md` (CQ-01) sets a floor of Python ≥3.12 (≥3.11 only
with an EOL-track ADR; ≥3.9 is the standard's explicitly *named, rejected* pattern).
This repo targets `requires-python = ">=3.9"` (`pyproject.toml`) as a deliberate,
pre-existing design goal: the core (`monitor/`, `store/`, `report/`) has zero runtime
dependencies specifically so it can run on an old, already-imaged Raspberry Pi with
whatever Python 3.9+ ships on it, with no installs beyond the standard library
(`docs/ROADMAP.md`'s "Zero-dependency, pure-Python core" ADR). Dropping to a ≥3.12 floor
would mean either requiring a Pi OS reimage/Python upgrade before the tool runs at all,
or dropping the zero-install quickstart promise in the README.

**New evidence as of this pass (2026-07-05):** hardening `make security` from a
soft-skip to a hard-fail (this remediation's P0-3) surfaced ten real `pip-audit`
findings in the **dev tooling** (filelock, msgpack, pip, pytest, requests, urllib3 —
transitive dependencies of `pip-audit`/`pytest` themselves, never shipped in the
zero-dependency runtime). Every fix version for all ten requires a Python ≥3.10 host
interpreter; none are installable into a `.venv` built on 3.9. This is the first
concrete cost the 3.9 floor has imposed beyond "old code needs a shim" — it now also
blocks picking up security fixes in the *development* toolchain (waived, dated, with
full detail in `docs/RESPONSIBLE-TECH-AUDITS.md` §F and `Makefile`'s
`PIP_AUDIT_WAIVERS`). The *runtime* is unaffected (zero dependencies).

Two honest paths, both discussed in the remediation plan (P1-5):
- **(a) Bump to `>=3.12`.** Delete the `ZoneInfo` fallback (`monitor/config.py:16-21`)
  and the mypy-under-3.10 workaround (`pyproject.toml`); shrink the CI matrix to
  3.12/3.13; commit `.python-version`. This is the standard-conformant path and would
  also resolve the dev-toolchain CVE waivers above for free.
- **(b) Keep 3.9, record the divergence in this ADR.** The standard as written only
  sanctions ≥3.11-with-ADR — so even with this ADR, a 3.9 floor is a **tracked
  nonconformance**, not a pass. What improves is the honesty of the claim (the README's
  Standards Conformance table says "Applies — gap tracked in GAP-CQ-1", not silence).

## Decision
**(b) for now.** This is a deliberately reversible, low-risk default chosen because
bumping the floor is a substantive, multi-file change (deleting compat shims, re-running
the full test matrix, confirming Pi/PWA deploy targets still work) that changes runtime
behavior on real hardware this project's maintainer depends on — not something to change
unilaterally as part of a documentation/gate-hardening pass. **This is a decision for the
maintainer to make deliberately, not a default to leave standing indefinitely** — the new
dev-toolchain CVE evidence above is a real, mounting cost of staying on 3.9 and should
weigh into that decision sooner rather than later.

## Consequences
- **Easier:** the Pi deployment target keeps its zero-install promise unchanged; no
  compat-shim removal risk introduced in this pass.
- **Harder / accepted:** Code Quality standard conformance stays "gap tracked", not
  "Applies" outright; ten dev-toolchain CVEs stay waived (not fixed) until either the
  floor moves or upstream ships a <3.10-compatible patch; mypy runs under a pinned
  `<2` floor (`pyproject.toml`) since `mypy>=2` dropped 3.9 host support (verified
  2026-07-05).
- **Mandatory review:** `make python-floor-review` fails after 2026-10-05 so this
  divergence cannot quietly become permanent. Review the active Raspberry Pi OS
  Python floor, the current dev-tool vulnerability set, and the cost of a 3.12
  upgrade. Record a new decision; do not merely move the date.
- **Earlier revisit trigger:** either (1) the maintainer decides to reimage/upgrade the Pi
  target, making option (a) free, or (2) the dev-toolchain CVE list grows large enough
  that the waiver-maintenance cost exceeds the shim-deletion cost of option (a).
