// Aggregation, accessible-report HTML, and CSV for the PWA. Parallels report/*.py:
// same honest methodology + limitations, same "no audio" guarantee, data tables for a11y.
//
// The caveats are not optional and they are not the Python side's alone. This is the
// zero-hardware route into the same task — no Raspberry Pi, no install, no command line —
// and it exports the same kind of file to hand to a landlord. The path with the lowest
// barrier to reaching for it must not be the path that ships without its limits. Every
// export path below therefore carries the "what this can and cannot prove" cover block, and
// anything that reports a quiet-hours count also carries the no-verdict line. The exact
// strings live in spec/report/cover.json and are replayed against both implementations
// (pwa/report.test.mjs here, tests/test_export_caveats.py on the Python side), the same
// way spec/detector/*.json keeps the two detectors from drifting.

export const RELATIVE_DBFS_NOTE =
  "Levels are measured in dBFS, which is relative to digital full scale, not absolute " +
  "sound pressure level (SPL) in dB. Without calibration against a reference meter, " +
  "treat the numbers as relative, not absolute.";
// What a peak or duration figure reads when there were no events to take it from.
export const NO_EVENTS_VALUE = "no events";

// The calendar's third state, in words. The same string report/charts.py renders as
// _UNMON_LABEL: two implementations of one report describing the same absence must not
// describe it with two different words, so this is a constant on both sides rather than
// a literal typed twice.
export const UNMONITORED_LABEL = "not monitored";

export const NO_SOURCE_NOTE =
  "This tool measures sound levels only. It cannot prove what made a sound or where it " +
  "came from; it does not record or identify any voice or source.";

// R1 — the plain-language cover block, verbatim from report/render.py.
export const COVER_HEADING = "What this can and cannot prove";
export const COVER_CAN = [
  "When sound at this device crossed a set loudness threshold, and for how long, with " +
    "timestamps — an honest, time-stamped record of the pattern.",
  "How that pattern lines up with a quiet-hours window you configure.",
];
export const COVER_CANNOT = [
  "What made a sound, or who caused it — no audio is recorded, so there is no source " +
    "attribution.",
  "Absolute loudness in dB SPL or dB(A): uncalibrated readings are relative dBFS, not " +
    "the units an ordinance, lease, or HOA rule is written in.",
  "That any law, lease, or rule was broken — only the relevant authority decides that, " +
    "and being within quiet hours is not the same as a violation.",
  "Anything about a place this device was not in — readings are specific to this " +
    "microphone in this spot, and change if it moves.",
];
export const COVER_PRIVACY =
  "By design no audio is ever recorded, stored, or transmitted, so there is nothing to " +
  "leak, subpoena, or misuse. This is general information, not legal advice; verify your " +
  "local rule before relying on these numbers.";

// R3 — a quiet-hours count is a measurement, never a finding.
export const NO_VERDICT_NOTE =
  "This is a measurement, not a determination. Being within quiet hours is not the same " +
  "as a violation, and only the relevant authority can decide whether a rule was broken.";

// --- Erasure, disclosed ---------------------------------------------------------------
//
// The browser half of `olive-forget` (issue #106). The Python side's rule is that erasure
// is an operation and not an edit: what it leaves behind is a gap, so every reader that
// already understands "the app was not listening here" understands an erasure with no new
// arithmetic — coverage subtracts it, the calendar hatches it, and an erased night can
// never read as a quiet one.
//
// Before this the page's only way to remove anything was "Clear events", which emptied the
// whole object store — events, gaps and session records alike — and left nothing at all
// behind. That is exactly the hand-edit of the SQLite file that `olive-forget` exists so
// nobody has to make: the record loses its hours and loses the fact that it ever had them.
//
// The heading is verbatim from report/render.py. The note is not, and deliberately: the
// Python one names `olive-forget`, a command this page has no access to, and says "the
// device", which here is a browser tab. Copying it verbatim would be a false statement
// about how the erasure happened, which is a strange way to be faithful to a disclosure.
// Its last two sentences are the claims that must not vary between the two documents and
// are pinned across implementations in pwa/report.test.mjs.
export const ERASED_HEADING = "Windows erased by the operator";
export const ERASED_NOTE =
  "The operator erased the periods below from this browser's log, so every measurement " +
  "inside them was deleted. They are reported here, and counted as not monitored in the " +
  "coverage figures and the calendar, exactly as a period the app was not listening is. " +
  "What was erased cannot be recovered from this file, and this disclosure is the only " +
  "record that it existed. A report with no such section had nothing erased from it.";

//: The `reason` an erasure carries on its gap record. A gap with no reason is an ordinary
//: coverage hole — a backgrounded tab or a locked device — and the two must not be
//: rendered with one explanation between them.
export const ERASED_REASON = "erased";

//: What an erasure with no operator note reads as. Not an empty cell: an erasure the
//: operator gave no reason for and one whose reason was dropped between the store and the
//: page must not render the same way.
export const NO_REASON_GIVEN = "no reason given";

// R2 — the browser edition has no calibration step at all, so it is always uncalibrated.
export const UNCALIBRATED_HEADLINE =
  "Uncalibrated — these readings are relative, not dB(A).";
export const UNCALIBRATED_NOTE =
  "This browser edition has no calibration step, so its readings are always relative " +
  "dBFS, never absolute sound level in dB(A) or dB SPL. Do not read them as the decibel " +
  "numbers an ordinance or lease specifies; only their pattern relative to each other on " +
  "this device is meaningful.";

