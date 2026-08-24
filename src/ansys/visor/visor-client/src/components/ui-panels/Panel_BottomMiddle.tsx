import { FC, RefObject, useEffect, useRef } from 'react';
import { AwcIcons } from '../AwcIcons';
import { VisorFrontend } from '../../VisorFrontend.tsx';
import { makeTooltip } from '../../utils/Tooltip';

export type Panel_BottomMiddle_Util = {};

export const Panel_BottomMiddle: FC<{
    visorState: VisorFrontend;
    onLoad: (util: Panel_BottomMiddle_Util) => void;
}> = ({ visorState, onLoad }) => {
    const edgeVisibility: RefObject<boolean> = useRef(false);
    const tableElemId = `tableElem-${crypto.randomUUID()}`;
    const selectionModeContainerId = `selMode-${crypto.randomUUID()}`;
    useEffect(() => {
        const perspectiveOrthographicButton = AwcIcons.getWatchIcon(null, 5, true, [
            'theme-hover-background-3',
        ]);
        const crossSectionButton = AwcIcons.getSinglePlaneIcon(null, 5, true, [
            'theme-hover-background-3',
        ]);
        const wireFrameButton = AwcIcons.getMeshIcon(null, 5, true, ['theme-hover-background-3']);
        const getFullScreenButton = AwcIcons.getExpandIcon(null, 5, true, [
            'theme-hover-background-3',
        ]);
        const boundingBoxButton = AwcIcons.getModelerIcon(null, 5, true, [
            'theme-hover-background-3',
        ]);
        const tableElem = document.getElementById(tableElemId) as HTMLTableElement;
        const cells = tableElem.rows[0].cells;
        //////////////////////////
        // get references to <td> elements
        const perspectiveOrthographicCell = cells[0];
        const crossSectionCell = cells[1];
        const wireFrameCell = cells[2];
        const getFullScreenCell = cells[3];
        const boundingBoxCell = cells[4];
        //////////////////////////
        // append buttons to <td> elements
        perspectiveOrthographicCell.appendChild(perspectiveOrthographicButton);
        crossSectionCell.appendChild(crossSectionButton);
        wireFrameCell.appendChild(wireFrameButton);
        getFullScreenCell.appendChild(getFullScreenButton);
        boundingBoxCell.appendChild(boundingBoxButton);
        //////////////////////////
        // set tooltips
        const cleanupFuncs = [
            makeTooltip(perspectiveOrthographicButton, 'Perspective / Orthographic'),
            makeTooltip(crossSectionButton, 'Cross-section'),
            makeTooltip(wireFrameButton, 'Edges / Wireframe'),
            makeTooltip(getFullScreenButton, 'Fullscreen'),
            makeTooltip(boundingBoxButton, 'Bounding Box'),
        ];
        //////////////////////////
        // set onclick events on buttons
        perspectiveOrthographicCell.onclick = async () => {
            await visorState.setOrthographicModeAsync();
            await visorState.render();
        };
        crossSectionCell.onclick = async () => {
            await visorState.setCrossSectionVisibilityAsync();
            await visorState.render();
        };
        wireFrameCell.onclick = async () => {
            await visorState.setEdgeVisibilityAsync();
            await visorState.render();
        };
        getFullScreenCell.onclick = async () => {
            await visorState.toggleFullScreenAsync();
        };
        boundingBoxCell.onclick = async () => {
            await visorState.setBoundingBoxVisibilityAsync();
            await visorState.render();
        };

        //////////////////////////
        // Selection mode widget
        const selModeContainer = document.getElementById(
            selectionModeContainerId
        ) as HTMLDivElement;
        type SelectionMode = 'part' | 'vertex' | 'edge' | 'face';

        const modeIconFactories: Record<SelectionMode, () => HTMLElement> = {
            part: () => AwcIcons.getGeometryPartIcon(null, 5, true, ['theme-hover-background-3']),
            edge: () => AwcIcons.getGeometryEdgeIcon(null, 5, true, ['theme-hover-background-3']),
            face: () => AwcIcons.getGeometryFaceIcon(null, 5, true, ['theme-hover-background-3']),
            vertex: () =>
                AwcIcons.getGeometryVertexIcon(null, 5, true, ['theme-hover-background-3']),
        };
        const modeLabels: Record<SelectionMode, string> = {
            part: 'Select Part',
            edge: 'Select Edge',
            face: 'Select Face',
            vertex: 'Select Vertex',
        };

        // The currently displayed icon button
        let currentModeButton: HTMLElement = modeIconFactories.part();
        makeTooltip(currentModeButton, modeLabels.part);
        selModeContainer.appendChild(currentModeButton);

        // Floating popup – appended to <body> so it escapes overflow:auto containers
        const popup = document.createElement('div');
        popup.className = 'theme-panel-1';
        popup.style.cssText = `
            position: fixed;
            display: none;
            flex-direction: row;
            gap: 2px;
            padding: 6px;
            border-radius: 4px;
            z-index: 1000;
            white-space: nowrap;
        `;
        document.body.appendChild(popup);

        const subModes: SelectionMode[] = ['edge', 'face', 'vertex'];
        const popupCleanupFuncs: Array<() => void> = [];
        for (const mode of subModes) {
            const btn = modeIconFactories[mode]();
            popupCleanupFuncs.push(makeTooltip(btn, modeLabels[mode]));
            btn.onclick = (e) => {
                e.stopPropagation();
                popup.style.display = 'none';
                selectMode(mode);
            };
            popup.appendChild(btn);
        }

        let popupOpen = false;

        function selectMode(mode: SelectionMode) {
            // Reset current-mode button
            currentModeButton.remove();
            currentModeButton = modeIconFactories[mode]();
            makeTooltip(currentModeButton, modeLabels[mode]);
            selModeContainer.appendChild(currentModeButton);
            popupOpen = false;
            popup.style.display = 'none';

            currentModeButton.onclick = (e) => {
                e.stopPropagation();
                if (mode === 'part') {
                    togglePopup();
                } else {
                    // clicking again resets to part
                    selectMode('part');
                }
            };

            visorState.setSelectionMode(mode);
        }

        function togglePopup() {
            popupOpen = !popupOpen;
            if (popupOpen) {
                popup.style.display = 'flex';
                // Position above the current mode button
                const rect = currentModeButton.getBoundingClientRect();
                popup.style.left = `${rect.left + rect.width / 2}px`;
                popup.style.top = `${rect.top}px`;
                popup.style.transform = 'translateX(-50%) translateY(-100%) translateY(-4px)';
            } else {
                popup.style.display = 'none';
            }
        }

        currentModeButton.onclick = (e) => {
            e.stopPropagation();
            togglePopup();
        };

        const closePopupOnOutsideClick = (e: MouseEvent) => {
            if (!selModeContainer.contains(e.target as Node)) {
                popup.style.display = 'none';
                popupOpen = false;
            }
        };
        document.addEventListener('click', closePopupOnOutsideClick);

        cleanupFuncs.push(...popupCleanupFuncs);
        cleanupFuncs.push(() => document.removeEventListener('click', closePopupOnOutsideClick));
        cleanupFuncs.push(() => popup.remove());
        //////////////////////////
        onLoad({});
        //////////////////////////
        return () => {
            for (const func of cleanupFuncs) {
                func();
            }
        };
    }, []);

    return (
        <div style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <table className={''} id={tableElemId} style={{}}>
                <tbody>
                    <tr>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
            <div
                id={selectionModeContainerId}
                style={{ display: 'inline-block', verticalAlign: 'top' }}
            ></div>
        </div>
    );
};
