"""`olive-bundle`: a tamper-evident evidence bundle, and the verifier that reads it.

The research roadmap's E1 is the item every adjudicator persona raised — a property
manager or a board will not weigh a log the other party could have edited — and
`docs/audits/residual-risk.md` row 1 accepts tampering as unmitigated. What makes a
manifest worth having is not that it exists but that it **fails**, so most of what is
below is a bundle being broken in a specific way and the verifier being required to
notice and to say which file.

Three properties here are load-bearing rather than nice to have.

**The three answers are three.** `unverifiable` is a real answer and never a polite form
of either of the others: a bundle whose manifest is gone has not been shown to be intact
and has not been shown to be modified, and a verifier that resolves that ambiguity in
either direction is worse than no verifier. This is the project's dominant defect class —
absence rendered as a value — in the one artifact built to be handed to somebody who
does not trust the sender.

**The inventory is closed.** A file *added* to a bundle is a finding, not only a file
changed. An open inventory lets anything be dropped into a bundle that still reads as
intact, which is most of the point of having one.

**Two bundles of one database are byte-identical apart from `created_at`.** That is
testable only because `created_at` is also the report's "generated at" line, so there is
exactly one moving value rather than several.

No assertion below is pinned to a length or an offset of a rendered artifact. A control
anchored to "the report is exactly N bytes" stops firing the moment an unrelated section
is added, and reads as a pass while it does.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest
from monitor.config import Config
from monitor.detector import Event
from report.bundle import (
    INTACT,
    MANIFEST_NAME,
    MANIFEST_VERSION,
    MODIFIED,
    SIGNATURE_NAME,
    SNAPSHOT_NAME,
    UNVERIFIABLE,
    WHAT_THIS_PROVES,
    BundleError,
    build_bundle,
    looks_like_audio,
    main,
    verify_bundle,
)
from report.render import ERASED_HEADING, cover_text_lines
from store import ERASED_REASON, EventStore

STAMP = "2026-03-11T00:00:00+00:00"
DAY = datetime(2026, 3, 10, tzinfo=timezone.utc)


def _at(day_offset: int, hour: int) -> float:
    return DAY.timestamp() + day_offset * 86400 + hour * 3600


@pytest.fixture()
def db(tmp_path):
    """A small but complete log: one session, two events, one recorded gap."""
    path = tmp_path / "olive.db"
    with EventStore(path) as store:
        sid = store.start_session(
            started_at=_at(0, 20),
            device_label="pi-1",
            mic_model="USB mic",
            placement_note="by the wall",
            tz="UTC",
            calibration_offset=0.0,
            calibration_note="uncalibrated",
            app_version="0.1.0",
        )
        store.add_event(Event(_at(0, 22), _at(0, 22) + 6, 6.0, -9.0, -14.0), session_id=sid)
        store.add_event(Event(_at(0, 23), _at(0, 23) + 3, 3.0, -12.0, -18.0), session_id=sid)
        store.add_gap(_at(0, 21), _at(0, 21) + 300, "device-error", session_id=sid)
        store.update_session(sid, frames_seen=1000, frames_dropped=0, ended_at=_at(1, 6))
    return path


def _build(db_path, out, *, created_at=STAMP):
    return build_bundle(
        db_path=db_path,
        out_dir=out,
        config=Config(db_path=str(db_path), tz="UTC"),
        created_at=created_at,
    )


# --- what a bundle contains -----------------------------------------------------------


def test_a_bundle_carries_the_evidence_and_the_ledgers_that_make_it_readable(db, tmp_path):
    manifest_path = _build(db, tmp_path / "bundle")
    names = {p.name for p in (tmp_path / "bundle").iterdir()}
    assert names == {
        SNAPSHOT_NAME,
        "report.html",
        "events.csv",
        "quiet-hours.csv",
        "quiet-hours.html",
        "sessions.csv",
        "calibration.csv",
        MANIFEST_NAME,
    }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == MANIFEST_VERSION
    # The digest of every file except the manifest itself, which cannot hash itself.
    assert {e["path"] for e in manifest["files"]} == names - {MANIFEST_NAME}
    assert all(len(e["sha256"]) == 64 for e in manifest["files"])
    assert manifest["config"]["tz"] == "UTC"


def test_the_manifest_says_what_a_hash_cannot_prove(db, tmp_path):
    """The over-promise `docs/RESEARCH-ROADMAP.md` flags, refused in the manifest itself
    rather than in a README the recipient never sees."""
    manifest = json.loads(_build(db, tmp_path / "bundle").read_text(encoding="utf-8"))
    assert manifest["what_this_proves"] == WHAT_THIS_PROVES
    blob = " ".join(WHAT_THIS_PROVES)
    assert "cannot prove that the device was placed honestly" in blob
    assert "not quiet hours" in blob
    assert "a measurement, not a determination" in blob


def test_the_two_ledgers_carry_the_cover_block_like_every_other_export(db, tmp_path):
    """`sessions.csv` and `calibration.csv` are handed to a person like any other export.
    `tests/test_export_caveats.py` discovers them from source; this checks the bytes."""
    root = tmp_path / "bundle"
    _build(db, root)
    for name in ("sessions.csv", "calibration.csv"):
        text = (root / name).read_text(encoding="utf-8")
        for line in cover_text_lines():
            assert (f"# {line}" if line else "#") in text, f"{name} ships without: {line[:50]}"
        rows = [ln for ln in text.splitlines() if not ln.startswith("#")]
        assert rows[0].split(",")[0] == "id", f"{name}'s data rows must still parse"


def test_an_empty_calibration_history_is_a_header_and_no_rows_not_a_missing_file(tmp_path):
    """ "This device was never calibrated" is a fact the recipient needs. A missing file
    states nothing, and nothing is the one thing this project will not hand over."""
    path = tmp_path / "olive.db"
    with EventStore(path) as store:
        store.add_event(Event(_at(0, 22), _at(0, 22) + 6, 6.0, -9.0, -14.0))
    root = tmp_path / "bundle"
    _build(path, root)
    rows = [
        ln
        for ln in (root / "calibration.csv").read_text(encoding="utf-8").splitlines()
        if not ln.startswith("#")
    ]
    assert rows[0].startswith("id,effective_from,offset_db")
    assert len(rows) == 1


def test_a_bundle_refuses_to_be_built_over_an_existing_one(db, tmp_path):
    root = tmp_path / "bundle"
    _build(db, root)
    with pytest.raises(BundleError, match="not empty"):
        _build(db, root)


def test_a_missing_database_is_refused_by_name(tmp_path):
    """SQLite answers "unable to open database file" for absent, unreadable and malformed
    alike. Naming the path is the difference between a typo and a corrupt log."""
    with pytest.raises(BundleError, match="no database at"):
        _build(tmp_path / "nowhere.db", tmp_path / "bundle")


# --- determinism ----------------------------------------------------------------------


def test_two_bundles_of_one_database_are_identical_apart_from_created_at(db, tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    _build(db, first)
    _build(db, second)
    for p in sorted(first.iterdir()):
        assert p.read_bytes() == (second / p.name).read_bytes(), f"{p.name} is not reproducible"

    later = tmp_path / "c"
    _build(db, later, created_at="2026-03-12T00:00:00+00:00")
    # Only the files that carry the timestamp may move, and they must all still verify.
    moved = {
        p.name for p in sorted(first.iterdir()) if p.read_bytes() != (later / p.name).read_bytes()
    }
    assert moved == {MANIFEST_NAME, "report.html", "quiet-hours.html"}
    assert verify_bundle(later).outcome == INTACT


# --- the verifier -------------------------------------------------------------------


def test_an_untouched_bundle_is_intact(db, tmp_path):
    root = tmp_path / "bundle"
    _build(db, root)
    result = verify_bundle(root)
    assert result.outcome == INTACT
    assert result.findings == []
    assert result.signature == "unsigned"
    assert result.exit_code == 0


def test_one_edited_byte_is_reported_and_the_file_is_named(db, tmp_path):
    """The edit is **length-preserving**, deliberately.

    Appending a byte would also be caught by comparing `st_size` against the manifest's
    `bytes` field, so a test that appends cannot tell a digest check from a size check --
    and a size check is the plausible wrong version of this, because it is faster and
    looks equivalent. Rewriting one character in place is caught only by the digest.
    """
    root = tmp_path / "bundle"
    _build(db, root)
    target = root / "events.csv"
    original = target.read_bytes()
    edited = original[:-1] + bytes([original[-1] ^ 0x01])
    target.write_bytes(edited)
    assert len(edited) == len(original), "the control only works if the length is unchanged"
    result = verify_bundle(root)
    assert result.outcome == MODIFIED
    assert result.exit_code == 1
    assert any("events.csv" in f and "changed" in f for f in result.findings), result.findings


def test_a_deleted_file_is_reported_as_missing_not_as_intact(db, tmp_path):
    root = tmp_path / "bundle"
    _build(db, root)
    (root / "quiet-hours.csv").unlink()
    result = verify_bundle(root)
    assert result.outcome == MODIFIED
    assert any("quiet-hours.csv" in f and "missing" in f for f in result.findings)


def test_a_file_added_to_a_bundle_is_a_finding_because_the_inventory_is_closed(db, tmp_path):
    """An open inventory would let anything be dropped into a bundle that still read as
    intact, which is most of the point of having one."""
    root = tmp_path / "bundle"
    _build(db, root)
    (root / "note-from-the-sender.txt").write_text("trust me", encoding="utf-8")
    result = verify_bundle(root)
    assert result.outcome == MODIFIED
    assert any(
        "note-from-the-sender.txt" in f and "absent from the manifest" in f for f in result.findings
    ), result.findings


def test_a_bundle_with_no_manifest_is_unverifiable_never_intact(db, tmp_path):
    root = tmp_path / "bundle"
    _build(db, root)
    (root / MANIFEST_NAME).unlink()
    result = verify_bundle(root)
    assert result.outcome == UNVERIFIABLE
    assert result.exit_code == 2
    assert "nothing to check the bundle against" in result.findings[0]


def test_an_unreadable_manifest_is_unverifiable(db, tmp_path):
    root = tmp_path / "bundle"
    _build(db, root)
    (root / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    assert verify_bundle(root).outcome == UNVERIFIABLE


def test_a_manifest_version_this_verifier_does_not_know_is_unverifiable(db, tmp_path):
    """The case where a confident "intact" is worst: a newer format read by older code,
    which would check the fields it happens to recognise and ignore the rest."""
    root = tmp_path / "bundle"
    manifest_path = _build(db, root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manifest_version"] = MANIFEST_VERSION + 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = verify_bundle(root)
    assert result.outcome == UNVERIFIABLE
    assert "will not guess" in result.findings[0]


def test_a_signature_nothing_can_check_is_unverifiable_not_intact(db, tmp_path):
    """This build makes no signatures, and a bundle that carries one from elsewhere must
    not be answered as though it never claimed one. Treating "unchecked" as "unsigned"
    would let a forged signature read as an honest bundle with no signature at all."""
    root = tmp_path / "bundle"
    _build(db, root)
    (root / SIGNATURE_NAME).write_text("-----BEGIN SSH SIGNATURE-----\n", encoding="utf-8")
    result = verify_bundle(root)
    assert result.outcome == UNVERIFIABLE
    assert result.signature == "unchecked"
    assert any("nothing here can check it" in f for f in result.findings)
    # And the signature file itself is not reported as an unlisted extra: it is not part
    # of the inventory, it is the thing taken over the inventory.
    assert not any("absent from the manifest" in f for f in result.findings)


# --- the no-audio guarantee, at the inventory level ----------------------------------


def test_an_audio_shaped_file_in_a_bundle_is_a_finding(db, tmp_path):
    """The project's central guarantee is that no audio is ever persisted. A bundle is
    the one artifact that packages files by inventory rather than one at a time, so the
    inventory is checked rather than trusted."""
    root = tmp_path / "bundle"
    _build(db, root)
    (root / "evidence.wav").write_bytes(b"RIFF....WAVEfmt ")
    result = verify_bundle(root)
    assert result.outcome == MODIFIED
    assert any("evidence.wav" in f and "audio-shaped" in f for f in result.findings)


def test_audio_is_recognised_by_its_bytes_as_well_as_its_name(tmp_path):
    """An extension is a claim the file makes about itself; the magic bytes are what it
    is. Renaming a WAV to `.csv` must not get it past this."""
    renamed = tmp_path / "definitely-not-audio.csv"
    renamed.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    assert looks_like_audio(renamed)
    named = tmp_path / "empty.mp3"
    named.write_bytes(b"")
    assert looks_like_audio(named)
    innocent = tmp_path / "rows.csv"
    innocent.write_text("id,value\n1,2\n", encoding="utf-8")
    assert not looks_like_audio(innocent)


# --- the CLI --------------------------------------------------------------------------


def test_the_cli_builds_then_verifies_and_exits_zero(db, tmp_path, capsys):
    out = tmp_path / "bundle"
    assert main(["build", "--db", str(db), "--out", str(out), "--created-at", STAMP]) == 0
    assert main(["verify", str(out)]) == 0
    printed = capsys.readouterr().out
    assert INTACT in printed
    assert "nothing at all about how the device was placed" in printed


def test_the_cli_exit_code_distinguishes_modified_from_unverifiable(db, tmp_path):
    out = tmp_path / "bundle"
    main(["build", "--db", str(db), "--out", str(out), "--created-at", STAMP])
    (out / "report.html").write_text("<html>edited</html>", encoding="utf-8")
    assert main(["verify", str(out)]) == 1
    (out / MANIFEST_NAME).unlink()
    assert main(["verify", str(out)]) == 2


def test_the_cli_with_no_subcommand_prints_help_and_does_not_exit_zero(capsys):
    """A tool that exits 0 having done nothing is a gate that cannot fail, in miniature."""
    assert main([]) == 2
    assert "olive-bundle" in capsys.readouterr().out


# --- an erasure survives into the bundle ---------------------------------------------


def test_an_erased_window_reaches_the_bundle_as_an_erasure_not_as_a_quiet_night(db, tmp_path):
    """Issue #106's remaining criterion, for the bundle half of it.

    `olive-forget` deletes the measurements in a window and leaves a `gaps` row with
    reason `erased` behind, and the whole design rests on every downstream reader
    understanding that row. A bundle is the furthest downstream reader there is -- the
    artifact handed to somebody who does not trust the sender -- so the erasure has to
    survive the snapshot, the report and the coverage arithmetic, all three.

    The sharpest half of this is the last one. An erased night that reached the bundle as
    a *report section* but not as unmonitored *time* would read as a quiet night to
    anyone who looked at the numbers rather than the prose, which is precisely what
    erasure is not allowed to look like.
    """
    with EventStore(db) as store:
        result = store.forget(start=_at(0, 22), end=_at(0, 23) + 600, reason="a guest")
    assert result.events == 2, "the fixture must actually have something to erase"

    root = tmp_path / "bundle"
    _build(db, root)
    assert verify_bundle(root).outcome == INTACT

    # 1. The snapshot carries the disclosure, not just the hole.
    snapshot = sqlite3.connect(root / SNAPSHOT_NAME)
    try:
        rows = snapshot.execute("SELECT reason, note FROM gaps WHERE reason = ?", (ERASED_REASON,))
        erased = rows.fetchall()
        remaining = snapshot.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        snapshot.close()
    assert erased == [(ERASED_REASON, "a guest")]
    assert remaining == 0, "the erased measurements must be gone from the snapshot too"

    # 2. The bundled report names the window and the operator's reason.
    report = (root / "report.html").read_text(encoding="utf-8")
    assert ERASED_HEADING in report
    assert "a guest" in report

    # 3. And the arithmetic agrees with the prose: those hours are not monitored, and the
    #    quiet-hours export says so rather than reporting a quiet night.
    quiet_hours = (root / "quiet-hours.csv").read_text(encoding="utf-8")
    assert "not monitored" in quiet_hours
    data = [ln for ln in quiet_hours.splitlines() if not ln.startswith("#")]
    assert len(data) == 1, f"every event was erased, so only the header may remain: {data}"
