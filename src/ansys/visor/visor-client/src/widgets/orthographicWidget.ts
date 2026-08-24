import VtkScene from '../wasm/VtkScene';

export class OrthographicWidget {
    constructor(vtkScene: VtkScene) {
        this.#vtkScene = vtkScene;
    }

    #enabled: boolean = false;
    get enabled() {
        return this.#enabled;
    }

    #vtkScene: VtkScene;

    setOrthographicModeAsync = async (enable?: boolean | null): Promise<void> => {
        if (enable == null) {
            enable = !(await this.isOrthographicAsync());
        }
        if ((this.#enabled = enable)) {
            await this.#vtkScene.camera.ParallelProjectionOn();
        } else {
            await this.#vtkScene.camera.ParallelProjectionOff();
        }
    };

    isOrthographicAsync = async (): Promise<boolean> => {
        const result = await this.#vtkScene.camera.GetParallelProjection();
        return result === 1 || result === true;
    };
}