// The cover as plain-text lines, for the leading "#" comment preamble of a CSV export —
// the same shape report/render.py's cover_text_lines() writes, so the caveat travels
// with a file that gets downloaded and emailed on.
export function coverTextLines() {
  return [
    COVER_HEADING,
    "",
    "What it can show:",
    ...COVER_CAN.map((x) => `  - ${x}`),
    "",
    "What it cannot prove:",
    ...COVER_CANNOT.map((x) => `  - ${x}`),
    "",
    COVER_PRIVACY,
  ];
}

// Every CSV this module writes starts with the cover. Exported so a new export path
// cannot quietly skip it, and so the gate can prove each path went through here.
export function csvPreamble(extraLines = []) {
  const lines = [...coverTextLines(), ...(extraLines.length ? ["", ...extraLines] : [])];
  return lines.map((line) => (line ? `# ${line}` : "#")).join("\n");
}

// Monitoring gaps, stated in the preamble of an export. A gap removes events, so an
// unmonitored stretch would otherwise read as a quiet one. Said either way: "none
// recorded" is information, silence is not.
export function gapPreambleLines(gaps) {
  if (!gaps || !gaps.length) {
    return [
      "Monitoring gaps: none recorded. The browser cannot monitor while the tab is " +
        "backgrounded or the device is locked; interruptions it noticed are listed here. " +
        "One it never got to record cannot appear, so treat this as an upper bound on " +
        "how much was observed.",
    ];
  }
  let seconds = 0;
  for (const g of gaps) seconds += Math.max(0, (g.end || 0) - (g.start || 0));
  const lines = [
    `Monitoring gaps: ${gaps.length} recorded, totalling ${Math.round(seconds)}s, during ` +
      "which no event could be detected. These periods are absences of data, not silence: " +
      "the absence of an event in them is not evidence that no sound occurred.",
    "",
  ];
  for (const g of gaps) {
    lines.push(
      `  - ${new Date(g.start * 1000).toISOString()} to ${new Date(g.end * 1000).toISOString()} ` +
        // Every line says why. Without it an erased window travels in a CSV preamble under
        // the sentence above it -- "the browser cannot monitor while the tab is
        // backgrounded" -- which is a reason, and the wrong one.
        `(${Math.round(Math.max(0, g.end - g.start))}s, ${gapReason(g)})`,
    );
  }
  return lines;
}

// --- Monitoring coverage: how much of the window was actually observed ---------------
//
// Issue #39 established, for the Python side, that a quiet-hours document is only honest
// if it says how much of the window it observed: an outage during quiet hours removes
// events, so a monitor that dropped out for most of the night produces a low count that
// reads as a quiet night. `report/violations.py` carries monitored-vs-wall-clock hours
// and a mandatory banner. The browser edition -- which pwa/README.md offers for the same
// "honest ... submission" -- shipped a gap total with no denominator: "37s of gap" that
// a reader cannot place against a 30-minute test run or a 10-hour night (issue #64).
//
// It could not have done better before now: there was nothing to compute a figure from.
// The store held events and gap records only, and a gap is written by the *running* app
// on a visibilitychange, so the most ordinary outage of all -- the tab closed, the
// browser restarted, the laptop shut -- left no trace whatsoever. Session records
// (pwa/app.js) are what changed; this is the arithmetic over them, ported from
// report/render.py's _coverage_window / on_air_spans / _coverage_hours so the two
// implementations answer the same question the same way.
//
// The exact strings live in spec/report/cover.json, replayed by both test suites.

export const COVERAGE_HEADING = "Monitoring coverage";

export const COVERAGE_ABSENCE_NOTE =
  "Hours that were not monitored are not quiet hours: no event could be recorded then, " +
  "so the absence of an event in those hours is not evidence that no sound occurred.";

export const COVERAGE_UNKNOWN_NOTE =
  "How much of this window the device actually monitored could not be determined from " +
  "this record: it carries no monitoring session, no recorded gap, and no measurable " +
  "span of events. Do not read the counts below as covering the whole window.";

// Said whether or not the figure is good news, and said in the browser's own terms: the
// upper-bound caveat is stronger here than on the Pi, because a tab can be killed
// between checkpoints and a session's last seconds go unrecorded.
export const COVERAGE_UPPER_BOUND_CAVEAT =
  "Coverage is measured from what the record contains. Time with no run in progress is " +
  "subtracted from the session record, and interruptions the app noticed are subtracted " +
  "as gaps, but an interruption it never got to write down cannot appear here -- a tab " +
  "killed outright ends its run at the last checkpoint, not at the true moment. Treat " +
  "these figures as an upper bound on how much was observed.";

const NOT_MONITORED_IS_NOT_QUIET =
  "Time outside a monitoring run is reported as not monitored, never as quiet.";

// -- span arithmetic (unix seconds; identical shape to report/render.py's helpers) -----

function clipSpans(spans, [winStart, winEnd]) {
  const out = [];
  for (const [s, e] of spans) {
    const start = Math.max(s, winStart);
    const end = Math.min(e, winEnd);
    if (end > start) out.push([start, end]);
  }
  return mergeSpans(out);
}

function mergeSpans(spans) {
  const sorted = [...spans].sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of sorted) {
    const last = merged[merged.length - 1];
    if (last && s <= last[1]) last[1] = Math.max(last[1], e);
    else merged.push([s, e]);
  }
  return merged;
}

function subtractSpans(spans, holes) {
  let out = spans.map((s) => [...s]);
  for (const [hs, he] of holes) {
    const next = [];
    for (const [s, e] of out) {
      if (he <= s || hs >= e) next.push([s, e]);
      else {
        if (s < hs) next.push([s, hs]);
        if (he < e) next.push([he, e]);
      }
    }
    out = next;
  }
  return out;
}

