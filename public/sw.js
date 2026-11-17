// Service worker for the EDM Remix Maker PWA.
// Caches the app shell so it loads instantly (and works offline).
const CACHE_NAME = "edm-remix-v2";
const APP_SHELL = [
  "/",
  "/static/index.html",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Always try network for API calls; fall back to cache for app shell.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/download")) {
    return; // let network handle it
  }

  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request)),
  );
});
