import type { NodeId } from '../renderer/IRenderer';
import type { CanvasClick } from '../rca/ServerCanvas';

/** A viewer-clicked listener: the picked node or null, the click's modifier keys, and its VTK-normalised position. */
export type ViewerClickedListener = (
    nodeId: NodeId | null,
    ctrlKey: boolean,
    shiftKey: boolean,
    normX: number,
    normY: number
) => void;

/** Runs at most one part pick at a time and gives each pick's result to every viewer-clicked listener once. */
export class ViewerClickDispatcher {
    /** Add listener; returns its remover. */
    addListener(listener: ViewerClickedListener): () => void {
        const remover = () => {
            this.#listeners.delete(remover);
        };
        this.#listeners.set(remover, listener);
        return remover;
    }

    /** Remove every listener. */
    clear(): void {
        this.#listeners.clear();
    }

    /**
     * Unless a pick is running, run pick and call every listener once with its
     * node and click's keys and position; a click during a pick is dropped.
     * A pick that rejects calls no listener, and the rejection propagates.
     */
    async dispatchAsync(click: CanvasClick, pick: () => Promise<NodeId | null>): Promise<void> {
        if (this.#pickPending) {
            return;
        }
        this.#pickPending = true;
        try {
            const nodeId = await pick();
            for (const listener of this.#listeners.values()) {
                listener(nodeId, click.ctrlKey, click.shiftKey, click.normX, click.normY);
            }
        } finally {
            this.#pickPending = false;
        }
    }

    readonly #listeners = new Map<() => void, ViewerClickedListener>();
    #pickPending = false;
}
