// Node test for the PWA aggregation/report/CSV. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  COVER_CAN,
  COVER_CANNOT,
  COVER_HEADING,
  COVER_PRIVACY,
  NO_EVENTS_VALUE,
  NO_VERDICT_NOTE,
  UNCALIBRATED_HEADLINE,
  buildReportHtml,
  eventsToCsv,
  summarize,
  violationsToCsv,
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
