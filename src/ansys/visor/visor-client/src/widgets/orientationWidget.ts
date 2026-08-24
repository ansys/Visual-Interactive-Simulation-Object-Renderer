import VtkScene from '../wasm/VtkScene';
import { type FrontendVtkObject } from '../wasm/RemoteVtkScene';

export class OrientationWidget {
    constructor(vtkScene: VtkScene, orientationWidgetWasmId: number) {
        this.#vtkScene = vtkScene;
        this.widget = vtkScene.getVtkObject(orientationWidgetWasmId);
    }

    widget: FrontendVtkObject;
    #rep: FrontendVtkObject;
    #vtkScene: VtkScene;
    resizeAsync = async (widgetSize?: number) => {
        this.#rep ??= await this.widget.GetRepresentation();
        if (widgetSize == null) {
            const windowSize = await this.#vtkScene.renderWindow.GetSize();
            widgetSize = Math.round(Math.min(windowSize[0], windowSize[1]) * 0.13);
        }
        await this.#rep.SetSize([widgetSize, widgetSize]);
    };
}
