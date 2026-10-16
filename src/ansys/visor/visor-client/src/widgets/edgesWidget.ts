import type { WasmRenderer } from '../renderer/WasmRenderer.ts';

export class EdgesWidget {
    /** Fan the global edges toggle out to every node the renderer holds. */
    constructor(renderer: WasmRenderer) {
        this.#renderer = renderer;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    #renderer: WasmRenderer;

    setEdgesVisibleAsync = async (enable?: boolean | null): Promise<void> => {
        this.#enabled = enable ?? !this.#enabled;
        const promises = [];
        for (const nodeId of this.#renderer.nodeIds()) {
            promises.push(this.#renderer.setEdgeVisibilityAsync(nodeId, this.#enabled));
        }
        await Promise.all(promises);
    };
}
