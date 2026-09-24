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

/**
 * createCrossSectionWidget encapsulates cross-section widget operations:
 * - toggling visibility (queries widget for authoritative state when toggling)
 * - checking enabled state
 * - an interaction handler that copies origin/normal from the widget representation to the plane and triggers a render
 * - updateBoundsAsync is provided as a placeholder (keeps parity with bounding-box API)
 */
export class CrossSectionWidget {
    constructor(
        vtkScene: VtkScene,
        ids: {
            planeWasmId: string | number;
            representationWasmId: string | number;
            widgetWasmId: string | number;
        }
    ) {
        const planeId = toNumericId(ids.planeWasmId, 'planeWasmId');
        const repId = toNumericId(ids.representationWasmId, 'representationWasmId');
        const widgetId = toNumericId(ids.widgetWasmId, 'widgetWasmId');
        const widget = vtkScene.getVtkObject(widgetId);
        const plane = vtkScene.getVtkObject(planeId);
        const rep = vtkScene.getVtkObject(repId);
        this.#rep = rep;
        this.#plane = plane;
        this.setVisibilityAsync = async (visible) => {
            this.#enabled = visible ?? !this.#enabled;
            if (this.#enabled) {
                await widget.On();
            } else {
                await widget.Off();
            }
        };
        this.updateBoundsAsync = async () => {
            // placeholder: cross-section bounds logic is currently empty in the original code
            // keep a no-op to preserve API parity; implement later if needed
            return;
        };
        this.interactionHandler = async (/* event */) => {
            // copy origin & normal from representation to the underlying plane and render
            try {
                const origin = await rep.GetOrigin();
                const normal = await rep.GetNormal();
                await plane.SetOrigin(origin);
                await plane.SetNormal(normal);
                vtkScene.render();
            } catch (e) {
                // keep failures non-fatal (mirrors previous behavior)
                console.debug('[CrossSectionWidget] interaction handler failed', e);
            }
        };
    }

    #rep: any;
    #plane: any;
    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    getOriginAsync: () => Promise<number[]> = async () => {
        return await this.#rep.GetOrigin();
    };
    getNormalAsync: () => Promise<number[]> = async () => {
        return await this.#rep.GetNormal();
    };
    /**
     * Write a plane to **both** objects: the representation first, then the
     * plane.
     *
     * The two setters below and the two getters above are deliberately no
     * longer symmetric in what they touch. The getters read the
     * representation, because that is the object the draggable handle moves.
     * The setters write the representation *and* the plane, because the
     * representation is the handle and the plane is the clip function every
     * pipeline holds, and a write that reached only one of them left the two
     * disagreeing: a load set the clip while the handle stayed where it was,
     * and the next end-of-drag report then carried that stale handle to the
     * server.
     *
     * Representation first, plane second, matching the order the server's own
     * `VisorCrossSectionWidget.set_origin` / `set_normal` write them in. The
     * order is consistency with the server rather than a correctness
     * requirement of its own -- these are two independent objects and neither
     * write feeds the other.
     */
    setOriginAsync: (origin: number[]) => Promise<void> = async (origin) => {
        await this.#rep.SetOrigin(origin);
        await this.#plane.SetOrigin(origin);
    };
    setNormalAsync: (normal: number[]) => Promise<void> = async (normal) => {
        await this.#rep.SetNormal(normal);
        await this.#plane.SetNormal(normal);
    };
    setVisibilityAsync: (visible?: boolean) => Promise<void>;
    updateBoundsAsync: () => Promise<void>;
    interactionHandler: (event?: any) => Promise<void>;
}
