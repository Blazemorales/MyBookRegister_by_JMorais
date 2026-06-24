// Service worker mínimo: existe para que o Android reconheça o app como
// instalável. Sem cache offline — todos os fetches passam direto pela rede.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {});
