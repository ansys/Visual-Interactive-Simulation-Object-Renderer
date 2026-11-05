import { UiScaffold, UiScaffoldUtil } from './components/UiScaffold.tsx';
import { CSSProperties, RefObject, useEffect, useRef } from 'react';
import { randomInt } from './utils/JsHelpers';
import { useVisorArgs } from './hooks/useVisorArgs';
import { useClientVtk } from './hooks/useClientVtk';
import { useRenderingMode } from './hooks/useRenderingMode';
import { useServerVtk } from './hooks/useServerVtk';

function App() {
    const visorArgs = useVisorArgs();
    const visorContainerStyle: CSSProperties =
        visorArgs.aspectRatio > 0
            ? {
                  position: 'relative',
                  aspectRatio: `${visorArgs.aspectRatio}`,
                  maxHeight: '100%',
                  margin: '0 auto',
              }
            : {
                  position: 'relative',
                  minHeight: '100px',
                  width: `100%`,
                  height: `100%`,
                  margin: '0 auto',
              };
    const uiScaffoldUtil: RefObject<UiScaffoldUtil> = useRef(null!);
    const probe = useRenderingMode(visorArgs.host, visorArgs.port);
    const client = useClientVtk(visorArgs, probe.mode === 'client');
    const server = useServerVtk(probe.mode === 'server' ? probe.trame : null, visorArgs);
    const active = probe.mode === 'server' ? server : client;
    const { visorFrontend: visorState, schemaMismatchError } = active;

    useEffect(() => {
        (async () => {
            if (visorState == null) {
                return;
            } else if (uiScaffoldUtil.current == null) {
                throw new Error(`uiScaffoldUtil.current should not be null here`);
            }
            (window as any).__visorState = visorState;
            //////////////////////////////////////////////////////////////////////////
            // Set UiScaffold params.
            uiScaffoldUtil.current.pixelDensity = visorArgs.pixelDensity;
        })();
        return () => {
            // Cleanup
            delete (window as any).__visorState;
        };
    }, [visorState]);

    return (
        <div style={visorContainerStyle}>
            {probe.error != null ? (
                <div>{probe.error.message}</div>
            ) : schemaMismatchError != null ? (
                <div>
                    {`Scene details schema version mismatch: payload is version ` +
                        `${schemaMismatchError.payloadVersion}, client expects version ` +
                        `${schemaMismatchError.expectedVersion}.`}
                </div>
            ) : (
                visorState != null && (
                    <UiScaffold
                        key={randomInt()}
                        visorState={visorState}
                        onLoad={(u) => {
                            uiScaffoldUtil.current = u;
                        }}
                    />
                )
            )}
        </div>
    );
}

export default App;
