# 0032. Python 3.10 floor

**Status:** Accepted · **Date:** 2026-10-19 · **Supersedes:** [ADR-0002](./0002-python-39-floor.md) · **Amends:** [ADR-0031](./0031-dev-interpreter-312-runtime-floor-39.md)

## Context
[ADR-0002](./0002-python-39-floor.md) kept `requires-python = ">=3.9"` for an old,
already-imaged Raspberry Pi. That floor made `uv.lock` carry a separate
`python_full_version < '3.10'` resolution on which no fixed version of urllib3, msgpack,
pip, filelock, pytest or requests installs, because each fix requires Python 3.10 or later.
GitHub's dependency scanner reads that branch of the lock and reported 14 open Dependabot
alerts (5 high, 9 medium) against dev-toolchain packages. The shipped runtime still has no
dependencies; the alerts were about the lock, not the product.

## Decision
- `requires-python` is `>=3.10`, and `uv.lock` is re-locked so the 3.9 resolution no longer
  exists. The `>=3.10` resolution already held the patched versions.
- Ruff targets `py310`. The CI test matrix and the nightly macOS sweep run 3.10 through 3.13.
- The twelve `PIP_AUDIT_WAIVERS` entries are deleted. `tests/test_pip_audit_waivers.py` now
  fails if one comes back.
- The required check `test-matrix (ubuntu-latest, 3.9)` is removed from
  `.github/rulesets/main.json`. The live ruleset must be updated to match.
- The `pdf` extra no longer needs Python version markers, since WeasyPrint's own floor is
  now the core floor.

## Consequences
- **Easier:** `make security` and CI audit the same resolution with no waivers.
- **Harder / accepted:** a Raspberry Pi image whose system `python3` is 3.9 can no longer
  install the package. Raspberry Pi OS releases since Bookworm ship 3.11.
- `mypy<2` is left as it was; lifting it is a separate change.
