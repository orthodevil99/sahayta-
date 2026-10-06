/* Sahayta service worker — app-shell cache + offline fallback.
 * SOS outbox replay is handled by the app (lib/sync.ts) on 'online' + boot,
 * which works for BOTH demo and REST modes. The SW stays out of POST replay
 * to avoid double-submits; idempotency is via client_report_id regardless.
 */
const CACHE = "sahayta-v1";
const SHELL = [
  "/", "/report/", "/board/", "/volunteer/", "/alerts/", "/admin/",
  "/manifest.json", "/offline.html",
  "/demo-data/districts.json",
  "/demo-data/alert-templates/flood.json",
  "/demo-data/alert-templates/heatwave.json",
  "/demo-data/alert-templates/cyclone.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    // Third-party (tiles, fonts): stale-while-revalidate, never block the app.
    e.respondWith(
      caches.open(CACHE).then(async (c) => {
        const hit = await c.match(request);
        const net = fetch(request).then((r) => { if (r.ok) c.put(request, r.clone()); return r; }).catch(() => hit);
        return hit || net;
      }),
    );
    return;
  }
  // Demo data: cache-first (large, static, content-hashed by content in practice).
  if (url.pathname.startsWith("/demo-data/")) {
    e.respondWith(caches.match(request).then((hit) => hit || fetch(request).then((r) => {
      const copy = r.clone();
      caches.open(CACHE).then((c) => c.put(request, copy));
      return r;
    })));
    return;
  }
  // Navigations: network-first, fall back to cache, then offline page.
  if (request.mode === "navigate") {
    e.respondWith(
      fetch(request).then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
        return r;
      }).catch(() => caches.match(request).then((hit) => hit || caches.match("/offline.html"))),
    );
    return;
  }
  // Same-origin assets: stale-while-revalidate.
  e.respondWith(
    caches.match(request).then((hit) => {
      const net = fetch(request).then((r) => {
        if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(request, copy)); }
        return r;
      }).catch(() => hit);
      return hit || net;
    }),
  );
});
