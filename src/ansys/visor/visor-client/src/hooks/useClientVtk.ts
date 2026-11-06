import { useEffect, useRef, useState } from 'react';
import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import type { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { ClientViewer } from '../frontend/ClientViewer';
import { VisorArgs } from './useVisorArgs';

/** What the client-mode hook gives App. */
export type ClientVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Connect the wasm scene over the given session, rebuild on each server update, and apply set_state; idle while trame is null. */
export function useClientVtk(visorArgs: VisorArgs, trame: Trame | null): ClientVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);
    const viewer = useRef<ClientViewer | null>(null);

    useEffect(() => {
        if (trame == null) {
            return;
        }
        (async () => {
            if (viewer.current == null) {
                viewer.current = await ClientViewer.connectAsync(
                    visorArgs,
                    trame,
                    (frontend, mismatch) => {
                        setSchemaMismatchError(mismatch);
                        setVisorFrontend(frontend);
                    }
                );
            }
        })();
    }, [trame]);

    return { visorFrontend, schemaMismatchError };
}
