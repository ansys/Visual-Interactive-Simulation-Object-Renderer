/**
 * Helpers to resolve a scoped portal root for UI elements that would
 * otherwise be appended to `document.body` (tooltips, popups, invisible
 * DOM containers used by wasm). Prefer an element with the
 * `.visor-embed-style` class (added by host integrations), then fall back
 * to the client container id `VisorContainer`, and finally to a dedicated
 * `visor-portal-root` element created under `document.body`.
 *
 * A single JS implementation is kept (no separate .ts version) so there is
 * one source of truth; JSDoc types below give TS/TSX consumers proper typing.
 *
 * @returns {HTMLElement}
 */
export function getPortalRoot() {
    const doc = typeof document !== 'undefined' ? document : null;
    if (!doc) {
        // Non-browser environment (SSR). Return a harmless stub to avoid
        // throwing in places that call this helper during static analysis.
        // Callers should guard when used outside the browser.
        return /** @type {HTMLElement} */ ({});
    }

    const el = doc.querySelector('.visor-embed-style') || doc.getElementById('VisorContainer');
    if (el) return /** @type {HTMLElement} */ (el);

    let portalRoot = doc.getElementById('visor-portal-root');
    if (!portalRoot) {
        portalRoot = doc.createElement('div');
        portalRoot.id = 'visor-portal-root';
        portalRoot.setAttribute('data-visor-portal', '1');
        doc.body.appendChild(portalRoot);
    }

    return portalRoot;
}

/**
 * @param {HTMLElement} el
 * @returns {void}
 */
export function appendToPortal(el) {
    getPortalRoot().appendChild(el);
}

/**
 * @param {HTMLElement} el
 * @returns {void}
 */
export function removeFromPortal(el) {
    if (el && el.parentElement) {
        el.parentElement.removeChild(el);
    }
}
