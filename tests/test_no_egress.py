"""Merge-blocking: prove the monitor makes no network egress.

Local-only is a guardrail. The strongest practical check for a dependency-free core
is a static one: no first-party module imports a networking library. (The report is
a local HTML file; the store is local SQLite; capture is local audio.)
"""

from __future__ import annotations

import ast

from conftest import source_files

NETWORK_MODULES = {
    "socket",
    "ssl",
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "ftplib",
    "smtplib",
    "telnetlib",
    "asyncio",
    "requests",
    "httpx",
    "aiohttp",
    "websocket",
    "websockets",
    "boto3",
    "google.cloud",
}


def _imported_modules(tree: ast.AST) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_no_first_party_module_imports_network():
    offenders: dict[str, set[str]] = {}
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods = _imported_modules(tree)
        bad = {m for m in mods if m in NETWORK_MODULES or m.split(".")[0] in NETWORK_MODULES}
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"network imports found: {offenders}"


def test_runtime_pipeline_opens_no_socket(tmp_path, monkeypatch):
    """Run the full pipeline + report with sockets booby-trapped; nothing should reach
    for the network. This complements the static scan with a behavioral guarantee."""
    import socket

    def _boom(*_a, **_k):
        raise AssertionError("network access attempted — egress guarantee violated")

    monkeypatch.setattr(socket, "socket", _boom)

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
