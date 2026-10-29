import { render, waitFor } from '@testing-library/react';
import App from '../App';

/**
 * A `darkMode` passed by the host page wins over the theme the server
 * delivers: the stylesheet applied when the scene is first built is the one
 * for the page's theme.
 *
 * Expected values are hand-written literals.
 */

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: async () => mockMakeWasmView() },
}));

jest.mock('../renderer/WasmRenderer', () => ({
    WasmRenderer: { createAsync: async () => mockMakeRenderer() },
}));

jest.mock('../components/UiScaffold.tsx', () => ({
    UiScaffold: (props: { onLoad: (util: object) => void }) => {
        props.onLoad({});
        return null;
    },
}));

/** A minimal v4 scene-details payload whose delivered theme is light. */
function mockSceneDetailsPayload() {
    return {
        schemaVersion: 4,
        ui: { darkTheme: false },
        scene: { unit: '', orthographicEnabled: null },
        vtkInfo: {
            sceneGraph: {
                id: 0,
                dataArrays: [],
                name: '',
                isGroupNode: true,
                isActorNode: false,
                nodeType: 'root',
                diffuseColor: [1, 1, 1],
                bounds: [],
                children: [],
            },
            rendererAnnotation: {
                rendererKind: 'wasm',
                nodes: {},
                widgets: {
                    orientationWidgetId: 1,
                    crossSectionPlaneId: 2,
                    crossSectionPlaneWidgetId: 3,
                    crossSectionPlaneRepresentationId: 4,
                    boundingBoxAlgorithmId: 5,
                    boundingBoxOutlineActorId: 6,
                    boundingBoxAxesActorId: 7,
                },
            },
        },
    };
}

/** The client-mode scene connection; it delivers the light-themed payload. */
function mockMakeWasmView() {
    return {
        trameGetState: () => false,
        clearObserversAndEventListeners: () => {},
        addServerUpdatedListener: () => () => {},
        addSetStateListener: () => () => {},
        trameTriggerAsync: async (name: string) =>
            name === 'get_visor_scene_details_json' ? mockSceneDetailsPayload() : undefined,
        vtkScene: { resizeAsync: async () => undefined },
    };
}

/** The renderer members the build and the state seed reach. */
function mockMakeRenderer() {
    return {
        domElement: document.createElement('div'),
        addCameraSettledListener: () => () => {},
        addViewerClickedListener: () => () => {},
        resizeAsync: async () => undefined,
    };
}

const globals = globalThis as unknown as { fetch: unknown };
let originalFetch: unknown;

beforeEach(() => {
    (window as any).__visorArgs = { darkMode: true };
    // jsdom has no `fetch`; each theme stylesheet is served as a marker string.
    originalFetch = globals.fetch;
    globals.fetch = jest.fn(async (url: string) => ({
        text: async () => (url.endsWith('theme-dark.css') ? 'dark-sheet' : 'light-sheet'),
    }));
});

afterEach(() => {
    globals.fetch = originalFetch;
    document.getElementById('__visorThemeStyle')?.remove();
    delete (window as any).__visorArgs;
    delete (window as any).__visorState;
});

describe('App darkMode override', () => {
    test('a darkMode prop applies its theme over the delivered darkTheme', async () => {
        render(<App />);

        await waitFor(() =>
            expect(document.getElementById('__visorThemeStyle')?.innerHTML).toBe('dark-sheet')
        );
    });
});
