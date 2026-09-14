// Lightweight portal helper for runtime JS modules.
// This mirrors the TypeScript helper to support plain .js consumers
// (e.g. wasm/runtime files) without depending on TS compilation.
export function getPortalRoot() {
    const el =
        document.querySelector('.visor-embed-style') ||
        document.getElementById('TheiaContainer') ||
        document.getElementById('VisorContainer') ||
        document.body;
    return el;
}

export function appendToPortal(el) {
    getPortalRoot().appendChild(el);
}

export function removeFromPortal(el) {
    if (el && el.parentElement) {
        el.parentElement.removeChild(el);
    }
}
