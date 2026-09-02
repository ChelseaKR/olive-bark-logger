// Minimal offline cache. Note: the service worker is a local cache only — it never
// uploads anything. The app makes no network requests at all after these assets load.
const CACHE = "olive-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./clock.js",
  "./detector.js",
  "./level.js",
  "./report.js",
  "./manifest.webmanifest",
];

// Precache each asset on its own, rather than with cache.addAll().
//
// addAll() is all-or-nothing per the Cache API spec: if any single one of these fetches
// fails — one transient hiccup on one file — none of the responses are stored and the
// whole precache silently rolls back, with nothing surfaced anywhere. #65/#66/#67 fixed
// *which* files are listed above; this is the install path that stores them, which was
// the fragile half. A client that hit it on the exact visit meant to fix its offline
// reload stayed broken until some later visit where all eight fetches happened to
// succeed at once.
//
// So: cache them individually, keep whatever succeeded, then fail the install if any did
// not. Both halves matter.
//
//   * Keeping partial progress means the next attempt only has to fetch what is still
//     missing. Cache Storage is origin-scoped and outlives a discarded worker, so the
//     assets that did land stay landed.
//   * Failing means the browser discards this worker and retries the install on a later
//     navigation, instead of activating one whose cache cannot actually serve an offline
//     reload. A partial cache reporting success is the same defect class as a green
//     status check that cannot fail: it reads as coverage.
//
// cache.add() issues the request internally, exactly as addAll() did, and every URL it
// is given comes from the same-origin relative paths in ASSETS — nothing else, ever.
// tests/test_pwa_gates.py's no-egress scan is unchanged and still allows exactly one
// direct network call in this file, the cache-miss passthrough in the fetch handler
// below. (That scan reads comments too, and rejected an earlier draft of this note for
// containing the forbidden token in prose. Working as intended: it is a text scan by
// design, and a scan that made an exception for comments would be one comment away from
// making an exception for code.)
async function precache() {
  const cache = await caches.open(CACHE);
  const results = await Promise.allSettled(ASSETS.map((asset) => cache.add(asset)));
  const failed = ASSETS.filter((_, i) => results[i].status === "rejected");
  if (failed.length) {
    throw new Error(
      `olive: precache incomplete — ${failed.length} of ${ASSETS.length} asset(s) failed ` +
        `(${failed.join(", ")}). Whatever did fetch is kept; this install is rejected so ` +
        "the browser retries it later rather than activating a worker that cannot serve " +
        "an offline reload.",
    );
  }
}

self.addEventListener("install", (e) => {
  e.waitUntil(precache());
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
});

self.addEventListener("fetch", (e) => {
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
