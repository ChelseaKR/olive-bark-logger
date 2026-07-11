"""Generate a demo event log and render report.html, so `make report` always works.

Uses the synthetic session (no hardware, no audio) to populate a throwaway database,
then renders the real report. Handy for eyeballing the output and for `make a11y`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor.capture import LoudRegion, synthetic_session  # noqa: E402
from monitor.config import Config  # noqa: E402
from monitor.service import run_pipeline  # noqa: E402
from report.render import generate_report_from_db  # noqa: E402
from store import EventStore  # noqa: E402

DB = ROOT / "demo.db"
OUT = ROOT / "report.html"

if DB.exists():
    DB.unlink()

config = Config(
    db_path=str(DB),
    tagging=True,
    device_label="demo-pi",
    mic_model="USB mic (demo)",
    placement_note="Demo: synthetic session, no real microphone.",
)
labels = [
    LoudRegion(2.0, 6.0, 0.30),
    LoudRegion(20.0, 23.0, 0.45),
    LoudRegion(40.0, 41.0, 0.20),
]
with EventStore(DB) as store:
    store.add_calibration(config.calibration_offset, config.calibration_note, effective_from=0.0)
    sid = store.start_session(
        started_at=0.0,
        device_label=config.device_label,
        mic_model=config.mic_model,
        placement_note=config.placement_note,
        tz=config.tz,
        calibration_offset=config.calibration_offset,
        calibration_note=config.calibration_note,
        app_version="0.1.0",
    )
    events = list(
        run_pipeline(
            synthetic_session(60.0, labels, frame_size=config.frame_size),
            config,
            store,
            session_id=sid,
        )
    )
    store.update_session(sid, frames_seen=600, frames_dropped=0, ended_at=60.0)

html = generate_report_from_db(str(DB), config, generated_at="(demo) 2026-01-01 12:00 UTC")
OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes) from demo session.")
