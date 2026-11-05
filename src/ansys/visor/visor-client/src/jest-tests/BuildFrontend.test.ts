import { buildFrontendAsync } from '../buildFrontendAsync';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';

/**
 * Scene details at the wrong schema version are rejected before any renderer
 * is created for them.
 *
 * Expected values are hand-written literals.
 */

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
});
