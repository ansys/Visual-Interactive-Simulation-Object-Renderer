import VisorPartState from '../state/appstate/VisorPartState.tsx';

describe('a part state parses the delivered colorVariable', () => {
    test('a nested colorVariable parses onto the node reference', () => {
        const part = new VisorPartState({
            id: '1',
            colorVariable: { variableId: 'POINT::pressure::1', variableComponent: 2 },
        });

        expect(part.variableId).toBe('POINT::pressure::1');
        expect(part.variableComponent).toBe(2);
    });

    test('a null colorVariable parses as no reference', () => {
        const part = new VisorPartState({ id: '1', colorVariable: null });

        expect(part.variableId).toBeNull();
        expect(part.variableComponent).toBeUndefined();
    });
});