const spanSeconds = (spans) => spans.reduce((acc, [s, e]) => acc + Math.max(0, e - s), 0);

/**
 * The observed reporting span, as [start, end] unix seconds, or null.
 *
 * Earliest observed moment to latest, across events, gaps AND every session -- not the
 * most recent session, or a record whose app was restarted would report a window
 * starting at whichever event happened to come first. One definition of "the window", so
 * the report and the CSV cannot disagree about what they are covering.
 */
export function coverageWindow(records) {
  const starts = [];
  const ends = [];
  for (const r of records) {
    if (typeof r.start === "number") starts.push(r.start);
    if (typeof r.end === "number") ends.push(r.end);
  }
  if (!starts.length || !ends.length) return null;
  const winStart = Math.min(...starts);
  const winEnd = Math.max(...ends);
  return winEnd - winStart > 0 ? [winStart, winEnd] : null;
}

/**
 * Monitored vs wall-clock hours over the window, or null when undeterminable.
 *
 * Monitored time is the union of the session runs (plus each event's own span -- a
 * logged event proves the app was listening at that moment, whatever the session records
 * say), minus any recorded gap inside them.
 *
 * With no session records at all -- data captured before sessions existed -- this falls
 * back to whole-window-minus-recorded-gaps, exactly as the Python side does, because
 * such a record genuinely cannot say more. That is the most generous reading the record
 * allows, and the report says so rather than presenting it as measured.
 */
export function coverageHours(records) {
  const window = coverageWindow(records);
  if (!window) return null;
  const [winStart, winEnd] = window;
  const span = winEnd - winStart;
  const holes = clipSpans(
    onlyGaps(records).map((g) => [g.start, g.end]),
    window,
  );
  const sessions = onlySessions(records);
  let monitored;
  if (!sessions.length) {
    monitored = Math.max(0, span - spanSeconds(holes));
  } else {
    const onAir = clipSpans(
      [
        ...sessions.map((s) => [s.start, typeof s.end === "number" ? s.end : s.start]),
        ...onlyEvents(records).map((e) => [e.start, e.end]),
      ],
      window,
    );
    monitored = spanSeconds(subtractSpans(onAir, holes));
  }
  return {
    monitoredHours: monitored / 3600,
    wallClockHours: span / 3600,
    sessionsKnown: sessions.length > 0,
  };
}

/**
 * Stretches of the reporting window with no monitor running at all, or null.
 *
 * The browser twin of `report.render.off_air_spans`. null means the record cannot say
 * (no window, or no session records at all), which is a different statement from "none"
 * and is rendered as one: with no session rows the calendar marks nothing unmonitored
 * rather than inventing an outage the record cannot support.
 *
 * A gap is written by a *running* app catching its own coverage hole, so the ordinary
 * outage -- the tab closed, the device asleep, the app never opened that day -- leaves
 * no gap behind. Only the hole between two session records can find it.
 */
export function offAirSpans(records) {
  const window = coverageWindow(records);
  if (!window) return null;
  const sessions = onlySessions(records);
  if (!sessions.length) return null;
  const onAir = clipSpans(
    [
      ...sessions.map((s) => [s.start, typeof s.end === "number" ? s.end : s.start]),
      ...onlyEvents(records).map((e) => [e.start, e.end]),
    ],
    window,
  );
  return subtractSpans([window], onAir);
}

/**
 * Every calendar date (in `tz`) the window touches, as `YYYY-MM-DD`, in order.
 *
 * The browser twin of `report.render._fill_window_days`' day walk. The arithmetic runs
 * on UTC midnights of the *local* dates rather than by adding 86400 to the window's own
 * timestamps, so a daylight-saving transition inside the window cannot skip a day or
 * emit one twice.
 */
export function windowDays([winStart, winEnd], tz) {
  const first = partsInTz(winStart * 1000, tz).date;
  const last = partsInTz(winEnd * 1000, tz).date;
  const days = [];
  let cursor = Date.parse(`${first}T00:00:00Z`);
  const end = Date.parse(`${last}T00:00:00Z`);
  while (cursor <= end) {
    days.push(new Date(cursor).toISOString().slice(0, 10));
    cursor += 86400000;
  }
  return days;
}

/**
 * Which `date|hour` calendar cells the device was not listening for.
 *
 * The browser twin of `report.render._unmonitored_buckets`: only cells that exist in the
 * grid and hold zero events are marked, so a partly covered hour with a real event in it
 * still shows its count rather than being overwritten by the absence around it. Recorded
 * gaps and off-air stretches both count: they are different outages and neither is a
 * quiet hour.
 */
export function unmonitoredCells(records, byDayHour, tz) {
  const offAir = offAirSpans(records);
  const spans = [...onlyGaps(records).map((g) => [g.start, g.end]), ...(offAir || [])];
  const cells = new Set();
  for (const [start, end] of mergeSpans(spans)) {
    for (let t = start; t < end; t += 3600) {
      const { hour, date } = partsInTz(t * 1000, tz);
      if (byDayHour[date] && (byDayHour[date][hour] || 0) === 0) cells.add(`${date}|${hour}`);
    }
  }
  return cells;
}

