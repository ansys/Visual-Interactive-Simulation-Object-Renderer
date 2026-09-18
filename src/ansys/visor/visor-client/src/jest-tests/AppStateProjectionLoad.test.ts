import { VisorFrontend } from '../VisorFrontend';
import type { IRenderer } from '../renderer/IRenderer';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';

/**
 * The projection load path: `setAppStateAsync` applies projection from
 * `camera.parallelProjection` alone, through the one call that also sets the
 * widget flag.
 *
 * Two persisted fields used to write the same wasm camera property --
 * `scene.orthographicEnabled` and `scene.camera.parallelProjection` -- both
 * pushed into one unordered promise array, with only the first also setting
 * the cached flag `getAppStateAsync` reads back. Which one won was
 * unspecified. This module pins that there is now exactly one writer, that it
 * is the one that sets the flag, and that the persisted toggle is ignored on
 * load.
 *
 * The fixture is deliberately self-contradictory: the camera says `true` and
 * the toggle says `false`. That is what makes the assertion pin *authority*
 * rather than plumbing -- with both branches live the double is called twice,
 * once with each value, and the call count fails.
 *
 * Two constraints the fixture depends on, stated because they are load-bearing
 * and not merely convenient:
 *
 *   1. It omits `ui.darkTheme`. The theme branch of `setAppStateAsync`
 *      `fetch`es two CSS files and appends to `document.head`; it is gated on
 *      `darkTheme !== undefined`, and omitting the key is what keeps this test
 *      off the network.
 *   2. It passes `updateUI: false`. With `true`, `setAppStateAsync` awaits
 *      `treeViewUtilPromise`, which nothing in this test ever resolves, and
 *      the call would hang rather than fail.
 */

/** Hand-written literals. The camera and the toggle disagree on purpose. */
const CAMERA_PARALLEL_PROJECTION = true;
const PERSISTED_ORTHOGRAPHIC_ENABLED = false;

/**
 * The minimum root scene-graph node `CreateVisorSceneGraph` accepts, which
 * `VisorFrontend`'s constructor builds the live graph from. No parts: the
 * per-part half of `setAppStateAsync` is not the subject here.
 */
function makeSceneGraphNode() {
    return {
        id: 0,
        dataArrays: [],
        name: '',
        isGroupNode: true,
        isActorNode: false,
        nodeType: 'root',
        diffuseColor: [1, 1, 1],
        bounds: [],
        children: [],
    };
}

/**
 * Every renderer member `VisorFrontend`'s constructor and `setAppStateAsync`
 * reach on this fixture's path. The two projection setters are the subject;
 * the rest are here so the call completes.
 */
function makeRendererDouble() {
    return {
        // Touched by the constructor.
        attachSceneGraph: jest.fn(),
        domElement: document.createElement('div'),
        addCameraSettledListener: jest.fn(() => jest.fn()),
        addViewerClickedListener: jest.fn(() => jest.fn()),
        // The two projection writers. Exactly one of these may be called.
        setOrthographicModeAsync: jest.fn(async () => undefined),
        setCameraParallelProjectionAsync: jest.fn(async () => undefined),
        // The other widget toggles, unused by this fixture but part of the
        // surface `setAppStateAsync` branches over.
        setCrossSectionVisibilityAsync: jest.fn(async () => undefined),
        setEdgeVisibilityGlobalAsync: jest.fn(async () => undefined),
        setBoundingBoxVisibilityAsync: jest.fn(async () => undefined),
        // The remaining camera setters.
        setCameraPositionAsync: jest.fn(async () => undefined),
        setCameraFocalPointAsync: jest.fn(async () => undefined),
        setCameraViewUpAsync: jest.fn(async () => undefined),
        setCameraClippingRangeAsync: jest.fn(async () => undefined),
        setCameraViewAngleAsync: jest.fn(async () => undefined),
        setCameraParallelScaleAsync: jest.fn(async () => undefined),
        // The cross-section plane setters.
        setCrossSectionOriginAsync: jest.fn(async () => undefined),
        setCrossSectionNormalAsync: jest.fn(async () => undefined),
        // Awaited at the end of setAppStateAsync.
        resizeAsync: jest.fn(async () => undefined),
    };
}

type RendererDouble = ReturnType<typeof makeRendererDouble>;

function makeFrontend(): { frontend: VisorFrontend; renderer: RendererDouble } {
    const renderer = makeRendererDouble();
    const frontend = new VisorFrontend(
        renderer as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        jest.fn(async () => undefined)
    );
    return { frontend, renderer };
}

describe('setAppStateAsync applies projection from the camera alone', () => {
    test('a parallel camera with a contradictory orthographicEnabled applies projection once, with true, through setOrthographicModeAsync', async () => {
        const { frontend, renderer } = makeFrontend();

        await frontend.setAppStateAsync(
            {
                scene: {
                    orthographicEnabled: PERSISTED_ORTHOGRAPHIC_ENABLED,
                    camera: { parallelProjection: CAMERA_PARALLEL_PROJECTION },
                },
            },
            false
        );

        expect(renderer.setOrthographicModeAsync).toHaveBeenCalledTimes(1);
        expect(renderer.setOrthographicModeAsync).toHaveBeenCalledWith(true);
        expect(renderer.setCameraParallelProjectionAsync).not.toHaveBeenCalled();
    });

    test('a state with no camera.parallelProjection applies no projection at all', async () => {
        // The persisted toggle is not a fallback. Reinstating it as one --
        // "read the camera, and the toggle when the camera is silent" --
        // passes the test above and fails here.
        const { frontend, renderer } = makeFrontend();

        await frontend.setAppStateAsync(
            {
                scene: {
                    orthographicEnabled: true,
                    camera: {},
                },
            },
            false
        );

        expect(renderer.setOrthographicModeAsync).not.toHaveBeenCalled();
        expect(renderer.setCameraParallelProjectionAsync).not.toHaveBeenCalled();
    });
});

