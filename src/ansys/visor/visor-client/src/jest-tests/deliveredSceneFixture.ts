import VisorSceneState from '../state/appstate/VisorSceneState.tsx';

/**
 * One delivered part record as the wire carries it, every field resolved:
 * shown, opaque, not selected, white, and not coloured by a variable.
 */
export function deliveredPart(
    id: number,
    overrides: Record<string, unknown> = {}
): Record<string, unknown> {
    return {
        id: id.toString(),
        visible: true,
        opacity: 1,
        selected: false,
        diffuseRgb: [1, 1, 1],
        colorVariable: null,
        ...overrides,
    };
}

/** A delivered scene holding the given part records in one dataset. */
export function deliveredScene(...parts: Record<string, unknown>[]): VisorSceneState {
    const partStates: Record<string, unknown> = {};
    for (const part of parts) {
        partStates[part.id as string] = part;
    }
    return new VisorSceneState({ datasetStates: { '0': { id: '0', partStates } } });
}

