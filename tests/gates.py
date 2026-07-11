"""Pure scanner helpers behind the guarantee gates (no-audio, no-egress).

The gate tests (`test_no_audio.py`, `test_no_egress.py`) and the canary
self-tests (`test_gate_selftest.py`) all call these functions, so the same code
that clears the tree is the code proven to *bite* on a known violation. Each
`scan_*` takes a source string and returns the offenders it found (empty when
clean).
"""

from __future__ import annotations

import ast

# --- no-egress vocabulary -------------------------------------------------

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

# Shelling out is another way to reach the network (or disk); ctypes can call
# libc directly. First-party code must never import either.
FORBIDDEN_EXEC_MODULES = {
    "subprocess",
    "ctypes",
}

# --- no-audio vocabulary --------------------------------------------------

# APIs that would let raw audio reach disk or a wire. The point of the gate is
# that none of these appear in the codebase at all.
FORBIDDEN_AUDIO_APIS = (
    "wave",  # stdlib WAV writer
    "soundfile",
    "scipy.io.wavfile",
    "aifc",
    "sunau",
    ".tobytes(",
    "audioop",
)

# os.open flags that request a writable descriptor.
WRITE_OPEN_FLAGS = {"O_WRONLY", "O_RDWR", "O_CREAT", "O_APPEND", "O_TRUNC"}


def imported_modules(source: str) -> set[str]:
    """Every module name reached by `import x` / `from x import y`."""
    tree = ast.parse(source)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def _matches(mods: set[str], forbidden: set[str]) -> set[str]:
    return {m for m in mods if m in forbidden or m.split(".")[0] in forbidden}


def scan_network_imports(source: str) -> set[str]:
    """Networking libraries imported by this source."""
    return _matches(imported_modules(source), NETWORK_MODULES)


def scan_exec_imports(source: str) -> set[str]:
    """subprocess/ctypes imports — shell-out / native-call bypasses."""
    return _matches(imported_modules(source), FORBIDDEN_EXEC_MODULES)


def scan_os_shell_calls(source: str) -> set[str]:
    """Calls to os.system / os.popen / os.spawn* / os.exec* (shell bypasses)."""
    offenders: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        value = node.func.value
        if isinstance(value, ast.Name) and value.id == "os":
            attr = node.func.attr
            if attr in {"system", "popen"} or attr.startswith(("spawn", "exec")):
                offenders.add(f"os.{attr}")
    return offenders


def scan_audio_write_apis(source: str) -> list[str]:
    """Forbidden audio-serialization APIs present as text in the source."""
    return [api for api in FORBIDDEN_AUDIO_APIS if api in source]


def _os_open_write_flags(call: ast.Call) -> set[str]:
    flags: set[str] = set()
    for arg in call.args[1:]:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Attribute) and sub.attr in WRITE_OPEN_FLAGS:
                flags.add(sub.attr)
            elif isinstance(sub, ast.Name) and sub.id in WRITE_OPEN_FLAGS:
                flags.add(sub.id)
    return flags


def scan_binary_write(source: str) -> list[str]:
    """Ways to dump bytes to disk: binary-mode open()/io.open(), Path.write_bytes,
    and os.open() requesting a writable descriptor."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # open("x", "wb") or io.open("x", "wb") — literal binary mode.
        is_builtin_open = isinstance(func, ast.Name) and func.id == "open"
        is_io_open = (
            isinstance(func, ast.Attribute)
            and func.attr == "open"
            and isinstance(func.value, ast.Name)
            and func.value.id == "io"
        )
        if is_builtin_open or is_io_open:
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and "b" in str(arg.value):
                    offenders.append("open(binary)")

        # Path(...).write_bytes(...) — matched by method name.
        if isinstance(func, ast.Attribute) and func.attr == "write_bytes":
            offenders.append("write_bytes")

        # os.open(..., os.O_WRONLY | os.O_CREAT) — low-level writable descriptor.
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "open"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
            and _os_open_write_flags(node)
        ):
            offenders.append("os.open(write)")

    return offenders