// The claim itself, held as a template rather than built inline, so the shape lives in
// exactly one place on this side and can be checked character for character against the
// shared vector's `coverage.sentence_template` (pwa/report.test.mjs). Python's copy is
// COVERAGE_SENTENCE_TEMPLATE in report/violations.py, and the vector is generated from
// that one by scripts/gen_cover_spec.py -- so there is a single definition, and both
// suites fail the moment this stops matching it. Each placeholder is pre-formatted by
// the caller: hours to one decimal place, the percentage as a whole number.
export const COVERAGE_SENTENCE_TEMPLATE =
  "Over this reporting window the device monitored {monitored} of {wall} " +
  "wall-clock hours ({pct}%); the remaining {unmonitored} hours are shown as not " +
  "monitored rather than quiet.";

// The `{name}` substitution Python's str.format does for the same template. An unknown
// placeholder throws rather than surviving into the text: a template that gained a field
// this port does not fill would otherwise ship a literal "{...}" to a reader as though it
// were a measurement.
function fillTemplate(template, values) {
  return template.replace(/\{(\w+)\}/g, (whole, key) => {
    if (!Object.prototype.hasOwnProperty.call(values, key)) {
      throw new Error(`coverage sentence template has no value for ${whole}`);
    }
    return values[key];
  });
}

/** The one-line coverage claim, or the stated limit when it cannot be computed. */
export function coverageSentence(summary) {
  const { monitoredHours: monitored, wallClockHours: wall } = summary;
  if (monitored === null || wall === null) return COVERAGE_UNKNOWN_NOTE;
  const pct = wall ? (monitored / wall) * 100 : 0;
  const unmonitored = Math.max(0, wall - monitored);
  return fillTemplate(COVERAGE_SENTENCE_TEMPLATE, {
    monitored: monitored.toFixed(1),
    wall: wall.toFixed(1),
    pct: pct.toFixed(0),
    unmonitored: unmonitored.toFixed(1),
  });
}

/** The coverage statement as plain-text lines, for a CSV comment preamble. */
export function coverageTextLines(summary) {
  const lines = [
    COVERAGE_HEADING,
    "",
    coverageSentence(summary),
    "",
    COVERAGE_ABSENCE_NOTE,
    "",
    COVERAGE_UPPER_BOUND_CAVEAT,
  ];
  if (summary.wallClockHours !== null && !summary.sessionsKnown) {
    lines.push("", NO_SESSION_RECORD_NOTE);
  }
  // The erasure disclosure rides with the coverage statement, so it reaches every export
  // that carries one — including the event CSV, which lists no gaps of its own and would
  // otherwise be the one file that could be forwarded with no sign that a window had been
  // removed from it.
  const erased = summary.erasedLines || [];
  if (erased.length) {
    lines.push("", ERASED_HEADING, "", ERASED_NOTE, "", ...erased.map((line) => `  - ${line}`));
  }
  return lines;
}

// A record from before session tracking cannot show time with nothing running, so the
// figure above assumes the app was listening whenever no gap was recorded. That is the
// most generous reading available, and naming it is the difference between a measurement
// and an assumption presented as one.
export const NO_SESSION_RECORD_NOTE =
  "This record carries no monitoring sessions, so periods when nothing was running " +
  "cannot be identified from it and are not subtracted above. The coverage figure " +
  "therefore assumes the app was listening whenever no gap was recorded, which is the " +
  "most generous reading the record allows.";

function coverageHtml(summary) {
  const cell = (h) => (h === null ? "not determined" : `${h.toFixed(1)} h`);
  const unmonitored =
    summary.wallClockHours === null
      ? null
      : Math.max(0, summary.wallClockHours - summary.monitoredHours);
  const ok = summary.wallClockHours !== null && unmonitored !== null && unmonitored < 0.05;
  const extra = summary.wallClockHours !== null && !summary.sessionsKnown ? NO_SESSION_RECORD_NOTE : "";
  return `<section class="${ok ? "banner banner-ok" : "banner"}" role="note" aria-label="Monitoring coverage">
<p><strong>${esc(COVERAGE_HEADING)}:</strong> ${esc(coverageSentence(summary))}</p>
<p>${esc(COVERAGE_ABSENCE_NOTE)}</p>
<p class="note">${esc(COVERAGE_UPPER_BOUND_CAVEAT)}</p>
${extra ? `<p class="note">${esc(extra)}</p>` : ""}
${table("Monitoring coverage", ["Measure", "Hours"], [
  ["Monitored (wall-clock hours)", cell(summary.monitoredHours)],
  ["Reporting window (wall-clock hours)", cell(summary.wallClockHours)],
  ["Not monitored (wall-clock hours)", cell(unmonitored)],
])}
</section>`;
}

function partsInTz(ms, tz) {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
  });
  const p = Object.fromEntries(fmt.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return { hour: parseInt(p.hour, 10) % 24, date: `${p.year}-${p.month}-${p.day}` };
}

function inQuietHours(hour, startHour, endHour) {
  if (startHour <= endHour) return hour >= startHour && hour < endHour;
  return hour >= startHour || hour < endHour; // wraps midnight
}

