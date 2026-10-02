# 0031. Develop on Python 3.12; the 3.9 runtime floor is held by CI

**Status:** Accepted · **Date:** 2026-10-01 · **Amends:** [ADR-0002](./0002-python-39-floor.md) (its decision is unchanged)

## Context
[ADR-0002](./0002-python-39-floor.md) keeps `requires-python = ">=3.9"` so the core runs
on a Raspberry Pi with whatever Python 3.9+ ships on it. Until now `.python-version` held
the same number, so `make dev` built the local `.venv` on 3.9 and `make security` audited
the `python_full_version < '3.10'` branch of `uv.lock`.

On that branch the dev toolchain can no longer be kept patched. Every advisory fix since
2026-07-05 has required Python 3.10 or later, so each new advisory became a waiver in
`PIP_AUDIT_WAIVERS`. On 2026-10-01 urllib3 2.8.0 (PYSEC-2026-4175, PYSEC-2026-4176 and
PYSEC-2026-4177) was the next one: no fixed urllib3 installs on 3.9, and the choice was to
waive three more advisories or to stop auditing the floor branch locally. The maintainer
chose not to waive.

Two things share the number 3.9 here, and only one of them is a deploy constraint:

- **The runtime floor**: what the Pi install path (`scripts/setup-pi.sh`, the system
  `python3`, `deploy/olive-monitor.service`) needs. That is `requires-python`.
- **The development interpreter**: what `make dev`, `make verify` and `make security` run
  on. Nothing deploys from it.

## Decision
Split them.

- `.python-version` is **3.12**, matching CI's `verify` job and `release.yml`. `make dev`
  builds `.venv` on 3.12, so `make security` audits the same `>=3.10` resolution CI does.
- `requires-python` stays **`>=3.9`**. The Pi install path, ADR-0002's decision and its
  Consequences are unchanged.
- **The 3.9 floor is exercised by CI, not by the local venv.** The `test-matrix
  (ubuntu-latest, 3.9)` job runs the full suite on 3.9 and is a required check in
  `.github/rulesets/main.json`, and the nightly macOS sweep keeps its 3.9 leg. A local
  `make verify` no longer proves anything about 3.9.
- `PIP_AUDIT_WAIVERS` stays as it is, held to `uv.lock` by `tests/test_pip_audit_waivers.py`.
  On the default 3.12 venv the twelve IDs match nothing and are inert; they apply only to
  a venv deliberately built on the floor (`uv sync --locked --group dev --python 3.9`).
  No new waiver was added for urllib3 2.8.0.
- mypy stays capped below 2, because CI's 3.9 leg installs the same dev group on a 3.9
  interpreter.

## Consequences
- **Easier:** local `make security` is fixed rather than waived for advisories whose fix
  needs 3.10 or later, and it audits the same resolution as CI.
- **Harder / accepted:** a 3.10-only construct that runs at import or call time (see
  ADR-0014's accepted risk) now passes every local gate and is caught only by CI's 3.9
  job. To reproduce that job locally, build a 3.9 venv as above and run `make test`.
- **Revisit trigger:** the same as ADR-0002's. If the floor itself moves to 3.10 or later,
  the waivers, the mypy cap and this split all go with it.
