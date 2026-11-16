import VtkScene from '../wasm/VtkScene.js';

/**
 * Local mode remaps mouse buttons on their way to the VTK canvas, and stops
 * every press it remaps.  The click listeners hear the same element in the
 * bubble phase, so they see only the events the remap lets through: a left
 * click reaches them, a right click does not, and a release with nothing held
 * must always reach them.  A click reads nothing from the wasm scene.
 *
 * The scene is built over a fake remote scene: its canvas sits inside its
 * canvas div, and its renderer, camera and interactor are doubles.
 * `requestAnimationFrame` does nothing, so the frame-rate monitor never runs.
 *
 * Expected values are hand-written literals.
 */

let originalRequestAnimationFrame;
/**@type{VtkScene|null}*/
let scene = null;

beforeEach(() => {
    originalRequestAnimationFrame = globalThis.requestAnimationFrame;
    globalThis.requestAnimationFrame = () => 0;
});

afterEach(() => {
    scene?.clearObserversAndEventListeners();
    scene = null;
    globalThis.requestAnimationFrame = originalRequestAnimationFrame;
});

/** A scene over a fake remote scene whose canvas div is 200 x 100 at (0, 0). */
async function makeScene() {
    const canvasDiv = document.createElement('div');
    const canvas = document.createElement('canvas');
    canvasDiv.appendChild(canvas);
    canvasDiv.getBoundingClientRect = () => ({
        left: 0,
        top: 0,
        width: 200,
        height: 100,
        right: 200,
        bottom: 100,
        x: 0,
        y: 0,
    });
    const camera = { observe: () => undefined };
    const interactor = {};
    const remoteVtkScene = {
        renderer: { GetActiveCamera: async () => camera },
        renderWindow: { GetInteractor: async () => interactor },
        canvasDiv,
        canvas,
    };
    scene = await VtkScene.getInstanceAsync(null, remoteVtkScene);
    return { scene, canvas };
}

/** Dispatch a bubbling mouse event of type with DOM button on target at client (clientX, clientY). */
function mouse(target, type, button, clientX, clientY) {
    target.dispatchEvent(
        new MouseEvent(type, { button, clientX, clientY, bubbles: true, cancelable: true })
    );
}

/** Let any pending work finish. */
async function settle() {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('VtkScene mouse', () => {
    test('a left press and release at one point reaches each click listener once', async () => {
        const { scene, canvas } = await makeScene();
        const listener = jest.fn();
        scene.addCanvasClickListener(listener);

        mouse(canvas, 'mousedown', 0, 20, 30);
        mouse(canvas, 'mouseup', 0, 20, 30);
        await settle();

        expect(listener.mock.calls).toEqual([
            [{ normX: 0.1, normY: 0.7, ctrlKey: false, shiftKey: false }],
        ]);
    });

    test('a right press and release at one point does not reach the click listeners', async () => {
        const { scene, canvas } = await makeScene();
        const listener = jest.fn();
        scene.addCanvasClickListener(listener);

        mouse(canvas, 'mousedown', 2, 20, 30);
        mouse(canvas, 'mouseup', 2, 20, 30);
        await settle();

        expect(listener).not.toHaveBeenCalled();
    });

    test('a left and right press drives button 1 on the VTK canvas', async () => {
        const { canvas } = await makeScene();
        const pressed = [];
        canvas.addEventListener('mousedown', (e) => pressed.push(e.button));

        mouse(canvas, 'mousedown', 0, 20, 30);
        mouse(canvas, 'mousedown', 2, 20, 30);

        expect(pressed[pressed.length - 1]).toBe(1);
    });
});