// The store holds three kinds of record, distinguished by a `kind` field that detected
// events deliberately do not carry:
//
//   (no kind)                          a detected event
//   { kind: 'gap',     start, end }    the tab was backgrounded or locked: a coverage
//                                      hole inside a run, written by the running app
//   { kind: 'gap',     start, end,     the operator erased this window; the measurements
//                      reason:          are gone and this row is the only record they
//                      'erased', note } existed
//   { kind: 'session', start, end }    one observation run, start() to stop()
//
// Events are therefore selected as "records with no kind", not as "not a gap". The
// difference is the whole of issue #64's first hazard: `(r) => !isGap(r)` would have
// counted every session record as a loud event the moment sessions were introduced,
// inflating every count in the document this file exists to keep honest.
//
// An erasure is a gap and is *selected* as one everywhere coverage is computed, so it
// costs the coverage figures and the calendar nothing to learn about it. It is separated
// only where the document explains a gap in words, because "the browser cannot monitor
// while the tab is backgrounded" is not why an erased window is missing.
const isGap = (r) => r && r.kind === "gap";
const isErased = (r) => isGap(r) && r.reason === ERASED_REASON;
const isSession = (r) => r && r.kind === "session";
const onlyEvents = (records) => records.filter((r) => r && !r.kind);
const onlyGaps = (records) => records.filter(isGap);
const onlyErased = (records) => records.filter(isErased);
const onlySessions = (records) => records.filter(isSession);

/** Why a gap row is missing, in words. Never blank, and never the wrong reason. */
export function gapReason(gap) {
  return isErased(gap)
    ? `erased by the operator (${gap.note || NO_REASON_GIVEN})`
    : "tab backgrounded or device locked";
}

/**
 * One line per erased window, oldest first, with the reason the operator gave.
 *
 * Empty when nothing was erased, which is what keeps the disclosure section out of a
 * report that has nothing to disclose — `ERASED_NOTE` says in terms that a report without
 * the section had nothing erased from it, so the absence is not silent.
 */
export function erasedWindowLines(records) {
  return onlyErased(records)
    .slice()
    .sort((a, b) => a.start - b.start)
    .map(
      (g) =>
        `${new Date(g.start * 1000).toISOString()} to ${new Date(g.end * 1000).toISOString()} ` +
        `(${((g.end - g.start) / 3600).toFixed(1)} h) — erased (${g.note || NO_REASON_GIVEN})`,
    );
}

/**
 * The gap record an erasure leaves behind, given a window and the operator's reason.
 *
 * Built here rather than in pwa/app.js so the one place that decides what an erasure looks
 * like is the same file that decides how one is read back. `note` is normalised to a
 * string and never invented: an empty reason stays empty and is rendered as
 * `NO_REASON_GIVEN` at the point of display, not stored as it.
 */
export function erasureRecord(start, end, note = "") {
  return { kind: "gap", start, end, reason: ERASED_REASON, note: String(note || "") };
}

/**
 * Whether erasing `[start, end)` removes this record. Ported predicate-for-predicate from
 * `EventStore.forget` (store/db.py), because the two implementations erasing different
 * rows for the same request is the drift `spec/SEMANTICS.md` exists to stop.
 *
 * - **Events go by overlap, not containment.** A row that straddles the boundary still
 *   carries measurement from inside the window, and a half-covered event cannot be
 *   half-erased.
 * - **A gap goes only if it lies wholly inside the window**, which the erasure row
 *   subsumes. One that straddles the boundary also says something about time *outside*
 *   the window, and the erasure row does not cover that part.
 * - **An erasure row is never erased.** Removing the disclosure of an earlier erasure is
 *   the single deletion this whole design exists to prevent.
 * - **Session records stay.** A session is metadata about a run — when it began, when it
 *   ended — not a measurement of any moment, and a run usually spans far more than the
 *   erased window. Deleting it would destroy the lineage of the rows that were *kept*, to
 *   no privacy end, and would take the erased hours out of the coverage denominator
 *   entirely, which is the opposite of disclosing them.
 */
export function willForget(record, start, end) {
  if (!record || isErased(record)) return false;
  if (isSession(record)) return false;
  const s = record.start ?? 0;
  const e = record.end ?? record.start ?? 0;
  if (isGap(record)) return s >= start && e <= end;
  return e > start && s < end;
}

/**
 * What erasing `[start, end)` would remove, by kind, so a confirmation can state what it
 * is about to destroy before it destroys it rather than after.
 */
export function forgetCounts(records, start, end) {
  const doomed = records.filter((r) => willForget(r, start, end));
  return { events: doomed.filter((r) => !r.kind).length, gaps: doomed.filter(isGap).length };
}

/** How many of these records are detected events, as opposed to gaps or sessions. */
export function countEvents(records) {
  return onlyEvents(records).length;
}

