import { Trame } from '@kitware/trame/src/trame.js';
import TrameInterface from '../wasm/TrameInterface.js';

/**
 * `TrameInterface` wraps the session it is given: the server's calls on the
 * ref name reach the callbacks added to the wrapper through that session's
 * `refs`, and the wrapper opens no connection of its own.
 *
 * Expected values are hand-written literals.
 */

jest.mock('@kitware/trame/src/trame.js', () => ({
    Trame: jest.fn(),
}));

/** A connected session whose state names the ref the server calls. */
function makeSession() {
    return {
        refs: {},
        client: { getConnection: () => ({ getSession: () => ({}) }) },
        state: { get: (key) => (key === 'wasm_ref_name' ? 'visor_wasm' : undefined) },
    };
}

describe('TrameInterface', () => {
    test('wraps the given connection: its refs reach the callbacks and no Trame is constructed', async () => {
        const session = makeSession();
        const update = () => {};

        const wrapper = await TrameInterface.getInstanceAsync(session, 'wasm_ref_name');
        wrapper.addSingleCallback('update', update);

        expect(session.refs['visor_wasm'].update).toBe(update);
        expect(Trame).not.toHaveBeenCalled();
    });
});
