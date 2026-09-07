"""`olive-forget` -- erase a time range and leave the erasure disclosed.

A privacy-first tool needs a privacy verb. A guest's visit, a family argument, a
medical episode: an operator may reasonably not want any trace of a window in a file
they are about to hand to a landlord. Before this the only two options were to keep it
or to edit the SQLite file by hand, and the second destroys the record's honesty in
silence, which is the thing this project exists not to do.

So erasure is an operation, not an edit, and what it leaves behind is a `gaps` row with
reason `erased`. Every reader that already understands "the device was not listening
here" understands that with no new arithmetic: the coverage figures subtract it, the
calendar hatches it, the CSV's `monitored` column reads `no` beside it. An erased night
therefore reads as *not monitored*, never as quiet, which is the only way erasure can
coexist with a report that is handed to somebody as evidence.

Two things this command does that a `DELETE` would not:

* it asks first, printing the counts and the window in the operator's own time zone,
  and needs `--yes` or a typed confirmation before it removes anything;
* it writes the disclosure in the same transaction as the deletes, so a crash cannot
  leave the hole without the row that discloses it.

`--dry-run` prints the same counts and changes nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, tzinfo
from pathlib import Path

from monitor import __version__
from monitor.config import Config

from store.db import EventStore, ForgetResult

#: What the operator must type when they have not passed `--yes`. A bare "y" is too
#: close to a keystroke to stand for a deletion that cannot be undone.
CONFIRMATION = "erase"


class TimestampError(ValueError):
    """A `--from` or `--to` value that cannot be read as a moment."""


def parse_moment(text: str, tz: tzinfo) -> float:
    """Read a timestamp as unix seconds, refusing rather than guessing.

    Accepts an ISO 8601 datetime (`2026-09-06T21:00`, `2026-09-06 21:00:00`, or one
    with an explicit offset) and a bare unix number. A naive ISO value is read in the
    configured zone, which is the zone the report and the quiet-hours window already
    use, so an operator naming "last night" gets the night they mean.

    It does not accept a bare date, and refusing that takes an explicit check rather
    than falling out of the parser: `datetime.fromisoformat("2026-09-06")` succeeds and
    returns midnight. Accepting it would silently round the operator's window outward to
    a whole day and erase more than they asked for, while looking like a convenience. A
    value with no time of day in it is therefore refused by name.
    """
    raw = text.strip()
    try:
        return float(raw)
    except ValueError:
        pass
    if ":" not in raw:
        raise TimestampError(
            f"{text!r} names a day, not a moment. Give a time of day too "
            "(2026-09-06T00:00 to 2026-09-07T00:00 for a whole day), so the window "
            "erased is the one you meant."
        )
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TimestampError(
            f"cannot read {text!r} as a moment. Use an ISO 8601 date and time "
            "(2026-09-06T21:00), optionally with an offset, or a unix timestamp."
        ) from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    return moment.timestamp()


def _fmt(moment: float, tz: tzinfo) -> str:
    return datetime.fromtimestamp(moment, tz=tz).strftime("%Y-%m-%d %H:%M:%S %Z")


def describe(result: ForgetResult, tz: tzinfo) -> list[str]:
    """The operator-facing lines for one erasure or dry run.

    Every table is named with its count, including the zeros. A summary that printed
    only the non-empty rows would let a window that removed nothing read the same as
    one that removed everything but the ambient ledger.
    """
    lines = [
        f"Window: {_fmt(result.start, tz)} to {_fmt(result.end, tz)}",
        f"Reason: {result.reason or 'no reason given'}",
    ]
    lines += [f"  {table:<18} {count}" for table, count in result.as_dict().items()]
    lines.append(f"  {'total rows':<18} {result.total}")
    return lines


def _confirm() -> bool:
    """Ask, and accept only the exact word. Erasure cannot be undone."""
    reply = input(f"Type {CONFIRMATION!r} to erase this window, or anything else to stop: ")
    return reply.strip() == CONFIRMATION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="olive-forget",
        description=(
            "Erase every measurement in a time range and record the erasure as a "
            "disclosed gap. The window is reported as not monitored, never as quiet."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, default=None, help="path to JSON config")
    parser.add_argument("--db", type=str, default=None, help="path to SQLite event log")
    parser.add_argument(
        "--from",
        dest="start",
        required=True,
        help="start of the window: ISO 8601 datetime (read in the configured zone if "
        "it carries no offset) or a unix timestamp",
    )
    parser.add_argument(
        "--to",
        dest="end",
        required=True,
        help="end of the window, exclusive; same formats as --from",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help=(
            "short note recorded with the erasure and shown in the report. Optional; "
            "the report says 'no reason given' rather than nothing when it is omitted."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be removed and change nothing",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the typed confirmation (for scripts; erasure cannot be undone)",
    )
    args = parser.parse_args(argv)

    config = Config.load(args.config)
    tz = config.tzinfo()
    db_path = args.db or config.db_path

    try:
        start = parse_moment(args.start, tz)
        end = parse_moment(args.end, tz)
    except TimestampError as exc:
        print(f"olive-forget: {exc}", file=sys.stderr)
        return 2
    if not end > start:
        print(
            f"olive-forget: --to must be after --from ({args.start!r} to {args.end!r})",
            file=sys.stderr,
        )
        return 2

    with EventStore(db_path) as store:
        preview = store.forget(start=start, end=end, reason=args.reason, dry_run=True)
        header = "Would erase:" if args.dry_run else "About to erase:"
        print(header)
        for line in describe(preview, tz):
            print(line)
        if args.dry_run:
            print("Dry run: nothing was changed.")
            return 0
        if not args.yes and not _confirm():
            print("Stopped. Nothing was changed.")
            return 1
        result = store.forget(start=start, end=end, reason=args.reason)

    print(f"Erased {result.total} row(s).")
    print(
        f"Recorded gap #{result.gap_id}: this window now reports as not monitored, "
        "in the report, the status page and every export."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
