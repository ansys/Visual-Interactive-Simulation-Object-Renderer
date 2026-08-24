import { ensureNumber, StateInput } from './VisorStateCommon.tsx';
import VisorVtkInfo from './vtkInfo/VisorVtkInfo.tsx';
import VisorAppState from './VisorAppState.tsx';

/**
 * Must equal SCENE_DETAILS_SCHEMA_VERSION on the Python side
 * (`ansys.visor.viewer.models.runtime.visor_scene_details`). Bumped whenever
 * the scene-details wire shape changes incompatibly. See proposal §2.
 */
export const SCENE_DETAILS_SCHEMA_VERSION = 2;

/**
 * Thrown when the payload's `schemaVersion` does not match the client's
 * compiled-in `SCENE_DETAILS_SCHEMA_VERSION`. Distinguishable from every
 * other parse-time error so `App.tsx` can catch this case, and only this
 * case. See proposal §2.2.
 */
export class SchemaVersionMismatchError extends Error {
    constructor(payloadVersion: number, expectedVersion: number) {
        super(
            `Scene details schema version mismatch: payload is version ${payloadVersion}, ` +
                `client expects version ${expectedVersion}.`
        );
        this.name = `SchemaVersionMismatchError`;
        this.payloadVersion = payloadVersion;
        this.expectedVersion = expectedVersion;
    }

    readonly payloadVersion: number;
    readonly expectedVersion: number;
}

export default class VisorSceneDetails {
    constructor(json_or_object: StateInput<VisorSceneDetails> = null) {
        const obj =
            typeof json_or_object === `string` ? JSON.parse(json_or_object) : json_or_object;
        // First statement, ahead of every sub-parse: see proposal §2.1.
        ensureNumber(obj.schemaVersion, `schemaVersion`);
        if (obj.schemaVersion !== SCENE_DETAILS_SCHEMA_VERSION) {
            throw new SchemaVersionMismatchError(obj.schemaVersion, SCENE_DETAILS_SCHEMA_VERSION);
        }
        this.schemaVersion = obj.schemaVersion;
        this.appState = new VisorAppState(obj.appState);
        this.vtkInfo = new VisorVtkInfo(obj.vtkInfo);
    }

    schemaVersion: number;
    appState: VisorAppState;
    vtkInfo: VisorVtkInfo;
}
