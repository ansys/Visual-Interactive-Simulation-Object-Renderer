/*
 * THIS SERVICE WORKER IS REGISTERED IN WasmView.js
 */
const sw = /**@type{ServiceWorkerGlobalScope}*/ self;
sw.onactivate = (e) => {
    // When a service worker is initially registered, pages won't
    // use it until their next load. The claim() method causes
    // those pages to be controlled immediately. Be aware that
    // this results in your service worker controlling pages that
    // loaded regularly over the network, or possibly via a
    // different service worker.
    // see https://stackoverflow.com/a/68773653
    e.waitUntil(self.clients.claim());
};
sw.onfetch = (e) => {
    e.respondWith(
        /**@type{PromiseLike<Response>}*/ (
            async () => {
                let request = /**@type{Request}*/ e.request;
                // Ensure Trame's request to "/paraview" returns a success code. If we do not do this,
                // there will be an error message logged in the browser developer console stating
                // that "/paraview" returned a 404. The request to "/paraview" is not needed for Visor
                // to function.
                if (/paraview\/*$/i.test(request.url) && /^post$/i.test(request.method)) {
                    return new Response('', {
                        status: 200,
                        headers: { 'Content-Type': 'text/plain' },
                    });
                }
                // Ensure we always fetch resources anew, do not cache them.
                // This mitigates strange bugs that may occur if a user's browser
                // decides to cache old versions of trame-vtklocal or the mjs/wasm files.
                return await fetch(request, { cache: 'no-store' });
            }
        )()
    );
};
