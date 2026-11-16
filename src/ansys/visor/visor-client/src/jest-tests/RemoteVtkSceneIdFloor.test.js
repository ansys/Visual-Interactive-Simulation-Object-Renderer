import RemoteVtkScene from '../wasm/RemoteVtkScene.js';
import TrameInterface from '../wasm/TrameInterface.js';

/**
 * The browser and the server draw VTK object ids from one counter range.  Right after the wasm module loads,
 * and before any other wasm call, the scene registers one object at an explicit high id so every id the
 * browser allocates afterwards lands above the server's range.
 *
 * Expected values are hand-written literals.
 */

/** Every call the scene makes on the handler, in order. */
const mockCalls = [];

jest.mock('@kitware/vtk-wasm/remote', () => ({
    VtkWASMHandler: function VtkWASMHandler() {
        this.loaded = false;
        this.sceneManager = {
            updateObjectFromState: (state) => {
                mockCalls.push(['updateObjectFromState', state]);
                return true;
            },
            unRegisterState: (id) => mockCalls.push(['unRegisterState', id]),
            startEventLoop: () => true,
        };
        this.stateDecorator = (state) => state;
        this.bindNetwork = () => {};
        this.load = async () => {
            mockCalls.push(['load']);
            this.loaded = true;
        };
        this.bindCanvasToDOM = (_id, div) => {
            mockCalls.push(['bindCanvasToDOM']);
            div.appendChild(globalThis.document.createElement('canvas'));
        };
        this.update = async () => mockCalls.push(['update']);
        this.freeMemory = () => {};
        this.getVtkObject = (id) => {
            mockCalls.push(['getVtkObject', id]);
            return { id };
        };
    },
}));

jest.mock('../wasm/TrameInterface.js', () => ({
    __esModule: true,
    default: { getInstanceAsync: jest.fn() },
}));

jest.mock('../wasm/VtkScene.js', () => ({
    __esModule: true,
    default: { getInstanceAsync: jest.fn(async () => ({})) },
}));

async function loadScene() {
    TrameInterface.getInstanceAsync.mockResolvedValue({
        session: {},
        getState: (key) => (key === 'wasm_ids' ? { rendererId: 5, renderWindowId: 6 } : undefined),
        addSingleCallback: () => {},
    });
    return RemoteVtkScene.getInstanceAsync({
        trame: {},
        wasmIdsStateKey: 'wasm_ids',
        refNameStateKey: 'wasm_ref_name',
        wasmUrl: 'http://server/wasm',
        serverOrigin: 'http://server',
    });
}

describe('RemoteVtkScene id floor', () => {
    beforeEach(() => {
        mockCalls.length = 0;
    });

    test('the first wasm call after load registers one vtkPoints at id 1073741824, before any other call', async () => {
        await loadScene();

        expect(mockCalls[0]).toEqual(['load']);
        expect(mockCalls[1]).toEqual([
            'updateObjectFromState',
            { Id: 1073741824, ClassName: 'vtkPoints', SuperClassNames: ['vtkObject'] },
        ]);
    });
});
