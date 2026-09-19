const CACHE = "rythu-sodara-shell-v3";
const SHELL = ["/", "/index.html", "/styles.css", "/app.js"];
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  // HTML and JavaScript must update promptly after a deployment; other shell
  // resources still use the cached copy if the network is unavailable.
  const url = new URL(event.request.url);
  if (url.pathname === "/" || url.pathname.endsWith(".html") || url.pathname.endsWith(".js")) {
    event.respondWith(fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match(event.request)));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone();
    if (new URL(event.request.url).origin === self.location.origin) caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => cached)));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(clients.matchAll({type:"window", includeUncontrolled:true}).then(windows => {
    const existing = windows[0];
    if (existing) return existing.focus().then(() => existing.postMessage({type:"OPEN_WEATHER"}));
    return clients.openWindow("/#weather");
  }));
});
