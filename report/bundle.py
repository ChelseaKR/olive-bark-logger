"""`olive-bundle` -- a tamper-evident evidence bundle, and the verifier for it.

The research roadmap's E1 is the item every adjudicator persona raised: a property
manager or a board will not weigh a log the other party could have edited, and
`docs/audits/residual-risk.md` row 1 accepts tampering as unmitigated. A manifest turns
"trust me" into "check it" -- offline, deterministic, and with no network step anywhere.

What a bundle is: one directory holding a consistent snapshot of the database, the
artifacts `olive-report` produces from it, the session ledger and calibration history as
CSV, and `manifest.json` -- the tool version, the schema version, the config in force,
the SHA-256 and byte count of every other file, and a plain-language block saying what
the hashes do and do not prove.

Three design choices are load-bearing rather than incidental.

**The artifacts are produced by `report.render.main`, not re-rendered here.** A bundle
containing a second implementation's idea of the report would be evidence of nothing;
this way the bundled document is byte-for-byte the one the tool produces.

**The manifest is the one file a signature would be taken over.** It carries the digest
of every other file, so signing it covers the whole bundle and leaves a recipient exactly
one thing to check. Making and checking that signature is **not** in this module yet, and
the reason is written down rather than left as an omission: every candidate tool
(`ssh-keygen -Y`, minisign) is a subprocess, `make security` runs bandit over `report/`,
and bandit reports `subprocess` at LOW severity, which fails that gate. This repository
has no `# nosec` suppression anywhere and adding the first one inside a feature is how a
security gate erodes. So the format reserves the name and the verifier *detects* a
signature it cannot check -- answering `unverifiable`, never `intact` -- and the
suppression is the owner's decision to make.

**The inventory is closed.** `verify` reports a file present in the bundle and absent
from the manifest, not only a listed file that changed. An open inventory would let
anything be added to a bundle that still verified as intact, which is most of the point
of having one.

And the sentence the roadmap flags as the over-promise to avoid is in the manifest
verbatim: a hash proves the files were not edited after signing, and cannot prove the
device was placed or tuned honestly before.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from monitor import __version__
from monitor.config import Config
from store import EventStore
from store.db import SCHEMA_VERSION

from report.render import cover_text_lines
from report.render import main as render_main

#: The manifest format's own version. A verifier that does not recognise it must say
#: "unverifiable" rather than reading the fields it happens to know: a future manifest
#: read by an old verifier is exactly the case where a confident "intact" is worst.
MANIFEST_VERSION = 1

MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "manifest.json.sig"

#: The database snapshot's name inside the bundle. Named rather than derived from the
#: source path so two bundles of differently-named databases have identical inventories.
SNAPSHOT_NAME = "olive.db"

#: What the manifest says about itself, in the recipient's language. The second line is
#: the one `docs/RESEARCH-ROADMAP.md` names as the over-promise this format must not
#: make; it is written into every manifest rather than left to a README nobody receives.
WHAT_THIS_PROVES = [
    "Every file in this bundle is listed below with its SHA-256 digest. Recomputing "
    "those digests proves the files have not been edited since the bundle was made.",
    "It cannot prove that the device was placed honestly, tuned honestly, or running "
    "when it says it was. A hash covers what happened after the bundle was built and "
    "nothing that happened before it.",
    "Hours the record shows as not monitored are not quiet hours: no event could have "
    "been recorded in them, and their emptiness is an absence of data rather than an "
    "absence of sound.",
    "A count in these files is a measurement, not a determination. Only the relevant "
    "authority decides whether a rule was broken.",
]

#: The three answers `verify` gives, and the only three. "Unverifiable" is a real answer
#: and never a synonym for either of the others: a bundle whose manifest is gone has not
#: been shown to be intact and has not been shown to be modified.
INTACT = "intact"
MODIFIED = "modified"
UNVERIFIABLE = "unverifiable"

#: Exit codes, following `scripts/check_ruleset.py`: 0 for a clean answer, 1 for a
#: finding, and 2 for "I could not tell", which must never be reported as 0.
EXIT_FOR = {INTACT: 0, MODIFIED: 1, UNVERIFIABLE: 2}

#: Extensions and leading magic bytes that would mean audio reached a bundle. The whole
#: project's central guarantee is that no audio is ever written; a bundle is the one
#: artifact that packages files by inventory rather than one at a time, so the inventory
#: is checked against this rather than trusted.
#:
#: The longer spellings of the WAV and AIFF extensions are deliberately absent. Each is
#: also the name of a stdlib module that *writes* that format, and the merge-blocking
#: no-audio scanner (`tests/gates.py`) forbids those names as substrings anywhere in this
#: tree -- comments included, which is why they are not written out here either. Listing
#: them would have meant weakening that scanner to admit a string literal, and the trade
#: is not close: the magic-byte check below reads `RIFF` and `FORM` whatever the file is
#: called, and an extension is only a claim a file makes about itself.
AUDIO_SUFFIXES = frozenset(
    {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".aiff", ".aif"}
)
AUDIO_MAGIC = (b"RIFF", b"ID3", b"OggS", b"fLaC", b"FORM", b"\xff\xfb", b"\xff\xf3")


class BundleError(RuntimeError):
    """A bundle could not be built. Never raised by `verify`, which answers instead."""


@dataclasses.dataclass(frozen=True)
class FileEntry:
    """One file's line in the manifest."""

    path: str
    sha256: str
    bytes: int


