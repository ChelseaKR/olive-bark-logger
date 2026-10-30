# 0032. Python 3.11 floor

**Status:** Accepted · **Date:** 2026-10-29 · **Supersedes:** [ADR-0002](./0002-python-39-floor.md) · **Amends:** [ADR-0031](./0031-dev-interpreter-312-runtime-floor-39.md), [ADR-0014](./0014-type-check-under-310-semantics.md)

## Context
[ADR-0002](./0002-python-39-floor.md) kept `requires-python = ">=3.9"` for an old,
already-imaged Raspberry Pi. That floor made `uv.lock` carry separate resolutions for
Python 3.9 and 3.10, and on those resolutions no fixed version of pillow, urllib3, msgpack,
filelock, pip, pytest or requests installs, because each fix requires a newer Python.
GitHub's dependency scanner reads every branch of the lock, so about 30 critical and high
alerts stayed open against versions that only the 3.9 and 3.10 resolutions held. The
shipped runtime still has no dependencies; the alerts were about the lock, not the
product.

A 3.10 floor was proposed first (PR #133). It clears the 3.9 branch but leaves the 3.10
one, which still pins vulnerable pillow and others. Separately, `ubuntu-latest` is now
Ubuntu 26.04, where `actions/setup-python` has no Python 3.9 build, so the required 3.9
test-matrix leg could no longer run at all.

## Decision
- `requires-python` is `>=3.11`, and `uv.lock` is re-locked so the 3.9 and 3.10
  resolutions no longer exist. The `>=3.11` resolution already held the patched versions.
- Ruff targets `py311` and mypy checks under 3.11. The CI test matrix and the nightly
  macOS sweep run 3.11 through 3.13.
- The twelve `PIP_AUDIT_WAIVERS` entries are deleted. `tests/test_pip_audit_waivers.py`
  fails if one comes back, or if the lock regains a branch below 3.11.
- The required checks `test-matrix (ubuntu-latest, 3.9)` and `(ubuntu-latest, 3.10)` are
  removed from `.github/rulesets/main.json`. The live ruleset must be updated to match,
  or the verify job's ruleset check reports the difference and no PR can merge.
- The `pdf` extra no longer needs Python version markers, since WeasyPrint's own floor
  (3.10) is below the core floor.

## Consequences
- **Easier:** `make security` and CI audit the same resolution with no waivers.
- **Harder / accepted:** a Raspberry Pi image whose system `python3` is 3.9 or 3.10 can no
  longer install the package. Raspberry Pi OS Bookworm and later ship 3.11.
- ADR-0014's split (run on 3.9, type-check under 3.10) no longer applies: the runtime
  floor and the checked version are both 3.11.
- `mypy<2` is left as it was; lifting it is a separate change.
