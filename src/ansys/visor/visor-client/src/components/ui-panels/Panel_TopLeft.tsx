import { FC, RefObject, useEffect, useRef } from 'react';
import { TreeView, TreeViewUtil } from '../../treeview/TreeView.tsx';
import { VisorFrontend } from '../../VisorFrontend.tsx';
import { VisorSceneNodeExtended } from '../../state/VisorSceneGraph.tsx';
import { AwcIcons } from '../AwcIcons';
import { Panel_TopLeft_Util } from './Panel_TopLeft_Util.tsx';
import { getRootFontSize, randomId } from '../../utils/JsHelpers';

export const Panel_TopLeft: FC<{
    visorState: VisorFrontend;
    onLoad: (util: Panel_TopLeft_Util) => void;
}> = ({ visorState, onLoad }) => {
    const treeViewUtil: RefObject<TreeViewUtil<VisorSceneNodeExtended>> = useRef(null!);
    const reactComponentContainerId = randomId();
    const collapseButtonContainerId = randomId();
    const treeViewContainerId = randomId();
    useEffect(() => {
        const reactComponentContainer = document.getElementById(
            reactComponentContainerId
        ) as HTMLDivElement;
        const collapseButtonContainer = document.getElementById(
            collapseButtonContainerId
        ) as HTMLTableCellElement;
        const treeViewContainer = document.getElementById(treeViewContainerId) as HTMLDivElement;
        treeViewUtil.current.addSelectionChangeListener((selectedNodes) => {
            (async () => {
                for (const node of visorState.sceneGraph.descendantActorNodesOrSelfArray) {
                    await node.setSelectedAsync(false);
                }
                for (const node of selectedNodes) {
                    await node.setSelectedAsync(true);
                }
                await visorState.render();
            })();
        });
        treeViewUtil.current.addVisibilityChangeListener((visibleNodes) => {
            (async () => {
                for (const node of visorState.sceneGraph.descendantActorNodesOrSelfArray) {
                    await node.setVisibilityAsync(false);
                }
                for (const node of visibleNodes) {
                    await node.setVisibilityAsync(true);
                }
                // await visorState.updateBoundingBoxBoundsAsync();
                await visorState.render();
            })();
        });
        const fontSize: number = getRootFontSize(14);
        const collapseButton = AwcIcons.getArrowHeadDownIcon(fontSize * 1.2, 3, true, [
            'theme-hover-background-3',
        ]) as HTMLButtonElement;
        const expandButton = AwcIcons.getArrowHeadUpIcon(fontSize * 1.2, 3, true, [
            'theme-hover-background-3',
        ]) as HTMLButtonElement;
        let isPanelCollapsed = false;
        collapseButton.onclick = (e) => {
            reactComponentContainer.style.width = `${reactComponentContainer.offsetWidth}px`;
            treeViewContainer.style.display = 'none';
            collapseButton.remove();
            collapseButtonContainer.appendChild(expandButton);
            isPanelCollapsed = true;
        };
        expandButton.onclick = (e) => {
            reactComponentContainer.style.removeProperty('width');
            treeViewContainer.style.removeProperty('display');
            expandButton.remove();
            collapseButtonContainer.appendChild(collapseButton);
            isPanelCollapsed = false;
        };
        expandButton.click();
        visorState.setTreeViewUtil(treeViewUtil.current);
        const util = new Panel_TopLeft_Util(
            treeViewUtil.current,
            () => {
                expandButton.click();
            },
            () => {
                collapseButton.click();
            },
            () => {
                return isPanelCollapsed;
            }
        );
        visorState.setPanelTopLeftUtil(util);
        onLoad(util);
    }, []);
    return (
        <div
            id={reactComponentContainerId}
            style={{
                whiteSpace: 'nowrap',
            }}
        >
            <table>
                <tbody>
                    <tr>
                        <td>Objects</td>
                        <td id={collapseButtonContainerId} className={'shrink'}></td>
                    </tr>
                </tbody>
            </table>
            <div
                id={treeViewContainerId}
                className={'margin-top'}
                style={{
                    minWidth: '200px',
                    maxHeight: '500px',
                }}
            >
                <TreeView
                    sceneGraph={visorState.sceneGraph}
                    onLoad={(u) => {
                        treeViewUtil.current = u;
                        // treeViewReady.current();
                    }}
                />
            </div>
        </div>
    );
};
