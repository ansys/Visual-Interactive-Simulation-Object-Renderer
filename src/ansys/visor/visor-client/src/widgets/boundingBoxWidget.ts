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
    /** Toggle the bounding-box outline and axes. */
    constructor(
        vtkScene: VtkScene,
        ids: {
            outlineActorId: string | number;
            axesActorId: string | number;
            outlineQueryId: string | number;
        }
    ) {
        // convert once and validate
        const outlineQueryId = toNumericId(ids.outlineQueryId, 'outlineQueryId');
        const outlineActorId = toNumericId(ids.outlineActorId, 'outlineActorId');
        const axesActorId = toNumericId(ids.axesActorId, 'axesActorId');
        const outlineQuery = vtkScene!.getVtkObject(outlineQueryId);
        const outlineActor = vtkScene!.getVtkObject(outlineActorId);
        const axesActor = vtkScene!.getVtkObject(axesActorId);
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

        this.setVisibilityAsync = setVisibilityAsync;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    setVisibilityAsync: (visible?: boolean) => Promise<void>;
}
