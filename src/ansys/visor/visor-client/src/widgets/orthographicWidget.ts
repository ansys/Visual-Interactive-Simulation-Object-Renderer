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
     * `#enabled` is initialised to `false` unconditionally at construction,
     * and nothing else reads the real camera except the toggle path. A
     * renderer built against a camera the server has already made parallel
     * would therefore report perspective, and `getAppStateAsync` reads that
     * cached flag -- so on a rebuild the wrong value is what gets saved.
     *
     * Awaited from `WasmRenderer.createAsync`, after the wasm state fetch has
     * completed, which is what makes the value read here the delivered one.
     */
    seedFromCameraAsync = async (): Promise<void> => {
        this.#enabled = await this.isOrthographicAsync();
    };

    isOrthographicAsync = async (): Promise<boolean> => {
        const result = await this.#vtkScene.camera.GetParallelProjection();
        return result === 1 || result === true;
    };
}
