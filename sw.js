// Network first, so updates arrive straight away; falls back to the cached copy when offline.
const CACHE='baktas-v1';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy)).catch(()=>{});return r;})
    .catch(()=>caches.match(e.request,{ignoreSearch:true})));
});
