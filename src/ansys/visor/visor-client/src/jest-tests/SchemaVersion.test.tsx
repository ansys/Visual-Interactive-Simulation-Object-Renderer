import VisorSceneDetails, {
    SchemaVersionMismatchError,
    SCENE_DETAILS_SCHEMA_VERSION,
} from '../state/appstate/VisorSceneDetails.tsx';
import { parseRendererAnnotation, requireWasmAnnotation } from '../renderer/RendererAnnotation';

describe('SchemaVersion', () => {
    test('mismatched schemaVersion throws SchemaVersionMismatchError before any sub-parse, carrying both versions', () => {
        const payloadVersion = SCENE_DETAILS_SCHEMA_VERSION + 1;
        const badPayload = {
            schemaVersion: payloadVersion,
            // Deliberately malformed: if the version check ran after any
            // sub-parse, this would throw a plain TypeError first instead.
            appState: undefined,
            vtkInfo: undefined,
        };
        let thrown: unknown = null;
        try {
            new VisorSceneDetails(badPayload);
        } catch (err) {
            thrown = err;
        }
        expect(thrown).toBeInstanceOf(SchemaVersionMismatchError);
        const error = thrown as SchemaVersionMismatchError;
        expect(error.payloadVersion).toBe(payloadVersion);
        expect(error.expectedVersion).toBe(SCENE_DETAILS_SCHEMA_VERSION);
    });

    test('parseRendererAnnotation returns null for a null or undefined annotation', () => {
        expect(parseRendererAnnotation(null)).toBeNull();
        expect(parseRendererAnnotation(undefined)).toBeNull();
    });

    test('parseRendererAnnotation survives every field of a fully populated wasm annotation, by name and value', () => {
        const wireAnnotation = {
            rendererKind: 'wasm',
            nodes: {
                '5': { actorId: 10, propertyId: 11, mapperId: 12 },
            },
            widgets: {
                orientationWidgetId: 1,
                crossSectionPlaneId: 2,
                crossSectionPlaneWidgetId: 3,
                crossSectionPlaneRepresentationId: 4,
                boundingBoxAlgorithmId: 5,
                boundingBoxOutlineActorId: 6,
                boundingBoxAxesActorId: 7,
            },
        };
        const parsed = requireWasmAnnotation(parseRendererAnnotation(wireAnnotation));

        expect(parsed.rendererKind).toBe('wasm');

        // The three node handle fields.
        expect(parsed.nodes['5'].actorId).toBe(10);
        expect(parsed.nodes['5'].propertyId).toBe(11);
        expect(parsed.nodes['5'].mapperId).toBe(12);

        // All seven widget fields.
        expect(parsed.widgets.orientationWidgetId).toBe(1);
        expect(parsed.widgets.crossSectionPlaneId).toBe(2);
        expect(parsed.widgets.crossSectionPlaneWidgetId).toBe(3);
        expect(parsed.widgets.crossSectionPlaneRepresentationId).toBe(4);
        expect(parsed.widgets.boundingBoxAlgorithmId).toBe(5);
        expect(parsed.widgets.boundingBoxOutlineActorId).toBe(6);
        expect(parsed.widgets.boundingBoxAxesActorId).toBe(7);
    });

    test('requireWasmAnnotation throws when the annotation is absent (null)', () => {
        expect(() => requireWasmAnnotation(null)).toThrow(TypeError);
    });
});
