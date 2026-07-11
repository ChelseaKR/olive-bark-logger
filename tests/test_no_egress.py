"""Merge-blocking: prove the monitor makes no network egress.

Local-only is a guardrail. The strongest practical check for a dependency-free core
is a static one: no first-party module imports a networking library, and none shells
out (subprocess/ctypes/os.system/os.popen/os.spawn*/os.exec*) — a shell is just
another route to the network. (The report is a local HTML file; the store is local
SQLite; capture is local audio.)

The scanner functions live in `tests/gates.py` and are exercised against known
violations by `tests/test_gate_selftest.py`, so we know they still bite.
"""

from __future__ import annotations

from conftest import source_files
from gates import scan_exec_imports, scan_network_imports, scan_os_shell_calls


def test_no_first_party_module_imports_network():
    offenders: dict[str, set[str]] = {}
    for path in source_files():
        bad = scan_network_imports(path.read_text(encoding="utf-8"))
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"network imports found: {offenders}"


def test_no_first_party_module_shells_out():
    """No first-party module imports subprocess/ctypes or calls an os shell primitive."""
    offenders: dict[str, set[str]] = {}
    for path in source_files():
        source = path.read_text(encoding="utf-8")
        bad = scan_exec_imports(source) | scan_os_shell_calls(source)
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"shell-out / native-call bypasses found: {offenders}"


def test_runtime_pipeline_opens_no_socket(tmp_path, monkeypatch):
    """Run the full pipeline + report with sockets and shell-out booby-trapped;
    nothing should reach for the network. This complements the static scan with a
    behavioral guarantee."""
    import os
    import socket
    import subprocess

    def _boom(*_a, **_k):
        raise AssertionError("network/shell access attempted — egress guarantee violated")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(os, "system", _boom)

    from monitor.capture import LoudRegion, synthetic_session
    from monitor.config import Config
    from monitor.service import run_pipeline
    from report.render import generate_report_from_db
    from store import EventStore

    db = tmp_path / "olive.db"
    config = Config(db_path=str(db))
    with EventStore(db) as store:
        list(run_pipeline(synthetic_session(8.0, [LoudRegion(1.0, 4.0, 0.3)]), config, store))
    html = generate_report_from_db(str(db), config, generated_at="2026-01-01 UTC")
    assert "<h2>Methodology</h2>" in html  # full path ran without touching a socket
