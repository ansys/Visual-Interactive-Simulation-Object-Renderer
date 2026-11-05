import VtkScene from '../wasm/VtkScene';
import { type FrontendVtkObject } from '../wasm/RemoteVtkScene';

/** Widget edge as a fraction of the render window's shorter side. */
const SIZE_FRACTION = 0.15;

export class OrientationWidget {
    constructor(vtkScene: VtkScene, orientationWidgetWasmId: number) {
        this.#vtkScene = vtkScene;
        this.#widget = vtkScene.getVtkObject(orientationWidgetWasmId);
    }

    readonly #widget: FrontendVtkObject;
    readonly #vtkScene: VtkScene;

    /** Size the widget to SIZE_FRACTION of the render window's shorter side. */
    async fitToWindowAsync(): Promise<void> {
        const [width, height] = await this.#vtkScene.renderWindow.GetSize();
        const size = OrientationWidget.sizeForWindow(width, height);
        const representation = await this.#widget.GetRepresentation();
        await representation.SetSize([size, size]);
    }

    /** Square edge for a window of this size, rounded half up. */
    static sizeForWindow(width: number, height: number): number {
        return Math.floor(Math.min(width, height) * SIZE_FRACTION + 0.5);
    }
}
