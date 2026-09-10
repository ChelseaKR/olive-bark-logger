"""Every pip-audit waiver covers the 3.9 branch of the lock and nothing else.

`make security` runs pip-audit against the *installed environment*. `.python-version` is
3.9, so a developer's `.venv` resolves the `python_full_version < '3.10'` branch of
`uv.lock` — and on that branch several dev-toolchain packages sit below their first fixed
version, because every fix so far requires Python >=3.10 and this repository's floor is 3.9
(ADR-0002 / CQ-01). Twelve advisories are waived for that reason.

The waiver comment in the `Makefile` carries the sentence the whole arrangement rests on:

    uv.lock carries pip 26.2.1 for >=3.10, so CI (3.12) is fixed, not waived

That is the difference between "we cannot fix this on our floor interpreter" and "we have
turned off an alert". It was prose, and nothing re-derived it — so a waiver added for the
3.9 branch would keep suppressing the finding on CI's 3.12 the day the >=3.10 resolution
also fell behind, and the gate would stay green over a package CI actually installs.

This module makes it checkable, offline, from the lock:

* every id in `PIP_AUDIT_WAIVERS` has a registry entry naming its package and its first
  fixed version, and every registry entry is in the Makefile — neither list may grow alone;
* for every waived package that `uv.lock` resolves, the **>=3.10** resolution is at or above
  the fixed version, so CI is fixed rather than waived;
* the **<3.10** resolution is *below* it, because a waiver over a branch that is already
  fixed is suppressing nothing and should be deleted (the exemption-list rot this repository
  has found elsewhere, pointed at its own suppression inventory).

What it deliberately does not check is whether a fix has since become installable on 3.9 —
that is a question for the index, not the lock. `Makefile`'s comment names the command
(`uv pip install --dry-run --python .venv/bin/python '<pkg>>=<fix>'`) and the audit cadence
that asks it. Re-derived by hand 2026-09-10 for all seven packages: unsatisfiable on 3.9 in
every case, each because the fix depends on Python>=3.10.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"
LOCKFILE = ROOT / "uv.lock"

#: The floor this repository supports, and therefore the resolution branch a default
#: `make dev` venv installs. `.python-version` holds the same number.
FLOOR_BRANCH = "python_full_version < '3.10'"

#: advisory id -> (package, first fixed version). Fixed versions are pip-audit's own
#: `fix_versions`, read off `pip-audit --format=json` run with no waivers on the 3.9 venv
#: (2026-09-10, twelve findings, twelve waivers, none dead), not looked up by hand.
WAIVER_REGISTRY: dict[str, tuple[str, str]] = {
    "PYSEC-2026-3721": ("pip", "26.2"),
    "PYSEC-2026-3447": ("setuptools", "83.0.0"),
    "GHSA-w853-jp5j-5j7f": ("filelock", "3.20.1"),
    "GHSA-qmgc-5h2g-mvrw": ("filelock", "3.20.3"),
    "GHSA-6v7p-g79w-8964": ("msgpack", "1.2.1"),
    "PYSEC-2026-196": ("pip", "26.1.2"),
    "GHSA-58qw-9mgm-455v": ("pip", "26.1"),
    "GHSA-jp4c-xjxw-mgf9": ("pip", "26.1"),
    "GHSA-6w46-j5rx-g56g": ("pytest", "9.0.3"),
    "GHSA-gc5v-m9x4-r6x2": ("requests", "2.33.0"),
    "PYSEC-2026-142": ("urllib3", "2.7.0"),
    "PYSEC-2026-141": ("urllib3", "2.7.0"),
}

#: Waived packages `uv.lock` does not resolve at all, with the reason. `setuptools` is a
#: venv seed package pip puts there, not a locked dependency, so it has no >=3.10 resolution
#: to hold to anything -- and it does not occur on CI. Named rather than skipped silently:
#: "absent from the lock" and "the lock reader stopped working" are the same observation.
UNLOCKED_PACKAGES: dict[str, str] = {
    "setuptools": "a venv seed package pip installs, not a locked dependency; absent from CI",
}


def _version_tuple(version: str) -> tuple[int, ...]:
    """A dotted numeric version as a tuple. Every version this file compares is numeric."""
    parts = version.split(".")
    assert all(part.isdigit() for part in parts), f"non-numeric version component in {version!r}"
    return tuple(int(part) for part in parts)


def _waived_ids() -> list[str]:
    """Advisory ids from the Makefile's `PIP_AUDIT_WAIVERS`, in file order."""
    text = MAKEFILE.read_text(encoding="utf-8")
    start = text.index("PIP_AUDIT_WAIVERS :=")
    # The assignment is a backslash-continued block; it ends at the first line that does not
    # continue. Reading to the next blank line would swallow the recipe that uses it.
    block: list[str] = []
    for line in text[start:].splitlines():
        block.append(line)
        if not line.rstrip().endswith("\\"):
            break
    return re.findall(r"--ignore-vuln\s+([A-Za-z0-9-]+)", "\n".join(block))


