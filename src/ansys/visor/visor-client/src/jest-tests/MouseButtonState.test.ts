import { MouseButtonState } from '../input/MouseButtonState';

/**
 * The held DOM buttons map to the one VTK button they drive together: a
 * middle press drives rotate (0), and pan (1) is the left and right chord.
 *
 * Expected values are hand-written literals.
 */

/** A state with each DOM button in `pressed` held, in order. */
function holding(...pressed: number[]): MouseButtonState {
    const state = new MouseButtonState();
    for (const button of pressed) {
        state.setButton(button, true);
    }
    return state;
}

describe('MouseButtonState', () => {
    test('left alone drives 0', () => {
        expect(holding(0).effectiveButton()).toBe(0);
    });

    test('right alone drives 2', () => {
        expect(holding(2).effectiveButton()).toBe(2);
    });

    test('left and right drive 1', () => {
        expect(holding(0, 2).effectiveButton()).toBe(1);
    });

    test('middle alone drives 0', () => {
        expect(holding(1).effectiveButton()).toBe(0);
    });

    test('left and middle drive 0', () => {
        expect(holding(0, 1).effectiveButton()).toBe(0);
    });

    test('nothing held drives null', () => {
        expect(holding().effectiveButton()).toBeNull();
    });

    test('releasing every held button drives null', () => {
        const state = holding(0, 1, 2);

        state.setButton(0, false);
        state.setButton(1, false);
        state.setButton(2, false);

        expect(state.effectiveButton()).toBeNull();
    });

    test('isDown reports only the button held', () => {
        const state = holding(1);

        expect([state.isDown(0), state.isDown(1), state.isDown(2)]).toEqual([false, true, false]);
    });
});
