import { FC, useEffect } from 'react';
import { VisorFrontend } from '../../VisorFrontend.tsx';
import { VisorSceneNodeExtended } from '../../state/VisorSceneGraph.tsx';
import { randomId } from '../../utils/JsHelpers';

export type ContextMenuUtil = {};

export type ContextMenuOptions = {
    node: VisorSceneNodeExtended | null;
    x: number;
    y: number;
};

export const ContextMenu: FC<{
    visorState: VisorFrontend;
    onLoad: (util: ContextMenuUtil) => void;
    options?: ContextMenuOptions | null;
}> = ({ onLoad, options }) => {
    const contextMenuElemId = randomId();
    const { node, x, y } = options ?? {
        node: null,
        x: 0,
        y: 0,
    };
    useEffect(() => {
        const contextMenuElem = document.getElementById(contextMenuElemId) as HTMLDivElement;
        onLoad({});
    }, []);

    return (
        <div
            id={contextMenuElemId}
            className={'theme-panel-1'}
            style={{
                display: `${node == null ? 'none' : 'block'}`,
                whiteSpace: 'nowrap',
                position: 'absolute',
                zIndex: '2',
                left: `${x * 100}%`,
                top: `${y * 100}%`,
            }}
        >
            {node != null && (
                <table>
                    <tbody>
                        <tr>
                            <th style={{ textAlign: 'right' }}>ID:</th>
                            <td style={{ paddingLeft: '10px' }}>{node.id}</td>
                        </tr>
                        <tr style={{ borderTopWidth: '4px', borderColor: 'transparent' }}>
                            <th style={{ textAlign: 'right' }}>Type:</th>
                            <td style={{ paddingLeft: '10px' }}>{node.nodeType}</td>
                        </tr>
                        <tr style={{ borderTopWidth: '4px', borderColor: 'transparent' }}>
                            <th style={{ textAlign: 'right' }}>Name:</th>
                            <td style={{ paddingLeft: '10px' }}>{node.name}</td>
                        </tr>
                    </tbody>
                </table>
            )}
        </div>
    );
};
