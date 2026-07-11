// Node test for the PWA clock mapping and gap-record handling. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { computeAnchor, toEpochSeconds } from "./clock.js";
import { eventsToCsv, summarize, violationsToCsv } from "./report.js";

test("anchor maps context time back to wall-clock epoch seconds", () => {
  const nowMs = 1_700_000_000_000;
  const ctxTime = 3.5; // seconds since the AudioContext was created
  const anchor = computeAnchor(nowMs, ctxTime);
  // context-time 0 maps to (now - 3.5s); the same reading maps back to now.
  assert.ok(Math.abs(toEpochSeconds(0, anchor) - (nowMs / 1000 - 3.5)) < 1e-9);
  assert.ok(Math.abs(toEpochSeconds(ctxTime, anchor) - nowMs / 1000) < 1e-9);
  // A later context reading advances epoch time by the same amount.
  assert.ok(Math.abs(toEpochSeconds(ctxTime + 10, anchor) - (nowMs / 1000 + 10)) < 1e-9);
});

test("a context-relative reading buckets into today's local date via summarize", () => {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const nowMs = Date.now();
  const ctxTime = 3.5;
  const anchor = computeAnchor(nowMs, ctxTime);
  const startEpoch = toEpochSeconds(ctxTime, anchor); // ~= now
  const s = summarize(
    [{ start: startEpoch, end: startEpoch + 2, duration: 2, peak_level: -10, avg_level: -13, coarse_tag: null }],
    { tz },
  );
  const days = Object.keys(s.byDay);
  assert.equal(days.length, 1);
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(startEpoch * 1000));
  assert.equal(days[0], today);
});

test("gap records are excluded from event counts and both CSVs", () => {
  const T = Date.UTC(2026, 0, 1, 23) / 1000;
  const real = { start: T, end: T + 2, duration: 2, peak_level: -10, avg_level: -13, coarse_tag: null };
  const gap = { kind: "gap", start: T + 10, end: T + 50 };

  const s = summarize([real, gap], { tz: "UTC" });
  assert.equal(s.count, 1); // gap not counted as an event
  assert.equal(s.gapCount, 1);
  assert.equal(s.gapSeconds, 40);

  const eventLines = eventsToCsv([real, gap]).split("\n");
  assert.equal(eventLines.length, 2); // header + 1 real event only

  const violationLines = violationsToCsv([real, gap], { tz: "UTC" }).split("\n");
  assert.equal(violationLines.length, 2); // header + 1 real event only
});
