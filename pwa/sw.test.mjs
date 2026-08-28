// The service worker's install path, executed rather than read. Run: node --test pwa/
//
// Issue #68: `caches.open(CACHE).then((c) => c.addAll(ASSETS))` is all-or-nothing per
// the Cache API spec. One transient failure on one of the eight assets stored *none* of
// them and surfaced nothing. Everything #65/#66/#67 established about which files belong
// in ASSETS rested on an install path that could silently store nothing at all.
//
// The other PWA tests read `sw.js` as text and assert on its source. Text cannot tell
// you what `addAll` does on a partial failure — only running it can — so this file loads
// the real, shipped `sw.js` into a `node:vm` context with a fake `self` and a fake Cache
// API, fires the install handler, and looks at what ended up in the cache. The canary at
// the bottom runs the *previous* implementation through the identical harness and shows
// it storing nothing, which is what makes the assertions above a gate rather than a
// description.

import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const pwaDir = dirname(fileURLToPath(import.meta.url));
const SW_SRC = readFileSync(join(pwaDir, "sw.js"), "utf8");

// The install handler as it stood before this change, for the canary. Kept verbatim
// rather than described, so the comparison is between two implementations and not
// between an implementation and a paraphrase of one.
const ADD_ALL_INSTALL = `
const CACHE = "olive-v1";
const ASSETS = ["./", "./index.html", "./app.js", "./clock.js", "./detector.js", "./level.js", "./report.js", "./manifest.webmanifest"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
});
`;

/**
 * Load a service-worker source into a sandbox with a fake Cache API.
 *
 * `failing` names asset URLs whose fetch rejects, which is the transient-hiccup case.
 * The fake `addAll` reproduces the spec's atomicity deliberately: it resolves every
 * request first and only commits if all of them succeeded. Getting that wrong would
 * make the canary prove nothing.
 */
function loadWorker(source, { failing = [] } = {}) {
  const store = new Map();
  const listeners = new Map();

  const fetchOne = async (url) => {
    if (failing.includes(url)) throw new TypeError(`Failed to fetch: ${url}`);
    return `body-of:${url}`;
  };

  const cache = {
    async add(url) {
      store.set(url, await fetchOne(url));
    },
    async addAll(urls) {
      // Spec behaviour: every response is resolved before anything is written, and a
      // single rejection discards the lot.
      const bodies = await Promise.all(urls.map(fetchOne));
      urls.forEach((url, i) => store.set(url, bodies[i]));
    },
  };

  const caches_ = {
    async open() {
      return cache;
    },
    async keys() {
      return ["olive-v1"];
    },
    async delete() {
      return true;
    },
    async match() {
      return undefined;
    },
  };

  const sandbox = {
    self: { addEventListener: (name, fn) => listeners.set(name, fn) },
    caches: caches_,
    fetch: async () => {
      throw new Error("the install path must not call fetch() directly");
    },
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "sw.js" });
  return { listeners, store };
}

/** Fire the install listener and return the promise it passed to waitUntil. */
function install(worker) {
  const handler = worker.listeners.get("install");
  assert.ok(handler, "sw.js should register an install listener");
  let waited;
  handler({
    waitUntil: (p) => {
      waited = p;
    },
  });
  assert.ok(waited, "the install handler must pass a promise to waitUntil");
  return waited;
}

test("a clean install precaches every asset", async () => {
  const worker = loadWorker(SW_SRC);
  await install(worker);
  assert.equal(worker.store.size, 8);
  assert.ok(worker.store.has("./clock.js")); // the module #66 was about
  assert.ok(worker.store.has("./index.html"));
});

test("one failing asset does not discard the seven that succeeded", async () => {
  // The defect, stated as the assertion: with addAll this number was zero.
  const worker = loadWorker(SW_SRC, { failing: ["./report.js"] });
  await assert.rejects(install(worker), /precache incomplete/);
  assert.equal(worker.store.size, 7, "the assets that did fetch must be kept");
  assert.ok(!worker.store.has("./report.js"));
  assert.ok(worker.store.has("./clock.js"));
});

test("an incomplete precache fails the install rather than activating quietly", async () => {
  // Keeping the partial cache is only half of it. A worker that activates with an
  // incomplete precache reports success while being unable to serve an offline reload,
  // and never runs install again. Rejecting makes the browser retry on a later
  // navigation, with the already-cached assets still in place.
  const worker = loadWorker(SW_SRC, { failing: ["./app.js", "./level.js"] });
  await assert.rejects(install(worker), (err) => {
    assert.match(err.message, /2 of 8/);
    assert.match(err.message, /\.\/app\.js/);
    assert.match(err.message, /\.\/level\.js/);
    return true;
  });
});

test("the addAll install this replaced stored nothing on a single failure", async () => {
  // Canary. Same harness, same one failing asset, previous implementation: everything
  // rolls back. Without this, the test above only describes the new behaviour instead of
  // showing what it fixed — and a gate that cannot show its own defect is not a gate.
  const worker = loadWorker(ADD_ALL_INSTALL, { failing: ["./report.js"] });
  await assert.rejects(install(worker));
  assert.equal(
    worker.store.size,
    0,
    "addAll is all-or-nothing: one transient failure discarded all eight responses",
  );
});
