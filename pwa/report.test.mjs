// Node test for the PWA aggregation/report/CSV. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  COVERAGE_ABSENCE_NOTE,
  COVERAGE_HEADING,
  COVERAGE_SENTENCE_TEMPLATE,
  COVERAGE_UNKNOWN_NOTE,
  COVER_CAN,
  COVER_CANNOT,
  COVER_HEADING,
  COVER_PRIVACY,
  NO_EVENTS_VALUE,
  NO_SESSION_RECORD_NOTE,
  NO_VERDICT_NOTE,
  UNCALIBRATED_HEADLINE,
  UNMONITORED_LABEL,
  buildReportHtml,
  countEvents,
  coverageSentence,
  coverageTextLines,
  eventsToCsv,
  offAirSpans,
  summarize,
  violationsToCsv,
  windowDays,
} from "./report.js";

// The shared vector both implementations are held to. Same arrangement as
// spec/detector/*.json: one list, replayed here and in tests/test_export_caveats.py, so
// the two report modules cannot drift the way they did.
const SPEC = JSON.parse(
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "spec", "report", "cover.json"), "utf8"),
);
const REQUIRED_IN_EVERY_EXPORT = [
  SPEC.cover.heading,
  ...SPEC.cover.can,
  ...SPEC.cover.cannot,
  SPEC.cover.privacy,
];

const ev = (start, dur = 2, peak = -10, tag = null) => ({
  start,
  end: start + dur,
  duration: dur,
  peak_level: peak,
  avg_level: peak - 3,
  coarse_tag: tag,
});

// 2026-01-01 23:00 and 02:00 UTC, and 12:00 UTC.
const T23 = Date.UTC(2026, 0, 1, 23) / 1000;
const T02 = Date.UTC(2026, 0, 2, 2) / 1000;
const T12 = Date.UTC(2026, 0, 1, 12) / 1000;

test("summarize counts, distributions, quiet hours", () => {
  const s = summarize([ev(T23), ev(T02), ev(T12)], { startHour: 22, endHour: 8, tz: "UTC" });
  assert.equal(s.count, 3);
  assert.equal(s.byHour[23], 1);
  assert.equal(s.byHour[2], 1);
  assert.equal(s.quietCount, 2); // 23:00 and 02:00 are in 22-08
});

test("summarize tags", () => {
  const s = summarize([ev(T12, 2, -10, "bark-like"), ev(T12, 2, -10, "bark-like")], { tz: "UTC" });
  assert.equal(s.byTag["bark-like"], 2);
});

test("report has mandatory sections and no-audio statement", () => {
  const s = summarize([ev(T23)], { tz: "UTC" });
  const html = buildReportHtml(s, { generatedAt: "2026-01-01", tz: "UTC" });
  assert.ok(html.includes("<h2>Methodology</h2>"));
  assert.ok(html.includes("<h2>Limitations</h2>"));
  assert.ok(html.includes("No audio was recorded"));
  assert.ok(html.includes("cannot prove"));
  assert.ok(html.includes('<html lang="en">'));
});

test("csv has header and rows", () => {
  const csv = eventsToCsv([ev(T23, 2, -8, "bark-like")]);
  const lines = csv.split("\n").filter((l) => !l.startsWith("#"));
  assert.ok(lines[0].startsWith("start_unix,"));
  assert.equal(lines.length, 2);
  assert.ok(lines[1].endsWith(",bark-like"));
});

test("summarize builds the day x hour heatmap grid and outside counts", () => {
  const s = summarize([ev(T23), ev(T23), ev(T02), ev(T12)], { startHour: 22, endHour: 8, tz: "UTC" });
  assert.equal(s.byDayHour["2026-01-01"][23], 2);
  assert.equal(s.byDayHour["2026-01-02"][2], 1);
  // Each present day covers all 24 hours.
  assert.equal(Object.keys(s.byDayHour["2026-01-01"]).length, 24);
  assert.equal(s.outsideCount, 1); // only T12 is outside 22-08
});

