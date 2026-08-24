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

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then(async (c) => {
      await Promise.allSettled(
        ASSETS.map(async (asset) => {
          try {
            const res = await fetch(asset);
            if (res.ok) {
              await c.put(asset, res);
            }
          } catch {
            // Individual fetch failure during install should not abort caching other assets
          }
        }),
      );
    }),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
});

self.addEventListener("fetch", (e) => {
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
