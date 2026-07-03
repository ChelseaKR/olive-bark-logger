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

import ast

from conftest import ROOT, source_files
from gates import scan_exec_imports, scan_network_imports, scan_os_shell_calls

# Surgical carve-out: `socket` stays banned everywhere except the one module that owns
# the opt-in, emit-only local automation feed. That module may only ever open an AF_UNIX
# (local filesystem) datagram socket — never AF_INET — which cannot reach a network, so
# the no-egress guarantee holds. The two canary tests below enforce that restriction.
ALLOWED_SOCKET_FILES = {"monitor/ipc.py"}


def test_no_first_party_module_imports_network():
    offenders: dict[str, set[str]] = {}
    for path in source_files():
        bad = scan_network_imports(path.read_text(encoding="utf-8"))
        relative_path = path.relative_to(ROOT).as_posix()
        if relative_path in ALLOWED_SOCKET_FILES:
            # The IPC feed is allowed `socket` (AF_UNIX only, proven below) but nothing else.
            bad -= {"socket"}
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


def _attr_name(node: ast.AST) -> str | None:
    """Return the trailing attribute name (e.g. `AF_UNIX` from `socket.AF_UNIX`)."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def test_ipc_module_uses_only_af_unix():
    """The one module allowed `socket` must only ever ask for AF_UNIX, never AF_INET.

    A local filesystem socket cannot reach a network, so this is what keeps the
    no-egress guarantee intact even with the surgical carve-out above.
    """
    tree = ast.parse((ROOT / "monitor" / "ipc.py").read_text(encoding="utf-8"))

    socket_calls = 0
    for node in ast.walk(tree):
        # Every socket.socket(...) construction must pass AF_UNIX as its family.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "socket"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "socket"
        ):
            socket_calls += 1
            assert node.args, "socket.socket() must be called with an explicit family"
            assert _attr_name(node.args[0]) == "AF_UNIX", (
                f"socket.socket() family must be AF_UNIX, got {ast.dump(node.args[0])}"
            )
            assert len(node.args) > 1 and _attr_name(node.args[1]) == "SOCK_DGRAM", (
                "IPC socket must remain a one-way AF_UNIX datagram"
            )

    assert socket_calls >= 1, "expected at least one socket.socket() call in ipc.py"

    # AF_INET / AF_INET6 must never appear anywhere in the module, not even in a comment
    # that got parsed as an attribute — a purely static, name-level guarantee.
    for node in ast.walk(tree):
        if _attr_name(node) in {"AF_INET", "AF_INET6"}:
            raise AssertionError("ipc.py references AF_INET/AF_INET6 — INET egress possible")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"bind", "listen", "accept", "recv", "recvfrom"}, (
                f"ipc.py must remain emit-only; found {node.func.attr}()"
            )


def test_ipc_emitter_cannot_open_inet_socket(monkeypatch):
    """Booby-trap INET socket creation and exercise the emitter to prove it never tries.

    Mirrors test_runtime_pipeline_opens_no_socket's `_boom` pattern, but only trips on an
    AF_INET/AF_INET6 family so the legitimate AF_UNIX datagram socket is still allowed.
    """
    import socket
    import tempfile
    from pathlib import Path

    from monitor.ipc import LocalIpcEmitter

    real_socket = socket.socket

    def _boom(family=socket.AF_INET, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError("INET socket attempted — egress guarantee violated")
        return real_socket(family, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", _boom)

    # A short-named path with no listener bound (AF_UNIX paths are length-capped, so we
    # avoid the deep pytest tmp dir): emit must open an AF_UNIX socket, swallow the
    # missing-peer error, and never reach for INET.
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        emitter = LocalIpcEmitter(str(Path(d) / "ipc.sock"))
        emitter.emit({"type": "event", "peak_level": -12.0})
        emitter.close()


def test_ipc_emitter_is_nonblocking_and_drops_backpressure(monkeypatch):
    """A bound but stalled listener must never freeze or crash the capture loop."""
    from monitor.ipc import LocalIpcEmitter

    class FakeSocket:
        blocking: bool | None = None

        def setblocking(self, value):
            self.blocking = value

        def sendto(self, _data, _path):
            raise BlockingIOError("listener queue is full")

        def close(self):
            pass

    fake = FakeSocket()
    monkeypatch.setattr("monitor.ipc.socket.socket", lambda *_args: fake)
    emitter = LocalIpcEmitter("unused.sock")
    emitter.emit({"type": "event"})
    assert fake.blocking is False
    emitter.close()