test("report includes an accessible calendar heatmap with counts", () => {
  const s = summarize([ev(T23), ev(T23), ev(T02)], { tz: "UTC" });
  const html = buildReportHtml(s, { generatedAt: "2026-01-01", tz: "UTC" });
  assert.ok(html.includes("<h2>Calendar heatmap</h2>"));
  assert.ok(html.includes("does not depend on color")); // not color-only
  assert.ok(html.includes('scope="col"') && html.includes('scope="row"'));
  assert.ok(html.includes("Quiet-hours") || html.includes("began within quiet hours"));
});

test("empty log shows a calendar placeholder, not a broken table", () => {
  const html = buildReportHtml(summarize([], { tz: "UTC" }), { generatedAt: "x", tz: "UTC" });
  assert.ok(html.includes("no calendar to show"));
});

test("violationsToCsv flags every event within/outside quiet hours", () => {
  const csv = violationsToCsv([ev(T23, 2, -8, "bark-like"), ev(T12)], { startHour: 22, endHour: 8, tz: "UTC" });
  const lines = csv.split("\n").filter((l) => !l.startsWith("#"));
  assert.ok(lines[0].startsWith("start_unix,"));
  assert.ok(lines[0].includes("within_quiet_hours"));
  assert.equal(lines.length, 3); // header + 2 events (all events listed, honest)
  assert.ok(lines[1].includes(",yes,")); // 23:00 is within quiet hours
  assert.ok(lines[1].endsWith(",bark-like"));
  assert.ok(lines[2].includes(",no,")); // 12:00 is outside
  assert.ok(lines[1].includes("22:00–08:00"));
});

// --- FIX-40: the caveats travel with the browser exports too ---------------------
//
// Asserted as the absence of the overstatement: there is no export path in this module
// that produces an artifact without the cover block. The set below must stay equal to
// JS_CHECKED in tests/test_export_caveats.py, which discovers the module's export paths
// from source and fails when a new one appears unchecked.
const EXPORTS_UNDER_TEST = () => {
  const records = [ev(T23, 2, -8, "bark-like"), ev(T12), { kind: "gap", start: T23 + 60, end: T23 + 300 }];
  return {
    buildReportHtml: buildReportHtml(summarize(records, { tz: "UTC" }), {
      generatedAt: "2026-01-01",
      tz: "UTC",
    }),
    eventsToCsv: eventsToCsv(records),
    violationsToCsv: violationsToCsv(records, { startHour: 22, endHour: 8, tz: "UTC" }),
  };
};

test("every browser export path carries the cover block", () => {
  for (const [name, text] of Object.entries(EXPORTS_UNDER_TEST())) {
    for (const required of REQUIRED_IN_EVERY_EXPORT) {
      assert.ok(text.includes(required), `${name} ships without: ${required.slice(0, 60)}...`);
    }
  }
});

test("the browser constants are the shared spec, not a second copy", () => {
  assert.deepEqual(COVER_CAN, SPEC.cover.can);
  assert.deepEqual(COVER_CANNOT, SPEC.cover.cannot);
  assert.equal(COVER_PRIVACY, SPEC.cover.privacy);
  assert.equal(COVER_HEADING, SPEC.cover.heading);
  assert.equal(NO_VERDICT_NOTE, SPEC.no_verdict);
  assert.equal(UNCALIBRATED_HEADLINE, SPEC.uncalibrated_headline);
});

test("no browser artifact reports a quiet-hours count without the no-verdict line", () => {
  for (const [name, text] of Object.entries(EXPORTS_UNDER_TEST())) {
    if (!/quiet.hours/i.test(text)) continue;
    assert.ok(
      text.includes(NO_VERDICT_NOTE) || text.includes(SPEC.cover.cannot[2]),
      `${name} reports a quiet-hours count with no no-verdict statement`,
    );
  }
});

test("the browser report says its readings are uncalibrated", () => {
  const html = buildReportHtml(summarize([ev(T23)], { tz: "UTC" }), { generatedAt: "x", tz: "UTC" });
  assert.ok(html.includes(UNCALIBRATED_HEADLINE));
  assert.ok(html.includes("no calibration step"));
});

