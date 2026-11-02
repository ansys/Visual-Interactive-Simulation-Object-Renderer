import { WasmUpdateOptions } from '../wasm/WasmUpdateOptions';

/**
 * The server's update options decide whether an update rebuilds the frontend.
 *
 * The key is written here as a literal, never read from the class under test.
 */

describe('WasmUpdateOptions', () => {
    test('an object whose dataOnly is true does not rebuild', () => {
        expect(WasmUpdateOptions.parse({ dataOnly: true }).rebuildsFrontend).toBe(false);
    });

    test('an empty object rebuilds', () => {
        expect(WasmUpdateOptions.parse({}).rebuildsFrontend).toBe(true);
    });

    test('the load-time true rebuilds', () => {
        expect(WasmUpdateOptions.parse(true).rebuildsFrontend).toBe(true);
    });
});
