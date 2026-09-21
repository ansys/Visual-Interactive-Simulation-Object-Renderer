import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type { IRenderer } from '../renderer/IRenderer.ts';

export class EdgesWidget {
    constructor(sceneGraph: VisorSceneNodeExtended, renderer: IRenderer) {
        this.#sceneGraph = sceneGraph;
        this.#renderer = renderer;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    #sceneGraph: VisorSceneNodeExtended;
    #renderer: IRenderer;

    setEdgesVisibleAsync = async (enable?: boolean | null): Promise<void> => {
        this.#enabled = enable ?? !this.#enabled;
        const promises = [];
        for (const n of this.#sceneGraph.descendantActorNodesOrSelfArray) {
            promises.push(this.#renderer.setEdgeVisibilityAsync(n.id, this.#enabled));
        }
        await Promise.all(promises);
    };
}