test("the quiet-hours CSV preamble names its monitoring gaps", () => {
  const gap = { kind: "gap", start: T23 + 60, end: T23 + 300 };
  const withGap = violationsToCsv([ev(T23), gap], { tz: "UTC" });
  assert.ok(withGap.includes("# Monitoring gaps: 1 recorded"));
  assert.ok(withGap.includes("absences of data, not silence"));
  // Stated either way -- "none recorded" is information, silence is not.
  const withoutGap = violationsToCsv([ev(T23)], { tz: "UTC" });
  assert.ok(withoutGap.includes("# Monitoring gaps: none recorded"));
  assert.ok(withoutGap.includes("upper bound"));
});

test("the cover is a comment preamble, so the data rows still parse", () => {
  for (const csv of [eventsToCsv([ev(T23)]), violationsToCsv([ev(T23)], { tz: "UTC" })]) {
    const lines = csv.split("\n");
    assert.ok(lines[0].startsWith("# "), "the cover must lead the file as comments");
    const data = lines.filter((l) => !l.startsWith("#"));
    assert.ok(data[0].startsWith("start_unix,"));
    assert.equal(data.length, 2); // header + 1 event
  }
});

test("an empty log does not print full scale (0.0 dBFS) as its loudest peak", () => {
  // summarize() returns 0 for the empty case and 0 dBFS is digital full scale -- the
  // loudest reading possible -- so a silent log must not read as maximum loudness.
  const summary = summarize([], { tz: "UTC" });
  assert.equal(summary.count, 0);
  const html = buildReportHtml(summary, { generatedAt: "x", tz: "UTC" });
  for (const label of ["Loudest peak (dBFS)", "Mean peak (dBFS)", "Longest event (s)"]) {
    assert.ok(
      html.includes(`<th scope="row">${label}</th><td>${NO_EVENTS_VALUE}</td>`),
      `${label} should read "${NO_EVENTS_VALUE}" with no events`,
    );
    assert.ok(!html.includes(`<th scope="row">${label}</th><td>0.0</td>`));
  }
  // ...and a log with events still prints its real peak.
  const withEvents = buildReportHtml(summarize([ev(T23, 2, -8)], { tz: "UTC" }), {
    generatedAt: "x",
    tz: "UTC",
  });
  assert.ok(withEvents.includes("<td>-8.0</td>"));
  assert.ok(!withEvents.includes(NO_EVENTS_VALUE));
});

// --- Monitoring coverage (issue #64) -------------------------------------------------
//
// The browser edition made pwa/README.md's "honest ... submission" claim about its
// quiet-hours CSV while stating a gap total with no denominator. #39 had already
// established, for the Python side, that a count is only readable against the time it
// was counted over. These tests hold the browser to the same strings, from the same
// shared vector, and to the same arithmetic.

const COV = SPEC.coverage;
const HOUR = 3600;
const T0 = Date.UTC(2026, 2, 1, 20) / 1000; // 20:00 UTC

const session = (start, end) => ({ kind: "session", start, end });
const gap = (start, end) => ({ kind: "gap", start, end });

test("the coverage strings are the shared vector's, verbatim", () => {
  assert.equal(COVERAGE_HEADING, COV.heading);
  assert.equal(COVERAGE_ABSENCE_NOTE, COV.absence_note);
  assert.equal(COVERAGE_UNKNOWN_NOTE, COV.unknown_note);
  // The sentence shape too, not only the sentence this port happens to build from it.
  // The vector is generated from report/violations.py's COVERAGE_SENTENCE_TEMPLATE
  // (scripts/gen_cover_spec.py), so this is what makes the Python constant the single
  // definition rather than the first of two.
  assert.equal(COVERAGE_SENTENCE_TEMPLATE, COV.sentence_template);
});

