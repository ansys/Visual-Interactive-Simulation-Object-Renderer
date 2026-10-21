import { render, screen } from '@testing-library/react';
import App from '../App';

/**
 * A scene-details payload at the wrong schema version is shown to the user as
 * a message in place of the scene, and no renderer is built for it.
 *
 * Expected values are hand-written literals.
 */

const mockCreateAsync = jest.fn();

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: async () => mockMakeWasmView() },
}));

jest.mock('../renderer/WasmRenderer', () => ({
    WasmRenderer: { createAsync: (...args: unknown[]) => mockCreateAsync(...args) },
}));

jest.mock('../components/UiScaffold.tsx', () => ({
    UiScaffold: () => null,
}));

/** The client-mode scene connection; its scene details carry schema version 3. */
function mockMakeWasmView() {
    return {
        trameGetState: () => false,
        clearObserversAndEventListeners: () => {},
        addServerUpdatedListener: () => () => {},
        addSetStateListener: () => () => {},
        trameTriggerAsync: async (name: string) =>
            name === 'get_visor_scene_details_json' ? { schemaVersion: 3 } : undefined,
        vtkScene: { resizeAsync: async () => undefined },
    };
}

afterEach(() => {
    delete (window as any).__visorState;
});

describe('App schema mismatch', () => {
    test('a version 3 payload shows the mismatch message and creates no renderer', async () => {
        render(<App />);

        const message = await screen.findByText(
            'Scene details schema version mismatch: payload is version 3, client expects version 4.'
        );

        expect(message).toBeTruthy();
        expect(mockCreateAsync).not.toHaveBeenCalled();
    });
});