export function summarize(records, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const events = onlyEvents(records);
  const gaps = onlyGaps(records);
  const cov = coverageHours(records);
  let gapSeconds = 0;
  for (const g of gaps) gapSeconds += Math.max(0, (g.end || 0) - (g.start || 0));
  const byHour = {};
  for (let h = 0; h < 24; h++) byHour[h] = 0;
  const byDay = {};
  const byTag = {};
  const byDayHour = {}; // date -> {hour -> count}: the calendar heatmap grid (counts only)
  let totalLoud = 0;
  let quietCount = 0;
  let quietLoud = 0;
  let outsideLoud = 0;
  let loudestPeak = -Infinity;
  let peakSum = 0;
  let longest = 0;
  for (const ev of events) {
    const { hour, date } = partsInTz(ev.start * 1000, tz);
    byHour[hour] += 1;
    byDay[date] = (byDay[date] || 0) + 1;
    if (!byDayHour[date]) {
      byDayHour[date] = {};
      for (let h = 0; h < 24; h++) byDayHour[date][h] = 0;
    }
    byDayHour[date][hour] += 1;
    if (ev.coarse_tag) byTag[ev.coarse_tag] = (byTag[ev.coarse_tag] || 0) + 1;
    totalLoud += ev.duration;
    peakSum += ev.peak_level;
    loudestPeak = Math.max(loudestPeak, ev.peak_level);
    longest = Math.max(longest, ev.duration);
    if (inQuietHours(hour, startHour, endHour)) {
      quietCount += 1;
      quietLoud += ev.duration;
    } else {
      outsideLoud += ev.duration;
    }
  }
  // Every calendar day the window covers gets a row, not only the days that had an
  // event. Without this a quiet monitored day and a day the app was never opened both
  // simply vanished from the calendar: indistinguishable from each other and from days
  // that were never in the window at all. The Python side fixed this in issue #59
  // (report.render._fill_window_days); this is the same fix on the browser side, where
  // the outage it hides is the commonest one there is -- a closed tab.
  const calendarWindow = coverageWindow(records);
  if (calendarWindow) {
    for (const day of windowDays(calendarWindow, tz)) {
      if (!byDayHour[day]) {
        byDayHour[day] = {};
        for (let h = 0; h < 24; h++) byDayHour[day][h] = 0;
      }
    }
  }
  // Filling those rows with zeros is only honest beside the third state: a zero is a
  // measurement, and an hour nothing was listening for is not one.
  const unmonitored = unmonitoredCells(records, byDayHour, tz);

  return {
    count: events.length,
    totalLoud,
    longest,
    loudestPeak: events.length ? loudestPeak : 0,
    meanPeak: events.length ? peakSum / events.length : 0,
    byHour,
    byDay,
    byTag,
    byDayHour,
    // `date|hour` keys the calendar renders as UNMONITORED_LABEL instead of a count.
    unmonitored,
    quietCount,
    quietLoud,
    outsideCount: events.length - quietCount,
    outsideLoud,
    gapCount: gaps.length,
    gapSeconds,
    gaps,
    // Erased windows travel with the summary for the same reason coverage does: the
    // document that states how much was observed is the document that has to say which of
    // the unobserved part the operator removed on purpose.
    erasedLines: erasedWindowLines(records),
    // Coverage travels with the counts rather than being computed per export path: a
    // count is only meaningful against the time it was counted over, and two exports
    // disagreeing about the denominator would be its own defect. null means the record
    // cannot say, which is a different statement from "0 hours" and is rendered as one.
    ...(cov
      ? { monitoredHours: cov.monitoredHours, wallClockHours: cov.wallClockHours, sessionsKnown: cov.sessionsKnown }
      : { monitoredHours: null, wallClockHours: null, sessionsKnown: false }),
    sessionCount: onlySessions(records).length,
  };
}

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" })[c]);

// The cover block as an accessible HTML section. Deterministic; restates limits that
// already hold elsewhere in the report, adds prominence, never a new claim.
function coverHtml() {
  const li = (xs) => xs.map((x) => `<li>${esc(x)}</li>`).join("");
  return `<section class="cover" aria-label="What this report can and cannot prove">
<h2>${esc(COVER_HEADING)}</h2>
<p><strong>What it can show:</strong></p>
<ul>${li(COVER_CAN)}</ul>
<p><strong>What it cannot prove:</strong></p>
<ul>${li(COVER_CANNOT)}</ul>
<p class="note">${esc(COVER_PRIVACY)}</p>
</section>`;
}