test("the coverage sentence matches the shared template exactly", () => {
  // 10 wall-clock hours, one 8-hour run, one 1-hour gap inside it: 7 monitored.
  const records = [session(T0, T0 + 8 * HOUR), gap(T0 + HOUR, T0 + 2 * HOUR), ev(T0 + 3 * HOUR)];
  const s = summarize([...records, { kind: "gap", start: T0 + 10 * HOUR - 1, end: T0 + 10 * HOUR }], {
    tz: "UTC",
  });
  const expected = COV.sentence_template
    .replace("{monitored}", s.monitoredHours.toFixed(1))
    .replace("{wall}", s.wallClockHours.toFixed(1))
    .replace("{pct}", ((s.monitoredHours / s.wallClockHours) * 100).toFixed(0))
    .replace("{unmonitored}", (s.wallClockHours - s.monitoredHours).toFixed(1));
  assert.equal(coverageSentence(s), expected);
});

test("a session record is not counted as a loud event", () => {
  // The hazard introducing sessions creates: `!isGap(r)` would have made every session
  // record an event, inflating the very counts this file exists to keep honest.
  const s = summarize([ev(T0), session(T0, T0 + HOUR), gap(T0 + 10, T0 + 20)], { tz: "UTC" });
  assert.equal(s.count, 1);
  assert.equal(s.sessionCount, 1);
  assert.equal(s.gapCount, 1);
  assert.equal(countEvents([ev(T0), session(T0, T0 + HOUR), gap(T0 + 10, T0 + 20)]), 1);
});

test("time with no run in progress is not monitored, and not quiet", () => {
  // Two one-hour runs three hours apart. The middle stretch left no gap record -- the
  // app was not running to write one -- and is exactly what #64 said was invisible.
  const records = [session(T0, T0 + HOUR), session(T0 + 3 * HOUR, T0 + 4 * HOUR)];
  const s = summarize(records, { tz: "UTC" });
  assert.equal(s.wallClockHours, 4);
  assert.equal(s.monitoredHours, 2);
  assert.match(coverageSentence(s), /monitored 2\.0 of 4\.0 wall-clock hours \(50%\)/);
});

test("a recorded gap inside a run is subtracted from monitored time", () => {
  const records = [session(T0, T0 + 4 * HOUR), gap(T0 + HOUR, T0 + 2 * HOUR)];
  const s = summarize(records, { tz: "UTC" });
  assert.equal(s.wallClockHours, 4);
  assert.equal(s.monitoredHours, 3);
});

test("a record with no sessions says so instead of assuming full coverage", () => {
  // Data captured before session tracking. The fallback (window minus recorded gaps) is
  // the most generous reading available, so the export names it as an assumption.
  const s = summarize([ev(T0), ev(T0 + 2 * HOUR)], { tz: "UTC" });
  assert.equal(s.sessionsKnown, false);
  const lines = coverageTextLines(s).join("\n");
  assert.ok(lines.includes(NO_SESSION_RECORD_NOTE));
  assert.ok(lines.includes(COV.absence_note));
});

test("a record with nothing in it says coverage is undeterminable, not zero", () => {
  const s = summarize([], { tz: "UTC" });
  assert.equal(s.monitoredHours, null);
  assert.equal(s.wallClockHours, null);
  assert.equal(coverageSentence(s), COV.unknown_note);
});

test("every quiet-hours export states its coverage, not just its gaps", () => {
  // The defect in one assertion: a gap total is a numerator. #64's report was that the
  // browser shipped one with no denominator anywhere in the artifact.
  const records = [ev(T0), session(T0 - HOUR, T0 + HOUR), gap(T0 + 100, T0 + 200)];
  const s = summarize(records, { startHour: 22, endHour: 8, tz: "UTC" });
  const artifacts = {
    "violations CSV": violationsToCsv(records, { startHour: 22, endHour: 8, tz: "UTC" }),
    "events CSV": eventsToCsv(records, "UTC"),
    "report HTML": buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 }),
  };
  for (const [name, text] of Object.entries(artifacts)) {
    assert.ok(text.includes(COV.heading), `${name} omits the coverage heading`);
    assert.ok(text.includes(COV.absence_note), `${name} omits the not-monitored-is-not-quiet note`);
    assert.ok(
      text.includes("wall-clock hours") || text.includes(COV.unknown_note),
      `${name} states no monitored-vs-wall-clock figure`,
    );
  }
});

