// Node test for the PWA clock mapping and gap-record handling. Run: node --test pwa/
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
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

  // Data rows only: both CSVs lead with the "#" cover/caveat preamble (FIX-40).
  const dataRows = (csvText) => csvText.split("\n").filter((l) => !l.startsWith("#"));

  const eventLines = dataRows(eventsToCsv([real, gap]));
  assert.equal(eventLines.length, 2); // header + 1 real event only

  const violationLines = dataRows(violationsToCsv([real, gap], { tz: "UTC" }));
  assert.equal(violationLines.length, 2); // header + 1 real event only
});

// --- Precache completeness: which local modules app.js imports ------------------------
//
// Anchored to real import/export statements, not to the bare word `from`. The previous
// pattern -- /from\s+["'](\.\/[^"']+)["']/g -- matched any literal `from` followed by a
// quoted relative path anywhere in the file, so a comment like
// `// ported from "./legacy.js"` would have been collected as an import and the test
// would then have demanded sw.js precache a module app.js never imports. A false-failure
// trap inside a test written to prevent false negatives (issue #68).
//
// Two shapes are recognised, both anchored to the start of a line:
//   import ... from "./x.js";  /  export ... from "./x.js";   (binding and re-export)
//   import "./x.js";                                          (side-effect only)
// `[^;]*?` cannot cross a statement terminator, so a multi-line import list still
// matches while a match cannot run away into unrelated code below.
const IMPORT_FROM_RE = /^[ \t]*(?:import|export)\b[^;]*?\bfrom\s*["'](\.\/[^"']+)["']/gm;
const IMPORT_SIDE_EFFECT_RE = /^[ \t]*import\s*["'](\.\/[^"']+)["']/gm;

/** Relative module specifiers imported by `src`, in source order, de-duplicated. */
function relativeImportsOf(src) {
  const found = new Set();
  for (const re of [IMPORT_FROM_RE, IMPORT_SIDE_EFFECT_RE]) {
    re.lastIndex = 0;
    let match;
    while ((match = re.exec(src)) !== null) found.add(match[1]);
  }
  return [...found];
}

/** The contents of sw.js's own ASSETS array, or null if it is not declared as one. */
function assetsArrayOf(swSrc) {
  const match = swSrc.match(/const ASSETS\s*=\s*\[([\s\S]*?)\]/);
  return match ? match[1] : null;
}

/** Imported modules that the precache list does not contain. */
function missingFromPrecache(appSrc, swSrc) {
  const assetsSrc = assetsArrayOf(swSrc);
  assert.ok(assetsSrc !== null, "sw.js should declare a const ASSETS = [...] precache list");
  return relativeImportsOf(appSrc).filter(
    (mod) => !assetsSrc.includes(`"${mod}"`) && !assetsSrc.includes(`'${mod}'`),
  );
}

test("sw.js precaches all local modules imported by app.js", () => {
  const pwaDir = dirname(fileURLToPath(import.meta.url));
  const appSrc = readFileSync(join(pwaDir, "app.js"), "utf8");
  const swSrc = readFileSync(join(pwaDir, "sw.js"), "utf8");

  const imported = relativeImportsOf(appSrc);
  assert.ok(imported.length > 0, "app.js should have relative module imports");

  const missing = missingFromPrecache(appSrc, swSrc);
  assert.deepEqual(missing, [], `sw.js ASSETS precache list missing: ${missing.join(", ")}`);
});

test("sw.js precache-completeness check actually fails on a real omission", () => {
  // A canary proving the check above can go red, not just green: this is
  // exactly the shape of the bug that motivated it (a module app.js
  // imports, silently missing from ASSETS) — reproduced against a
  // deliberately mismatched fixture pair, not the real sw.js/app.js.
  const fakeAppSrc = 'import { x } from "./missing-module.js";\n';
  const fakeSwSrc = 'const ASSETS = [\n  "./",\n  "./index.html",\n];\n';
  assert.deepEqual(missingFromPrecache(fakeAppSrc, fakeSwSrc), ["./missing-module.js"]);
});

test("sw.js precache-completeness check is not fooled by a stray mention outside ASSETS", () => {
  // The bug this test itself guards against: matching anywhere in the file
  // text, rather than inside the ASSETS array specifically, would let a
  // leftover comment mask a real omission. Confirms that no longer happens.
  const fakeAppSrc = 'import { x } from "./missing-module.js";\n';
  const fakeSwSrc =
    'const ASSETS = [\n  "./",\n  "./index.html",\n];\n' +
    '// keep "./missing-module.js" in sync with app.js\n';
  assert.deepEqual(
    missingFromPrecache(fakeAppSrc, fakeSwSrc),
    ["./missing-module.js"],
    "a mention of the module outside the ASSETS array must not count as precached",
  );
});

test("a comment that merely contains the word `from` is not read as an import", () => {
  // Issue #68 (2). The old pattern matched the bare word `from` anywhere, so this
  // comment would have been collected as an import and the completeness check would
  // have demanded sw.js precache a file app.js does not import: a false failure, in a
  // test whose whole job is to prevent a false pass.
  const appSrc = [
    'import { real } from "./clock.js";',
    '// ported from "./legacy.js" in 2024',
    'const doc = `see the notes from "./design/notes.md"`;',
  ].join("\n");
  assert.deepEqual(relativeImportsOf(appSrc), ["./clock.js"]);
});

test("side-effect and re-export forms are collected too", () => {
  // Anchoring must not narrow the check into missing real imports. A module pulled in
  // for its side effects alone is still a module sw.js has to precache.
  const appSrc = [
    'import "./polyfill.js";',
    'export { helper } from "./helpers.js";',
    "import {",
    "  a,",
    "  b,",
    '} from "./multi-line.js";',
  ].join("\n");
  assert.deepEqual(relativeImportsOf(appSrc).sort(), [
    "./helpers.js",
    "./multi-line.js",
    "./polyfill.js",
  ]);
});
