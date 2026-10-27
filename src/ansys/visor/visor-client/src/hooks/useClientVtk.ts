import { useEffect, useRef, useState } from 'react';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import type { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { ClientViewer } from '../frontend/ClientViewer';
import { VisorArgs } from './useVisorArgs';

/** What the client-mode hook gives App. */
export type ClientVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Connect the wasm scene, rebuild the frontend on each server update, and apply set_state; idle until active. */
export function useClientVtk(visorArgs: VisorArgs, active: boolean): ClientVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);
    const viewer = useRef<ClientViewer | null>(null);

    useEffect(() => {
        if (!active) {
            return;
        }
        (async () => {
            if (viewer.current == null) {
                viewer.current = await ClientViewer.connectAsync(
                    visorArgs,
                    (frontend, mismatch) => {
                        setSchemaMismatchError(mismatch);
                        setVisorFrontend(frontend);
                    }
                );
            }
        })();
    }, [active]);

    return { visorFrontend, schemaMismatchError };
}