test("the violations CSV's coverage lines are comment lines, so data rows still parse", () => {
  const records = [ev(T0), session(T0 - HOUR, T0 + HOUR)];
  const csv = violationsToCsv(records, { tz: "UTC" });
  const dataRows = csv.split("\n").filter((l) => !l.startsWith("#"));
  assert.equal(dataRows.length, 2); // header + the one real event
  assert.ok(csv.split("\n").some((l) => l.startsWith("# ") && l.includes("wall-clock hours")));
});

// ---------------------------------------------------------------------------
// The calendar's third state: a day nothing was listening on is not a quiet day.
//
// Issue #59 gave the Python calendar a row for every day the reporting window covers,
// on the reasoning that "a quiet monitored day and a day the monitor was switched off
// both simply vanished from the calendar". The browser twin of that calendar kept
// building its grid from the days that happened to have an event, where the outage it
// hides is the commonest one there is: a closed tab.
// ---------------------------------------------------------------------------

// Three days. The app runs on day 1 and day 3 with one event each, and is never opened
// on day 2 -- so day 2 leaves no gap row behind, only the hole between two sessions.
const D1 = Date.UTC(2026, 2, 10, 12) / 1000;
const D2 = D1 + 86400;
const D3 = D1 + 2 * 86400;
const threeDayRecords = () => [
  ev(D1),
  ev(D3),
  session(D1 - HOUR, D1 + HOUR),
  session(D3 - HOUR, D3 + HOUR),
];

const calendarOf = (records, tz = "UTC") => summarize(records, { tz });

test("the calendar has a row for every day the window covers, not only the days with events", () => {
  const s = calendarOf(threeDayRecords());
  assert.deepEqual(Object.keys(s.byDayHour).sort(), ["2026-03-10", "2026-03-11", "2026-03-12"]);
});

test("the day nothing was listening on is marked, not filled with zeros", () => {
  const s = calendarOf(threeDayRecords());
  // Every hour of 2026-03-11 is off air: no session covers it and no event falls in it.
  const marked = [...s.unmonitored].filter((k) => k.startsWith("2026-03-11|"));
  assert.equal(marked.length, 24, "the unopened day should be 24 unmonitored hours");
  // And the hour an event was actually recorded in is not marked, on any day.
  assert.ok(!s.unmonitored.has("2026-03-10|12"));
});

test("an unmonitored hour prints no count at all, not a zero", () => {
  const s = calendarOf(threeDayRecords());
  const html = buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 });
  const row = html.split("<tr>").find((r) => r.includes('scope="row">2026-03-11'));
  assert.ok(row, "the unopened day has no row in the rendered calendar");
  assert.ok(row.includes(UNMONITORED_LABEL), "the row does not say what the absence is");
  // A count chip in this row would be the defect: a measurement where there was none.
  // The row total at the end is a different thing and legitimately reads 0 events.
  assert.equal(
    row.match(/>\d+<\/span>/g),
    null,
    `an unmonitored hour rendered a count: ${row.slice(0, 300)}`,
  );
});

test("the third state does not depend on colour", () => {
  const s = calendarOf(threeDayRecords());
  const html = buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 });
  const row = html.split("<tr>").find((r) => r.includes('scope="row">2026-03-11'));
  // Three colour-free carriers: a text dash in the cell, the label in the cell's title,
  // and the day's count of unmonitored hours as a real column.
  assert.ok(row.includes(">—</span>"), "no text marker in the cell");
  assert.ok(row.includes(`— ${UNMONITORED_LABEL}"`), "no spelled-out title on the cell");
  assert.ok(row.trimEnd().endsWith("<td>24</td></tr>"), `no unmonitored-hours column: ${row.slice(-120)}`);
  assert.ok(
    html.includes(`Hours ${UNMONITORED_LABEL}`),
    "the unmonitored-hours column has no header",
  );
});