// Any width, not two. This destructured `([k, v])` and dropped every cell past the second
// in silence, so a caller that grew a column got a `<th scope="col">` with no cells under
// it -- a header that labels nothing, which is both a broken table for a screen reader and
// a column of data that simply vanished from the document. The width check makes that a
// failure rather than an omission nobody sees.
function table(caption, headers, rows) {
  const head = headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("");
  const body = rows
    .map((row) => {
      if (row.length !== headers.length) {
        throw new Error(
          `table("${caption}"): a row has ${row.length} cells and the header has ` +
            `${headers.length}. A column would be dropped or left unlabelled.`,
        );
      }
      const [first, ...rest] = row;
      const cells = rest.map((v) => `<td>${esc(v)}</td>`).join("");
      return `<tr><th scope="row">${esc(first)}</th>${cells}</tr>`;
    })
    .join("");
  return `<table><caption>${esc(caption)}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

// A diagonal hatch for the cells nothing was listening for. Paired with a text dash and
// a spelled-out title, so the third state survives with color removed -- the same rule
// report/charts.py follows for the same cell.
const UNMON_HATCH = "repeating-linear-gradient(45deg,#eee,#eee 3px,#bbb 3px,#bbb 5px)";

// Calendar heatmap as an accessible HTML table: rows are days, columns are hours 0..23.
// Cells are shaded by intensity AND print their count, so meaning never depends on color
// alone; the table itself is the data-table equivalent. Counts only — never audio.
//
// A cell nothing was listening for prints no count, not even a zero: there is no
// measurement to print, and an hour rendered as 0 here would be the absence-as-a-value
// defect this file exists to keep out of the report. It also does not enter the row
// total or the shading scale, because an unmonitored hour contributed no events and
// must not be read as having contributed none.
function heatTable(byDayHour, unmonitored = new Set()) {
  const days = Object.keys(byDayHour).sort();
  const isUnmon = (d, h) => unmonitored.has(`${d}|${h}`);
  let max = 0;
  for (const d of days)
    for (let h = 0; h < 24; h++) if (!isUnmon(d, h)) max = Math.max(max, byDayHour[d][h] || 0);
  const head = Array.from({ length: 24 }, (_, h) => `<th scope="col">${String(h).padStart(2, "0")}</th>`).join("");
  const rows = days
    .map((d) => {
      let rowTotal = 0;
      let unmonHours = 0;
      const cells = Array.from({ length: 24 }, (_, h) => {
        const label = `${esc(d)} ${String(h).padStart(2, "0")}:00`;
        if (isUnmon(d, h)) {
          unmonHours += 1;
          return `<td style="background:${UNMON_HATCH};text-align:center" title="${label} — ${esc(UNMONITORED_LABEL)}"><span style="background:#fff;color:#111;padding:0 3px;border-radius:2px">—</span></td>`;
        }
        const v = byDayHour[d][h] || 0;
        rowTotal += v;
        const ratio = max ? v / max : 0;
        const ch = Math.round(255 - (255 - 59) * ratio);
        const cg = Math.round(255 - (255 - 110) * ratio);
        const cb = Math.round(255 - (255 - 165) * ratio);
        const bg = v === 0 ? "#f5f5f5" : `rgb(${ch},${cg},${cb})`;
        // Dark count on a small white chip: WCAG AA (4.5:1) holds at every cell
        // shade. The old fg switch (white text when ratio >= 0.55) genuinely failed
        // AA on mid-intensity cells — same defect class fixed in report/charts.py
        // (see tests/test_svg_contrast.py for the exact ratios on the shared ramp).
        return `<td style="background:${bg};text-align:center" title="${label} — ${v} events"><span style="background:#fff;color:#111;padding:0 3px;border-radius:2px">${v}</span></td>`;
      }).join("");
      // The count of unmonitored hours is a real column, not only a colour: a reader who
      // cannot see the hatch still gets the number, and it is the figure that says how
      // much of the day the row's total was taken over.
      return `<tr><th scope="row">${esc(d)}</th>${cells}<td>${rowTotal}</td><td>${unmonHours}</td></tr>`;
    })
    .join("");
  return `<table><caption>Events by day and hour — darker cells saw more events; counts are printed in every cell. A cell marked — was ${esc(UNMONITORED_LABEL)}: nothing was listening, so no event could have been recorded in it, and it is not a quiet hour.</caption><thead><tr><th scope="col">Day</th>${head}<th scope="col">Total</th><th scope="col">Hours ${esc(UNMONITORED_LABEL)}</th></tr></thead><tbody>${rows}</tbody></table>`;
}

export function buildReportHtml(summary, { generatedAt, tz = "UTC", startHour = 22, endHour = 8 }) {
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const hourRows = Object.entries(summary.byHour).map(([h, c]) => [`${String(h).padStart(2, "0")}`, c]);
  const dayRows = Object.entries(summary.byDay).sort();
  const tagRows = Object.entries(summary.byTag).sort();
  const tagsSection = tagRows.length
    ? `<h2>Event types (coarse hint)</h2><p>A crude, on-device hint, not a fact; it cannot identify a source.</p>${table("Events by coarse type", ["Type", "Events"], tagRows)}`
    : "";
  // Every gap row carries why it is there. The paragraph below used to explain all of
  // them with one sentence about a backgrounded tab, which is true of the gaps the running
  // app writes and false of a window the operator erased on purpose — one explanation
  // covering two different absences, in the table a reader uses to size the other one.
  const gapRows = (summary.gaps || []).map((g) => [
    new Date(g.start * 1000).toISOString(),
    `${new Date(g.end * 1000).toISOString()} (${Math.round((g.end - g.start))}s)`,
    gapReason(g),
  ]);
  const erasedCount = (summary.erasedLines || []).length;
  const gapsSection = gapRows.length
    ? `<h2>Monitoring gaps</h2><p>During ${summary.gapCount} gap(s), totalling ${Math.round(summary.gapSeconds)}s, no events could be detected. These periods are absences of data, not silence. The browser cannot monitor while the tab is backgrounded or the device is locked; ${erasedCount ? `${erasedCount} of these were erased by the operator instead, and are listed again below with the reason given` : "none of these were erased by the operator"}.</p>${table("Monitoring gaps (no data collected)", ["Gap start", "Gap end", "Why"], gapRows)}`
    : "";
  // Omitted rather than rendered empty, on the same rule report/render.py's `_erased_html`
  // follows: a report from a log nobody erased anything from should read as it always did,
  // and ERASED_NOTE says in terms that a report without this section had nothing erased
  // from it, so the absence is not silent.
  const erasedSection = erasedCount
    ? `<h2>${esc(ERASED_HEADING)}</h2><div class="note"><p>${esc(ERASED_NOTE)}</p></div><ul>${summary.erasedLines
        .map((line) => `<li>${esc(line)}</li>`)
        .join("")}</ul>`
    : "";
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olive's Bark Logger — Noise Report</title>
<style>
section.cover { border: 1px solid #bbb; padding: .5rem 1.25rem 1rem; margin: 1rem 0; }
.banner { padding: .75rem 1rem; margin: 1rem 0; border: 2px solid #b35900; }
.note { border-left: 4px solid #3b6ea5; padding: .75rem 1rem; }
</style></head><body>
<main>
<h1>Olive's Bark Logger — Noise Report</h1>
<p>Generated ${esc(generatedAt)}. Sound-level <em>events</em> only. No audio was recorded, stored, or transmitted.</p>
${coverHtml()}
<aside class="banner" role="note" aria-label="Calibration status">
<strong>${esc(UNCALIBRATED_HEADLINE)}</strong> ${esc(UNCALIBRATED_NOTE)}
</aside>
<h2>Monitoring coverage</h2>
${coverageHtml(summary)}
<h2>Summary</h2>
${table("Summary", ["Metric", "Value"], [
  ["Total events", summary.count],
  ["Total loud time (s)", summary.totalLoud.toFixed(1)],
  // With no events there is no peak to report. summarize() returns 0 for the empty
  // case, and 0.0 dBFS is digital full scale -- the loudest reading possible -- so
  // printing it would state that a silent log hit maximum loudness. Same rule as the
  // Python report: absence is written as absence.
  ["Longest event (s)", summary.count ? summary.longest.toFixed(1) : NO_EVENTS_VALUE],
  ["Loudest peak (dBFS)", summary.count ? summary.loudestPeak.toFixed(1) : NO_EVENTS_VALUE],
  ["Mean peak (dBFS)", summary.count ? summary.meanPeak.toFixed(1) : NO_EVENTS_VALUE],
  [`Events during quiet hours (${window})`, summary.quietCount],
])}
<h2>Events by hour of day</h2>
${table("Events by hour of day", ["Hour", "Events"], hourRows)}
<h2>Events by day</h2>
${dayRows.length ? table("Events by day", ["Day", "Events"], dayRows) : "<p>No events yet.</p>"}
<h2>Calendar heatmap</h2>
${Object.keys(summary.byDayHour).length ? `<p>Each cell is the number of events that began in that hour, by day and hour of day. Darker cells saw more events; the count is printed in every cell, so the pattern does not depend on color. Every day the reporting window covers has a row, including the quiet ones and the ones nothing was listening on.</p>${heatTable(summary.byDayHour, summary.unmonitored)}` : "<p>Nothing has been observed yet — no events, no monitoring sessions — so there is no window to draw a calendar over and no calendar to show.</p>"}
${tagsSection}
${gapsSection}
${erasedSection}
<h2>Quiet hours</h2>
<p>Window <strong>${window}</strong> in time zone <strong>${esc(tz)}</strong>. Of ${summary.count} events, <strong>${summary.quietCount}</strong> began within quiet hours and <strong>${summary.outsideCount}</strong> outside them. An event counts as within quiet hours by its start time; this flags a level threshold being crossed, not the source of a sound.</p>
<div class="note"><p>${esc(NO_VERDICT_NOTE)} Compare these counts against your own local ordinance, lease, or HOA rule.</p>
<p>${esc(coverageSentence(summary))} ${esc(NOT_MONITORED_IS_NOT_QUIET)}</p></div>
<h2>Methodology</h2>
<p>Each audio frame is reduced in memory to one RMS level in dBFS and then discarded. An event is recorded when the level stays above the threshold for at least the minimum duration; brief dips shorter than the debounce do not split it. Only six numbers per event are stored — never audio.</p>
<h2>Limitations</h2>
<p>${esc(RELATIVE_DBFS_NOTE)}</p>
<p>${esc(NO_SOURCE_NOTE)}</p>
</main></body></html>`;
}

