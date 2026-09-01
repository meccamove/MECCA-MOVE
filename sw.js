const CACHE='mecca-move-v12';
self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => {
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  if(event.request.method!=='GET') return;
  event.respondWith((async()=>{
    try{
      return await fetch(event.request,{cache:'no-store'});
    }catch(e){
      const cached=await caches.match(event.request);
      if(cached) return cached;
      throw e;
    }
  })());
});
