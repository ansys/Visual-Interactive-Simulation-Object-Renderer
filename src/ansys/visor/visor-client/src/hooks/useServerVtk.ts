import { useEffect, useState } from 'react';
import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import type { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { ServerViewer } from '../frontend/ServerViewer';
import type { VisorArgs } from './useVisorArgs';

/** What the server-mode hook gives App. */
export type ServerVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Over the probe's session: stream frames, and rebuild the frontend on every scene_version change; idle when trame is null. */
export function useServerVtk(trame: Trame | null, visorArgs: VisorArgs): ServerVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);

    useEffect(() => {
        if (trame == null) {
            return;
        }
        // Under StrictMode the effect runs twice in development: each run
        // disposes only the viewer it created, and a build that finishes
        // after dispose disposes its own renderer.
        const viewer = new ServerViewer(trame, visorArgs.darkMode, (frontend, mismatch) => {
            setSchemaMismatchError(mismatch);
            setVisorFrontend(frontend);
        });
        return () => viewer.dispose();
    }, [trame]);

    return { visorFrontend, schemaMismatchError };
}
