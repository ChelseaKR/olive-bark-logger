// Node test for the PWA aggregation/report/CSV. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { buildReportHtml, eventsToCsv, summarize, violationsToCsv } from "./report.js";

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
  const lines = csv.split("\n");
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
  const lines = csv.split("\n");
  assert.ok(lines[0].startsWith("start_unix,"));
  assert.ok(lines[0].includes("within_quiet_hours"));
  assert.equal(lines.length, 3); // header + 2 events (all events listed, honest)
  assert.ok(lines[1].includes(",yes,")); // 23:00 is within quiet hours
  assert.ok(lines[1].endsWith(",bark-like"));
  assert.ok(lines[2].includes(",no,")); // 12:00 is outside
  assert.ok(lines[1].includes("22:00–08:00"));
});