export function eventsToCsv(records, tz = "UTC") {
  const events = onlyEvents(records);
  const header = ["start_unix", "start_iso", "end_iso", "duration_s", "peak_dbfs", "avg_dbfs", "coarse_tag"];
  const iso = (s) => new Date(s * 1000).toISOString();
  // The cover travels as a leading "#" comment preamble, the way report/export.py writes
  // it. Spreadsheets and csv parsers skip "#" lines; a person reading the file does not.
  const lines = [csvPreamble(coverageTextLines(summarize(records, { tz }))), header.join(",")];
  for (const ev of events) {
    lines.push([
      ev.start.toFixed(3),
      iso(ev.start),
      iso(ev.end),
      ev.duration.toFixed(3),
      ev.peak_level.toFixed(1),
      ev.avg_level.toFixed(1),
      ev.coarse_tag || "",
    ].join(","));
  }
  return lines.join("\n");
}

// Honest quiet-hours export: every event, flagged within/outside the window by its start
// time (in the given tz). Lists all events, never a cherry-picked subset. Counts only.
//
// This is the file a browser user downloads and emails on, so it carries the cover block
// and the no-verdict line as a "#" preamble: a bare table of timestamps and
// "within_quiet_hours,yes" with nothing attached is exactly the document that reads as a
// verdict. Recorded monitoring gaps are named too, since a gap removes events and would
// otherwise make an unmonitored stretch look like a quiet one.
export function violationsToCsv(records, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const events = onlyEvents(records);
  const gaps = onlyGaps(records);
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const header = [
    "start_unix", "start_iso", "end_iso", "hour_local",
    "duration_s", "peak_dbfs", "avg_dbfs", "within_quiet_hours", "quiet_window", "coarse_tag",
  ];
  const iso = (s) => new Date(s * 1000).toISOString();
  // Coverage before the gap list, deliberately. A gap total is a numerator; without the
  // denominator above it, "37s of gap" cannot be placed against a 30-minute test run or
  // a ten-hour night, which was the whole of issue #64.
  const notes = [
    NO_VERDICT_NOTE,
    "",
    ...coverageTextLines(summarize(records, { startHour, endHour, tz })),
    "",
    ...gapPreambleLines(gaps),
  ];
  const lines = [csvPreamble(notes), header.join(",")];
  for (const ev of events) {
    const { hour } = partsInTz(ev.start * 1000, tz);
    const within = inQuietHours(hour, startHour, endHour);
    lines.push([
      ev.start.toFixed(3),
      iso(ev.start),
      iso(ev.end),
      String(hour).padStart(2, "0"),
      ev.duration.toFixed(3),
      ev.peak_level.toFixed(1),
      ev.avg_level.toFixed(1),
      within ? "yes" : "no",
      window,
      ev.coarse_tag || "",
    ].join(","));
  }
  return lines.join("\n");
}