def _lock_resolutions(package: str) -> dict[str, str]:
    """`{"floor": version, "modern": version}` for one package in `uv.lock`.

    A package with a single unconditional entry appears under both keys: it resolves to the
    same version on every interpreter, which is the answer both questions want.
    """
    found: dict[str, str] = {}
    for block in LOCKFILE.read_text(encoding="utf-8").split("[[package]]")[1:]:
        name = re.search(r'^\s*name = "([^"]+)"', block, re.M)
        if not name or name.group(1) != package:
            continue
        version = re.search(r'^\s*version = "([^"]+)"', block, re.M)
        assert version, f"{package} block in uv.lock carries no version"
        markers = re.search(r"^\s*resolution-markers = \[(.*?)^\]", block, re.M | re.S)
        if markers is None:
            found["floor"] = found["modern"] = version.group(1)
        elif FLOOR_BRANCH in markers.group(1):
            found["floor"] = version.group(1)
        else:
            found["modern"] = version.group(1)
    return found


def test_the_makefile_and_the_registry_name_the_same_waivers() -> None:
    """Self-limiting in both directions. A waiver added to the build with no entry here has
    no recorded package or fixed version, so nothing below can hold it to anything; an entry
    here with no waiver in the build is describing an exemption that no longer exists."""
    ids = _waived_ids()
    assert len(ids) >= 10, f"only {len(ids)} waiver(s) parsed out of the Makefile; the reader broke"
    assert len(ids) == len(set(ids)), f"duplicate waiver ids: {sorted(ids)}"
    # `_waived_ids` reads the backslash-continued assignment and stops at its last line, so an
    # `--ignore-vuln` written anywhere else in the file would be invisible to this module. Make
    # would reject a stray tab-indented line outside a recipe, so it could not take effect
    # silently -- but "the gate cannot see it" and "it cannot happen" are different claims, and
    # only one of them is this module's to make. Found by a negative control that appended an
    # id *after* the final entry: the file changed, `git hash-object` moved, and the gate stayed
    # green because the edit had landed outside the property being tested.
    everywhere = re.findall(
        r"--ignore-vuln\s+([A-Za-z0-9-]+)", MAKEFILE.read_text(encoding="utf-8")
    )
    assert everywhere == ids, (
        "an --ignore-vuln appears in the Makefile outside PIP_AUDIT_WAIVERS, where this check "
        f"cannot hold it to anything: {sorted(set(everywhere) - set(ids))}"
    )
    assert set(ids) == set(WAIVER_REGISTRY), (
        "PIP_AUDIT_WAIVERS and WAIVER_REGISTRY have drifted apart. "
        f"in the Makefile only={sorted(set(ids) - set(WAIVER_REGISTRY))} "
        f"in the registry only={sorted(set(WAIVER_REGISTRY) - set(ids))}"
    )


def test_the_lock_reader_still_finds_both_resolution_branches() -> None:
    """The floor. A reader that has stopped matching returns `{}` for every package, and an
    empty mapping satisfies every loop below by describing nothing."""
    resolutions = _lock_resolutions("urllib3")
    assert set(resolutions) == {"floor", "modern"}, (
        f"uv.lock's urllib3 entries no longer split into a <3.10 and a >=3.10 resolution: "
        f"{resolutions}"
    )
    assert resolutions["floor"] != resolutions["modern"], (
        "the two urllib3 resolutions are the same version; this test would then be comparing "
        "one number with itself"
    )
    # Whatever the lock says, the floor it is read against is the one the repo declares.
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip().startswith("3.9")


@pytest.mark.parametrize(
    ("advisory", "package", "fixed"),
    sorted((key, *value) for key, value in WAIVER_REGISTRY.items()),
)
def test_ci_is_fixed_rather_than_waived_for_every_waived_advisory(
    advisory: str, package: str, fixed: str
) -> None:
    """The sentence the waiver block rests on, re-derived from the lock.

    A waiver is acceptable because the *floor* interpreter has no fix available. It is not
    acceptable for it to also cover the interpreter CI runs, where a fix is installed --
    that would be an alert turned off over a package CI actually ships through its gates.
    """
    resolutions = _lock_resolutions(package)
    if not resolutions:
        assert package in UNLOCKED_PACKAGES, (
            f"{advisory} waives {package}, which uv.lock does not resolve and which is not "
            "recorded in UNLOCKED_PACKAGES with a reason"
        )
        return
    modern = resolutions.get("modern")
    assert modern is not None, f"uv.lock has no >=3.10 resolution for {package}"
    assert _version_tuple(modern) >= _version_tuple(fixed), (
        f"{advisory}: uv.lock resolves {package} {modern} for Python >=3.10, below the fixed "
        f"version {fixed}. The waiver is written for the 3.9 floor but it also suppresses "
        f"this finding on CI, where a fix is installable -- fix CI rather than waiving it"
    )


@pytest.mark.parametrize(
    ("advisory", "package", "fixed"),
    sorted((key, *value) for key, value in WAIVER_REGISTRY.items()),
)
def test_every_waiver_still_covers_something_on_the_floor_branch(
    advisory: str, package: str, fixed: str
) -> None:
    """The other half, and the one an exemption list normally loses first.

    Once the floor resolution reaches the fixed version the waiver suppresses nothing, and a
    suppression that suppresses nothing makes the inventory's count an upper bound nobody can
    check. Deleting it is then the correct resolution, and this is what asks for it.
    """
    resolutions = _lock_resolutions(package)
    if not resolutions:
        assert package in UNLOCKED_PACKAGES
        return
    floor = resolutions.get("floor")
    assert floor is not None, f"uv.lock has no <3.10 resolution for {package}"
    assert _version_tuple(floor) < _version_tuple(fixed), (
        f"{advisory}: uv.lock resolves {package} {floor} on the 3.9 floor, at or above the "
        f"fixed version {fixed}. Nothing is being suppressed -- delete the waiver"
    )
