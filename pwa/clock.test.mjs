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

test("sw.js precaches all local modules imported by app.js", () => {
  const pwaDir = dirname(fileURLToPath(import.meta.url));
  const appSrc = readFileSync(join(pwaDir, "app.js"), "utf8");
  const swSrc = readFileSync(join(pwaDir, "sw.js"), "utf8");

  // Extract static import specifiers from app.js (e.g. from "./clock.js")
  const importRegex = /from\s+["'](\.\/[^"']+)["']/g;
  const importedFiles = [];
  let match;
  while ((match = importRegex.exec(appSrc)) !== null) {
    importedFiles.push(match[1]);
  }

  assert.ok(importedFiles.length > 0, "app.js should have relative module imports");

  // Extract only the ASSETS array's own contents, not the whole file: a
  // stray comment or unrelated string elsewhere in sw.js that happens to
  // mention a module's path must not satisfy this check. If ASSETS itself
  // is ever renamed or restructured, this fails loudly rather than passing
  // vacuously.
  const assetsMatch = swSrc.match(/const ASSETS\s*=\s*\[([\s\S]*?)\]/);
  assert.ok(assetsMatch, "sw.js should declare a const ASSETS = [...] precache list");
  const assetsSrc = assetsMatch[1];

  // Verify each imported relative module is an actual element of ASSETS.
  for (const mod of importedFiles) {
    assert.ok(
      assetsSrc.includes(`"${mod}"`) || assetsSrc.includes(`'${mod}'`),
      `sw.js ASSETS precache list missing imported module: ${mod}`,
    );
  }
});

test("sw.js precache-completeness check actually fails on a real omission", () => {
  // A canary proving the check above can go red, not just green: this is
  // exactly the shape of the bug that motivated it (a module app.js
  // imports, silently missing from ASSETS) — reproduced against a
  // deliberately mismatched fixture pair, not the real sw.js/app.js.
  const fakeAppSrc = 'import { x } from "./missing-module.js";\n';
  const fakeSwSrc = 'const ASSETS = [\n  "./",\n  "./index.html",\n];\n';

  const importRegex = /from\s+["'](\.\/[^"']+)["']/g;
  const importedFiles = [];
  let match;
  while ((match = importRegex.exec(fakeAppSrc)) !== null) {
    importedFiles.push(match[1]);
  }
  const assetsSrc = fakeSwSrc.match(/const ASSETS\s*=\s*\[([\s\S]*?)\]/)[1];

  const missing = importedFiles.filter(
    (mod) => !assetsSrc.includes(`"${mod}"`) && !assetsSrc.includes(`'${mod}'`),
  );
  assert.deepEqual(missing, ["./missing-module.js"]);
});

test("sw.js precache-completeness check is not fooled by a stray mention outside ASSETS", () => {
  // The bug this test itself guards against: matching anywhere in the file
  // text, rather than inside the ASSETS array specifically, would let a
  // leftover comment mask a real omission. Confirms that no longer happens.
  const fakeAppSrc = 'import { x } from "./missing-module.js";\n';
  const fakeSwSrc =
    'const ASSETS = [\n  "./",\n  "./index.html",\n];\n' +
    '// TODO: keep "./missing-module.js" in sync with app.js\n';

  const importRegex = /from\s+["'](\.\/[^"']+)["']/g;
  const importedFiles = [];
  let match;
  while ((match = importRegex.exec(fakeAppSrc)) !== null) {
    importedFiles.push(match[1]);
  }
  const assetsSrc = fakeSwSrc.match(/const ASSETS\s*=\s*\[([\s\S]*?)\]/)[1];

  const missing = importedFiles.filter(
    (mod) => !assetsSrc.includes(`"${mod}"`) && !assetsSrc.includes(`'${mod}'`),
  );
  assert.deepEqual(
    missing,
    ["./missing-module.js"],
    "a mention of the module outside the ASSETS array must not count as precached",
  );
});
