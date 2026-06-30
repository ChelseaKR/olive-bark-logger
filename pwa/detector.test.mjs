// Node test for the PWA detector/level ports. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { Detector } from "./detector.js";
import { dbfs, rms, SILENCE_FLOOR_DBFS } from "./level.js";

function run(detector, readings) {
  const events = [];
  for (const [t, level] of readings) {
    const ev = detector.push(t, level);
    if (ev) events.push(ev);
  }
  const final = detector.flush();
  if (final) events.push(final);
  return events;
}

test("single loud frame filtered by min duration", () => {
  const d = new Detector(-30, 0.5, 0.2);
  assert.deepEqual(run(d, [[0, -10], [0.3, -60], [0.6, -60]]), []);
});

test("sustained loud makes one event", () => {
  const d = new Detector(-30, 0.5, 0.2);
  const readings = [];
  for (let i = 0; i <= 10; i++) readings.push([i / 10, -10]);
  readings.push([2.0, -60]);
  const events = run(d, readings);
  assert.equal(events.length, 1);
  assert.equal(events[0].start, 0);
  assert.ok(Math.abs(events[0].duration - 1.0) < 1e-9);
});

test("debounce bridges a brief dip", () => {
  const d = new Detector(-30, 0.3, 1.0);
  const events = run(d, [[0, -10], [0.5, -10], [1.0, -60], [1.5, -10], [2.0, -10], [4.0, -60]]);
  assert.equal(events.length, 1);
  assert.equal(events[0].end, 2.0);
});

test("dip longer than debounce splits events", () => {
  const d = new Detector(-30, 0.3, 0.5);
  const events = run(d, [[0, -10], [0.5, -10], [2.0, -60], [3.0, -10], [3.5, -10], [6.0, -60]]);
  assert.equal(events.length, 2);
});

test("negative params rejected", () => {
  assert.throws(() => new Detector(-30, -1, 0));
});

test("level math: full scale is 0 dBFS, silence floors", () => {
  assert.equal(rms([]), 0);
  assert.ok(Math.abs(dbfs(new Float32Array([1, 1, 1]))) < 1e-9);
  assert.equal(dbfs(new Float32Array([0, 0])), SILENCE_FLOOR_DBFS);
  assert.ok(Math.abs(dbfs(new Float32Array([0.5, 0.5])) - -6.0206) < 1e-3);
});
