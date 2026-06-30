# Methodology & Limitations

**Last verified: 2026-06-05 · Recheck cadence: per acoustics/detection change.**

This is the committed long-form version of the Methodology and Limitations sections that
every generated report carries. The report-content test (`tests/test_report_content.py`)
asserts the report contains these statements; this file is the canonical source.

## How a level is measured

- Audio is read in ~100 ms frames (default 1600 samples at 16 kHz). Each frame is reduced
  to one **RMS** value, converted to **dBFS** (`20·log10(rms)`, clamped at a −120 dBFS
  silence floor), and the frame is then discarded. See `monitor/level.py`.
- **dBFS is relative.** 0 dBFS is a full-scale signal. dBFS is *not* absolute sound
  pressure level (SPL, in dB) unless a calibration offset measured against a reference
  meter is applied. Uncalibrated readings are meaningful **relative to each other** on
  this device in this position — not as absolute loudness.

## How an event is detected

A noise event is recorded when the level stays **at or above the threshold** (default
−35 dBFS) for at least the **minimum duration** (default 0.4 s). Brief dips shorter than
the **debounce** window (default 1.0 s) do not split one event into several — a dog
pausing between barks stays one event. Peak and average level are computed over the loud
readings only. Stored per event: start, end, duration, peak level, average level, and an
optional coarse tag. Six numbers. No audio.

## Calibration

The calibration offset (dB) shifts relative dBFS toward approximate SPL when the device
has been compared against a reference meter. With offset 0.0 (the default) readings are
purely relative, and the report says so explicitly. Even calibrated, readings remain
estimates affected by mic quality, placement, and room acoustics.

## Detection validation

Detection is validated against a labeled session (`tests/test_eval.py`): a synthetic
session with known loud spans must yield the right number of events, each aligned to a
labeled span within one frame, with no false positives in a quiet session and nothing
detected when the threshold is set above the signal.

## Calendar heatmap

The report and the PWA render a **day × hour calendar heatmap**: each cell is the number
of events that *began* in that hour on that day. It visualizes the same level/event
metadata as the rest of the report — counts only, never audio. Accessibility is preserved:
the count is printed as text in every non-empty cell (meaning never depends on color
alone), the SVG carries `role="img"` and a summarizing `aria-label`, and an equivalent
data table repeats every number. It is a pattern view, not new evidence.

## Quiet-hours violation report

Quiet hours are configurable (`quiet_hours.start_hour` / `end_hour`, local time, wraps
midnight — default **22:00–08:00**; set them to your local ordinance, lease, or HOA rule).
`olive-report --violations-csv` / `--violations-html` (and the PWA's "Download quiet-hours
CSV") export an honest record for a neighbor, landlord, or HOA submission. Honesty rules
baked into the export:

- An event is attributed to quiet hours **by its start time** in the configured zone.
- The export lists **all** events with a within/outside flag — never only the flagged
  ones — so it cannot be a cherry-picked subset.
- "Within quiet hours" means only that *this device measured a level above the threshold
  starting during the window*. It is **not** proof of the source of a sound or of who
  caused it. The no-source and relative-dBFS limitations below are reproduced verbatim in
  every exported violation report.

## Limitations (what this cannot prove)

1. **Relative, not absolute.** Without calibration, the numbers are relative dBFS, not
   SPL in dB. Treat them as relative.
2. **No source attribution.** The tool measures levels only. It **cannot prove what made
   a sound or where it came from**, and it does not record or identify any voice or
   source. An event is "sound crossed a threshold here", not "Olive barked".
3. **Placement-dependent.** Microphone placement and room acoustics affect every reading.
   An event count reflects this device in this spot, not an absolute fact about the
   building. Move the device → re-validate and re-calibrate.
4. **Informational, not adversarial.** These numbers are offered to understand and
   communicate a real pattern, never to manufacture or cherry-pick a case.
