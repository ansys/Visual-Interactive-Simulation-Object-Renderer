// Lightweight portal helper for runtime JS modules.
// This mirrors the TypeScript helper to support plain .js consumers
// (e.g. wasm/runtime files) without depending on TS compilation.
export function getPortalRoot() {
    const doc = typeof document !== 'undefined' ? document : null;
    if (!doc) {
        return {};
    }

    const el = doc.querySelector('.visor-embed-style') || doc.getElementById('VisorContainer');
    if (el) return el;

    let portalRoot = doc.getElementById('visor-portal-root');
    if (!portalRoot) {
        portalRoot = doc.createElement('div');
        portalRoot.id = 'visor-portal-root';
        portalRoot.setAttribute('data-visor-portal', '1');
        doc.body.appendChild(portalRoot);
    }

    return portalRoot;
}

export function appendToPortal(el) {
    getPortalRoot().appendChild(el);
}

export function removeFromPortal(el) {
    if (el && el.parentElement) {
        el.parentElement.removeChild(el);
    }
}
