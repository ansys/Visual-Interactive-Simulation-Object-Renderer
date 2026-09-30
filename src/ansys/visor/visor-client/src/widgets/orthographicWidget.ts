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

    /**
     * Seed the cached flag from the wasm camera.
     *
     * `#enabled` starts `false` unconditionally, and only the toggle path
     * otherwise reads the real camera. Without this seed, a renderer built
     * against a camera the server already made parallel would report
     * perspective, and `getAppStateAsync` would save that wrong cached value.
     *
     * Awaited from `WasmRenderer.createAsync`, after the wasm state fetch
     * completes, so the value read here is the delivered one.
     */
    seedFromCameraAsync = async (): Promise<void> => {
        this.#enabled = await this.isOrthographicAsync();
    };

    isOrthographicAsync = async (): Promise<boolean> => {
        const result = await this.#vtkScene.camera.GetParallelProjection();
        return result === 1 || result === true;
    };
}
