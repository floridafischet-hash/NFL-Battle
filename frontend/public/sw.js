/* NFL Bracket Battle – minimal service worker: makes the app installable and shows an offline
 * notice. API calls, WebSocket and uploads are never cached (always live data). */
const CACHE = "nbb-shell-v1";
const SHELL = ["/offline.html", "/icons/icon-192.png", "/favicon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || req.mode !== "navigate") return; // only page loads; everything else goes straight to the network
  event.respondWith(fetch(req).catch(() => caches.match("/offline.html")));
});
