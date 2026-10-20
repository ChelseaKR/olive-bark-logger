"""`make security` carries no pip-audit waivers, and the lock has no <3.10 branch.

Until the floor moved to Python 3.10 (ADR-0032) twelve advisories in pip-audit's own
dev-toolchain dependencies were waived, because every fix required Python >=3.10 and the
`python_full_version < '3.10'` branch of `uv.lock` could not install one. That branch is
gone, so a waiver would suppress nothing on any interpreter this repository supports.

Two checks keep it that way: an `--ignore-vuln` flag anywhere in the Makefile fails, so a
red audit is fixed by bumping the package rather than by turning the alert off, and a
`< '3.10'` resolution marker in `uv.lock` fails, because it means the floor was lowered
again without this file being revisited.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_makefile_carries_no_pip_audit_waivers() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^PIP_AUDIT_WAIVERS :=\s*$", text, re.MULTILINE), (
        "PIP_AUDIT_WAIVERS is no longer defined as empty"
    )
    assert not re.findall(r"--ignore-vuln\s+\S+", text), (
        "an --ignore-vuln flag is back in the Makefile; bump the package instead, or record "
        "the decision in an ADR first"
    )


def test_the_lock_has_no_branch_below_the_floor() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^requires-python = ">=3\.10"$', pyproject, re.MULTILINE)
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in lock
    assert "python_full_version < '3.10'" not in lock
