// Service worker：App 外殼快取優先、data/*.json 網路優先（離線時用最後一次資料）
const VER = "twdash-v1";
const SHELL = ["./", "index.html", "css/app.css", "js/app.js", "js/util.js", "js/data.js",
  "js/views/overview.js", "js/views/ranking.js", "js/views/stock.js", "js/views/portfolio.js", "js/views/settings.js",
  "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png", "icons/icon-512.png"];

self.addEventListener("install", (e) => { e.waitUntil(caches.open(VER).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VER).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (u.origin !== location.origin) {  // CDN（圖表元件、字型）：快取後重用
    if (/unpkg\.com|fonts\.(googleapis|gstatic)\.com/.test(u.host)) {
      e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).then((res) => { const c = res.clone(); caches.open(VER).then((x) => x.put(e.request, c)); return res; })));
    }
    return;
  }
  const isData = u.pathname.includes("/data/");
  if (isData || u.pathname.endsWith("/") || u.pathname.endsWith("index.html") || u.pathname.endsWith(".js") || u.pathname.endsWith(".css")) {
    // 網路優先：資料與程式更新立即生效；離線才用快取
    const key = isData ? new Request(u.origin + u.pathname) : e.request;
    e.respondWith(fetch(e.request, { cache: "no-cache" }).then((res) => { if (res.ok) { const c = res.clone(); caches.open(VER).then((x) => x.put(key, c)); } return res; })
      .catch(() => caches.match(key).then((r) => r || caches.match("index.html"))));
    return;
  }
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
