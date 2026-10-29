import { buildFrontendAsync } from '../buildFrontendAsync';
import { NullRenderer } from '../renderer/NullRenderer';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';

/**
 * Scene details at the wrong schema version are rejected before any renderer
 * is created for them.  A build clears the new renderer's geometry highlight
 * once.
 *
 * Expected values are hand-written literals.
 */

/** A minimal v4 scene-details payload with no renderer annotation. */
function sceneDetailsPayload() {
    return {
        schemaVersion: 4,
        ui: {},
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
            rendererAnnotation: null,
        },
    };
}

describe('buildFrontendAsync', () => {
    test('scene details at schema version 3 reject with SchemaVersionMismatchError before any renderer is created', async () => {
        const createRenderer = jest.fn();
        const sender = jest.fn(async () => undefined);

        let thrown: unknown = null;
        try {
            await buildFrontendAsync('{"schemaVersion":3}', createRenderer, sender, undefined);
        } catch (err) {
            thrown = err;
        }

        expect(thrown).toBeInstanceOf(SchemaVersionMismatchError);
        const error = thrown as SchemaVersionMismatchError;
        expect(error.payloadVersion).toBe(3);
        expect(error.expectedVersion).toBe(4);
        expect(createRenderer).not.toHaveBeenCalled();
    });

    test("a build clears the renderer's geometry highlight once", async () => {
        const renderer = new NullRenderer();
        const clear = jest.spyOn(renderer, 'clearGeometryHighlight');
        const sender = jest.fn(async () => undefined);

        await buildFrontendAsync(sceneDetailsPayload(), async () => renderer, sender, undefined);

        expect(clear).toHaveBeenCalledTimes(1);
    });
});
