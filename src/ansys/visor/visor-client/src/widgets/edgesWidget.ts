import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';

export class EdgesWidget {
    constructor(sceneGraph: VisorSceneNodeExtended) {
        this.#sceneGraph = sceneGraph;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    #sceneGraph: VisorSceneNodeExtended;

    setEdgesVisibleAsync = async (enable?: boolean | null): Promise<void> => {
        this.#enabled = enable ?? !this.#enabled;
        await this.#sceneGraph.setEdgeVisibilityAsync(this.#enabled);
    };
}
