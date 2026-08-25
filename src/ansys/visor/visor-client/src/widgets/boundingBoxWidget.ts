import VtkScene from '../wasm/VtkScene';

function toNumericId(id: string | number | undefined, name = 'id'): number {
    if (id === undefined || id === null) {
        throw new Error(`Missing ${name}`);
    }
    const n = typeof id === 'number' ? id : Number(id);
    if (!Number.isFinite(n)) {
        throw new Error(`Invalid ${name}: ${id}`);
    }
    return n;
}

export class BoundingBoxWidget {
    constructor(
        vtkScene: VtkScene,
        sceneGraph: any,
        ids: {
            outlineActorId: string | number;
            axesActorId: string | number;
            boxAlgorithmWasmId: string | number;
            outlineQueryId?: string | number;
        }
    ) {
        const outlineQueryIdRaw = ids.outlineQueryId ?? ids.outlineActorId;

        // convert once and validate
        const outlineQueryId = toNumericId(outlineQueryIdRaw, 'outlineQueryId');
        const outlineActorId = toNumericId(ids.outlineActorId, 'outlineActorId');
        const axesActorId = toNumericId(ids.axesActorId, 'axesActorId');
        const boxAlgorithmWasmId = toNumericId(ids.boxAlgorithmWasmId, 'boxAlgorithmWasmId');
        const outlineQuery = vtkScene!.getVtkObject(outlineQueryId);
        const outlineActor = vtkScene!.getVtkObject(outlineActorId);
        const axesActor = vtkScene!.getVtkObject(axesActorId);
        const boxAlgorithm = vtkScene!.getVtkObject(boxAlgorithmWasmId);
        const self = this;

        async function setVisibilityAsync(visible?: boolean) {
            if (visible == null) {
                // query current visibility (legacy VTK api)
                const invokeResult = await outlineQuery.GetVisibility();
                const currentlyVisible = invokeResult === 1 || invokeResult === true;
                self.#enabled = !currentlyVisible;
            } else {
                self.#enabled = visible;
            }
            await outlineActor.SetVisibility(self.#enabled ? 1 : 0);
            await axesActor.SetVisibility(self.#enabled ? 1 : 0);
        }

        async function updateBoundsAsync() {
            let x_min = Number.MAX_SAFE_INTEGER;
            let x_max = Number.MIN_SAFE_INTEGER;
            let y_min = Number.MAX_SAFE_INTEGER;
            let y_max = Number.MIN_SAFE_INTEGER;
            let z_min = Number.MAX_SAFE_INTEGER;
            let z_max = Number.MIN_SAFE_INTEGER;

            const nodes = sceneGraph?.descendantActorNodesOrSelfArray ?? [];
            nodes.forEach((node: any) => {
                if (!node.visible) return;
                x_min = Math.min(x_min, node.bounds[0]);
                x_max = Math.max(x_max, node.bounds[1]);
                y_min = Math.min(y_min, node.bounds[2]);
                y_max = Math.max(y_max, node.bounds[3]);
                z_min = Math.min(z_min, node.bounds[4]);
                z_max = Math.max(z_max, node.bounds[5]);
            });

            const finalBounds = [x_min, x_max, y_min, y_max, z_min, z_max];
            await boxAlgorithm.SetBounds([finalBounds]);
        }

        this.setVisibilityAsync = setVisibilityAsync;
        this.updateBoundsAsync = updateBoundsAsync;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    setVisibilityAsync: (visible?: boolean) => Promise<void>;
    updateBoundsAsync: () => Promise<void>;
}
