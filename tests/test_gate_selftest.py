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
