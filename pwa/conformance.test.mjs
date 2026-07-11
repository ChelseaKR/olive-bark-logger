// Cross-implementation conformance: the PWA detector must reproduce the exact
// same golden vectors (spec/detector/*.json) that tests/test_conformance.py
// replays against the Python detector. If a vector mismatches here, the JS port
// has drifted from the Python one (or vice versa) — that is the drift being
// caught. See spec/SEMANTICS.md. Auto-run by CI's `node --test pwa/*.test.mjs`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { Detector } from "./detector.js";

const SPEC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "spec", "detector");
const VECTOR_FILES = readdirSync(SPEC_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort();

const TOL = 1e-9;

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

test("spec directory is populated", () => {
  // An empty or moved spec/ dir must fail loudly rather than trivially pass.
  assert.ok(VECTOR_FILES.length > 0, `no conformance vectors found under ${SPEC_DIR}`);
});

for (const file of VECTOR_FILES) {
  const vec = JSON.parse(readFileSync(join(SPEC_DIR, file), "utf8"));
  test(`detector matches vector: ${vec.name}`, () => {
    const p = vec.params;
    const d = new Detector(p.threshold_dbfs, p.min_duration_s, p.debounce_s);
    const events = run(d, vec.readings);
    const expected = vec.expected_events;

    assert.equal(
      events.length,
      expected.length,
      `${vec.name}: got ${events.length} events, expected ${expected.length}`,
    );
    for (let i = 0; i < expected.length; i++) {
      const got = events[i];
      const exp = expected[i];
      for (const key of ["start", "end", "duration", "peak_level", "avg_level"]) {
        assert.ok(
          Math.abs(got[key] - exp[key]) < TOL,
          `${vec.name} event ${i} ${key}: got ${got[key]}, expected ${exp[key]}`,
        );
      }
    }
  });
}