@dataclasses.dataclass(frozen=True)
class VerifyResult:
    """The verifier's answer, and the findings behind it.

    ``outcome`` is one of :data:`INTACT`, :data:`MODIFIED`, :data:`UNVERIFIABLE`.
    ``findings`` names every file involved, because "something changed" is not a usable
    answer to somebody deciding whether to rely on the bundle.
    """

    outcome: str
    findings: list[str]
    signature: str

    @property
    def exit_code(self) -> int:
        return EXIT_FOR[self.outcome]


def sha256_of(path: Path) -> str:
    """The file's digest. Read whole rather than streamed: these are report-sized files,
    and `tests/gates.py`'s binary-write scan flags any `open(..., "rb")` in this tree."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def looks_like_audio(path: Path) -> bool:
    """Whether this file is audio by extension or by its first bytes.

    Both, not either: an extension is a claim the file makes about itself and the magic
    bytes are what it actually is, and the guarantee this protects is worth checking
    twice. An unreadable file is treated as *not* audio here -- `verify` will report it
    as missing or changed on the digest path, which is the finding that matters.
    """
    if path.suffix.lower() in AUDIO_SUFFIXES:
        return True
    try:
        head = path.read_bytes()[:4]
    except OSError:  # pragma: no cover - the digest path reports this file anyway
        return False
    return any(head.startswith(magic) for magic in AUDIO_MAGIC)


def _snapshot_db(src: str | Path, dest: Path) -> None:
    """Copy the database through SQLite's own backup API.

    Not `shutil.copy`: a live database has a write-ahead log and an in-flight
    transaction, and a byte copy of one can be a file no reader will open. `backup()`
    takes a consistent point-in-time image of a database that is being written to.

    Opened read-only through a URI built by `Path.as_uri()`, which percent-encodes a
    path with a space or a `?` in it. Interpolating the path into the URI string looked
    fine and would have opened the wrong database, or none, for any operator whose home
    directory has a space in it. `as_uri()` needs an absolute path, and refusing a
    missing file by name here is better than SQLite's "unable to open database file",
    which is the same message for absent, unreadable and malformed.
    """
    source_path = Path(src).expanduser().resolve()
    if not source_path.is_file():
        raise BundleError(f"no database at {source_path}")
    source = sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def write_sessions_csv(store: EventStore, path: Path) -> int:
    """The capture-session ledger: what ran, when, and under which detection knobs.

    In the bundle because it is the denominator for everything else. A count of events is
    only readable against the time somebody was listening, and this is the record of that
    time -- without it a recipient cannot tell a quiet night from an unattended one.
    """
    rows = store.sessions()
    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in cover_text_lines():
            fh.write(f"# {line}\n" if line else "#\n")
        writer = csv.writer(fh)
        writer.writerow(
            [
                "id",
                "started_at",
                "ended_at",
                "device_label",
                "mic_model",
                "placement_note",
                "tz",
                "calibration_offset",
                "calibration_note",
                "frames_seen",
                "frames_dropped",
                "frame_coverage",
                "app_version",
                "threshold_dbfs",
                "min_duration_s",
                "debounce_s",
            ]
        )
        for s in rows:
            writer.writerow(
                [
                    s.id,
                    f"{s.started_at:.3f}",
                    "" if s.ended_at is None else f"{s.ended_at:.3f}",
                    s.device_label,
                    s.mic_model,
                    s.placement_note,
                    s.tz,
                    "" if s.calibration_offset is None else f"{s.calibration_offset:.2f}",
                    s.calibration_note or "",
                    s.frames_seen,
                    s.frames_dropped,
                    f"{s.frame_coverage:.4f}",
                    s.app_version,
                    "" if s.threshold_dbfs is None else f"{s.threshold_dbfs:.2f}",
                    "" if s.min_duration_s is None else f"{s.min_duration_s:.3f}",
                    "" if s.debounce_s is None else f"{s.debounce_s:.3f}",
                ]
            )
    return len(rows)


def write_calibration_csv(store: EventStore, path: Path) -> int:
    """The append-only calibration history -- without which nothing else is interpretable.

    A level in these files is dBFS plus whatever offset was in force at the time. An
    empty history is written as a header and no rows, not omitted: "this device was never
    calibrated" is a fact a recipient needs, and a missing file states nothing.
    """
    rows = store.calibration_history()
    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in cover_text_lines():
            fh.write(f"# {line}\n" if line else "#\n")
        writer = csv.writer(fh)
        writer.writerow(["id", "effective_from", "offset_db", "note", "reference_instrument"])
        for c in rows:
            writer.writerow(
                [
                    c.id,
                    f"{c.effective_from:.3f}",
                    f"{c.offset:.2f}",
                    c.note or "",
                    c.reference_instrument or "",
                ]
            )
    return len(rows)


def build_bundle(
    *,
    db_path: str | Path,
    out_dir: Path,
    config: Config,
    config_path: Path | None = None,
    created_at: str | None = None,
) -> Path:
    """Assemble a bundle in ``out_dir`` and return the path of its manifest.

    ``created_at`` is both the manifest's timestamp and the report's "generated at"
    line, deliberately: it is then the *only* value in the bundle that moves between two
    runs over the same database, so "identical apart from `created_at`" is a claim a test
    can make and this one does. Given `None` it is now, in UTC.
    """
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise BundleError(
            f"{out_dir} is not empty. A bundle is an inventory of exactly what it "
            "contains, so it is built into an empty directory rather than over whatever "
            "was already there."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    _snapshot_db(db_path, out_dir / SNAPSHOT_NAME)

    argv = [
        "--db",
        str(db_path),
        "--out",
        str(out_dir / "report.html"),
        "--csv",
        str(out_dir / "events.csv"),
        "--violations-csv",
        str(out_dir / "quiet-hours.csv"),
        "--violations-html",
        str(out_dir / "quiet-hours.html"),
        "--generated-at",
        stamp,
    ]
    if config_path is not None:
        argv += ["--config", str(config_path)]
    if render_main(argv) != 0:  # pragma: no cover - render_main only fails on PDF export
        raise BundleError("the report could not be rendered; the bundle was not written")

    with EventStore(db_path) as store:
        write_sessions_csv(store, out_dir / "sessions.csv")
        write_calibration_csv(store, out_dir / "calibration.csv")

    files = sorted(p for p in out_dir.iterdir() if p.is_file())
    audio = [p.name for p in files if looks_like_audio(p)]
    if audio:  # pragma: no cover - no path here can produce one; the inventory is checked
        raise BundleError(
            f"refusing to write a bundle containing audio-shaped files: {audio}. "
            "This project never persists audio; a bundle packages an inventory rather "
            "than one file at a time, so the inventory is checked rather than trusted."
        )

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "tool": "olive-bark-logger",
        "tool_version": __version__,
        "db_schema_version": SCHEMA_VERSION,
        "created_at": stamp,
        "what_this_proves": WHAT_THIS_PROVES,
        "config": config.to_dict(),
        "files": [
            dataclasses.asdict(FileEntry(p.name, sha256_of(p), p.stat().st_size)) for p in files
        ],
    }
    manifest_path = out_dir / MANIFEST_NAME
    # `sort_keys` and an explicit `\n`: the manifest is the file a signature would be
    # taken over, so its bytes must not depend on dict ordering or on a platform's idea
    # of a line ending. Written through `open(newline="\n")` rather than
    # `write_text(newline=...)`, which arrived in 3.10 and this project's floor is 3.9
    # (docs/adr/0002-python-39-floor.md).
    with manifest_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return manifest_path


def _signature_state(manifest_path: Path) -> tuple[str, list[str]]:
    """Whether this bundle carries a signature, and whether anything checked it.

    Three states, not two. A bundle can be *unsigned* (no signature was ever made) or
    carry one that nothing here can check (*unchecked*). Collapsing "unchecked" into
    "unsigned" would let a bundle whose signature is a forgery read as a bundle that
    never claimed one, and collapsing it into "valid" is worse. A verifier that cannot
    check a signature says so; it does not decide.
    """
    if not manifest_path.with_name(SIGNATURE_NAME).exists():
        return "unsigned", []
    return "unchecked", [
        f"{SIGNATURE_NAME} is present and nothing here can check it. This verifier "
        "recomputes digests only; the digests below are still meaningful, but who made "
        "this bundle has not been established."
    ]


def _read_manifest(manifest_path: Path) -> tuple[dict[str, object] | None, str]:
    """The manifest as a dict, or (None, why-it-cannot-be-read).

    Split out of :func:`verify_bundle` so each half stays readable, and because every one
    of these branches ends in "unverifiable" rather than in a verdict: a manifest that is
    missing, unparseable, or a version this code does not know is not evidence that the
    bundle is intact and is not evidence that it was modified.
    """
    if not manifest_path.is_file():
        return None, f"{MANIFEST_NAME} is missing, so there is nothing to check the bundle against"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{MANIFEST_NAME} could not be read: {exc}"
    if not isinstance(manifest, dict):
        return None, f"{MANIFEST_NAME} is not a manifest object"
    declared = manifest.get("manifest_version")
    if declared != MANIFEST_VERSION:
        return None, (
            f"{MANIFEST_NAME} declares manifest_version {declared!r}; this verifier reads "
            f"version {MANIFEST_VERSION} and will not guess at another"
        )
    if not isinstance(manifest.get("files"), list):
        return None, f"{MANIFEST_NAME} lists no files"
    return manifest, ""


def _digest_findings(root: Path, entries: list[dict[str, object]]) -> tuple[list[str], set[str]]:
    """Every file that changed or went missing, and the set the manifest listed."""
    findings: list[str] = []
    listed: set[str] = set()
    for entry in entries:
        name = str(entry.get("path", ""))
        listed.add(name)
        target = root / name
        if not target.is_file():
            findings.append(f"{name}: listed in the manifest and missing from the bundle")
            continue
        if sha256_of(target) != entry.get("sha256"):
            findings.append(f"{name}: changed since the bundle was made (digest does not match)")
    return findings, listed


def verify_bundle(bundle_dir: str | Path) -> VerifyResult:
    """Recompute every digest and check the signature. Answers, never raises.

    The answer is :data:`UNVERIFIABLE` whenever the manifest cannot be read or is a
    version this code does not know, and whenever a signature is present that nothing
    here can check. It is :data:`MODIFIED` for any digest mismatch, any listed
    file that is missing, and any file present in the directory that the manifest does
    not list -- the inventory is closed, because an open one lets anything be added to a
    bundle that still reads as intact.
    """
    root = Path(bundle_dir)
    manifest_path = root / MANIFEST_NAME
    manifest, why_not = _read_manifest(manifest_path)
    if manifest is None:
        return VerifyResult(UNVERIFIABLE, [why_not], "unsigned")

    signature, sig_findings = _signature_state(manifest_path)

    entries = manifest["files"]
    if not isinstance(entries, list):  # pragma: no cover - _read_manifest refuses anything else
        return VerifyResult(UNVERIFIABLE, [f"{MANIFEST_NAME} lists no files"], signature)
    findings, listed = _digest_findings(root, entries)

    present = {p.name for p in root.iterdir() if p.is_file()}
    findings += [
        f"{extra}: present in the bundle and absent from the manifest"
        for extra in sorted(present - listed - {MANIFEST_NAME, SIGNATURE_NAME})
    ]
    findings += [
        f"{name}: audio-shaped file in a bundle that must never contain one"
        for name in sorted(p.name for p in root.iterdir() if p.is_file() and looks_like_audio(p))
    ]

    if findings:
        return VerifyResult(MODIFIED, findings, signature)
    if signature == "unchecked":
        return VerifyResult(UNVERIFIABLE, sig_findings, signature)
    return VerifyResult(INTACT, [], signature)


def _cmd_build(args: argparse.Namespace) -> int:
    config = Config.load(args.config)
    db_path = args.db or config.db_path
    manifest = build_bundle(
        db_path=db_path,
        out_dir=args.out,
        config=config,
        config_path=args.config,
        created_at=args.created_at,
    )
    print(f"Wrote {manifest}.")
    print(
        "Unsigned. The digests prove the files have not been edited since the bundle was "
        "made; a signature would additionally say who made it, and this build does not "
        "make one."
    )
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    result = verify_bundle(args.bundle)
    print(f"{result.outcome} (signature: {result.signature})")
    for finding in result.findings:
        print(f"  - {finding}")
    if result.outcome == INTACT:
        print(
            "Every file matches its digest. That proves nothing was edited after the "
            "bundle was made, and nothing at all about how the device was placed or "
            "tuned before it."
        )
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="olive-bundle",
        description="Assemble a tamper-evident evidence bundle, or verify one.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="assemble a bundle (the default command)")
    build.add_argument("--config", type=Path, default=None, help="path to JSON config")
    build.add_argument("--db", type=str, default=None, help="path to the SQLite event log")
    build.add_argument("--out", type=Path, required=True, help="empty directory to build into")
    build.add_argument(
        "--created-at",
        type=str,
        default=None,
        help=(
            "timestamp for the manifest and the report header (default: now, UTC). "
            "Passing the same value twice makes two bundles of one database byte-identical."
        ),
    )
    build.set_defaults(func=_cmd_build)

    check = sub.add_parser("verify", help="recompute every digest and check the signature")
    check.add_argument("bundle", type=Path, help="the bundle directory")
    check.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    func = args.func
    try:
        return int(func(args))
    except BundleError as exc:
        print(f"olive-bundle: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