test("an unmonitored hour is in no total and does not rescale the shading", () => {
  const s = calendarOf(threeDayRecords());
  const html = buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 });
  const row = html.split("<tr>").find((r) => r.includes('scope="row">2026-03-11'));
  // Row total 0 events, 24 hours nobody was listening: the two figures say different
  // things and the row carries both.
  assert.ok(row.includes("<td>0</td><td>24</td>"), `totals wrong: ${row.slice(-160)}`);
});

test("a quiet monitored day keeps its zeros, which are a measurement", () => {
  // Same three days, but the app also ran through day 2 and heard nothing.
  const records = [...threeDayRecords(), session(D2 - 12 * HOUR, D2 + 12 * HOUR)];
  const s = calendarOf(records);
  assert.ok(Object.keys(s.byDayHour).includes("2026-03-11"));
  const covered = [...s.unmonitored].filter((k) => k.startsWith("2026-03-11|"));
  assert.ok(covered.length < 24, "a monitored quiet day was marked as unmonitored");
  const html = buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 });
  const row = html.split("<tr>").find((r) => r.includes('scope="row">2026-03-11'));
  assert.ok(row.includes(">0</span>"), "a monitored quiet hour lost its zero");
});

test("a recorded gap marks its hours too, and an event inside one keeps its count", () => {
  // A gap is a different outage from being off air. Both are absences of data.
  const records = [ev(D1), session(D1 - 3 * HOUR, D1 + 3 * HOUR), gap(D1 + HOUR, D1 + 2 * HOUR)];
  const s = calendarOf(records);
  assert.ok(s.unmonitored.has("2026-03-10|13"), "the gap hour is not marked");
  assert.ok(!s.unmonitored.has("2026-03-10|12"), "the hour holding a real event was marked");
});

test("with no session records the calendar marks nothing, because the record cannot say", () => {
  // A log written before sessions existed. "Cannot say" is not "fully covered" and it
  // is not "entirely off air" either; the honest rendering is no third state at all.
  const s = calendarOf([ev(D1), ev(D3)]);
  assert.equal(s.unmonitored.size, 0);
  assert.equal(offAirSpans([ev(D1), ev(D3)]), null);
});

test("an empty record draws no calendar and says why", () => {
  const s = calendarOf([]);
  assert.deepEqual(Object.keys(s.byDayHour), []);
  const html = buildReportHtml(s, { generatedAt: "now", tz: "UTC", startHour: 22, endHour: 8 });
  assert.ok(html.includes("no window to draw a calendar over"));
});

test("windowDays does not skip or repeat a day across a DST transition", () => {
  // 2026-03-08 is the US spring-forward. Walking by 86400 s from a local timestamp
  // would land on 2026-03-08 twice or skip it; the day walk runs on calendar dates.
  const start = Date.UTC(2026, 2, 6, 20) / 1000;
  const end = Date.UTC(2026, 2, 10, 20) / 1000;
  const days = windowDays([start, end], "America/Los_Angeles");
  assert.deepEqual(days, ["2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10"]);
  assert.equal(new Set(days).size, days.length);
});

test("the two implementations name this absence with the same string", () => {
  // report/charts.py renders the same cell. Two words for one absence is how the two
  // halves of one report start disagreeing in front of a reader.
  const charts = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), "..", "report", "charts.py"),
    "utf8",
  );
  // Either name: this constant was `_UNMON_LABEL` and became the public
  // `UNMONITORED_LABEL` when the quiet-hours rollup started rendering the same string.
  // The binding is to the string, not to the identifier, so a rename on the Python side
  // must not read as "the two sides have stopped agreeing".
  const match = charts.match(/\b_?UNMON(?:ITORED)?_LABEL\s*=\s*"([^"]+)"/);
  assert.ok(match, "report/charts.py no longer defines an unmonitored-cell label");
  assert.equal(UNMONITORED_LABEL, match[1]);
});
