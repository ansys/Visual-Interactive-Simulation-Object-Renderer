import { FC, useEffect } from 'react';
import { VisorFrontend } from '../../VisorFrontend.tsx';
import { AwcIcons } from '../AwcIcons';
import { VisorSceneNodeExtended } from '../../state/VisorSceneGraph.tsx';
import { AggregateSpectrumComponentInfo } from '../../aggregate/AggregateSpectrumComponentInfo.tsx';
import { AggregateSpectrumInfo } from '../../aggregate/AggregateSpectrumInfo.tsx';
import { Panel_TopRight_Util } from './Panel_TopRight_Util.tsx';
import { AggregateSelectionInfo } from '../../aggregate/AggregateSelectionInfo.tsx';
import {
    escapeHtml,
    formatNumber,
    getRootFontSize,
    isNumeric,
    randomId,
} from '../../utils/JsHelpers';

export const Panel_TopRight: FC<{
    visorState: VisorFrontend;
    onLoad: (util: Panel_TopRight_Util) => void;
}> = ({ visorState, onLoad }) => {
    // Opacity is stored internally and in appState as a normalized value in [0, 1].
    // The UI (slider/text) is shown as percent in [0, 100].
    const opacity01ToPercent = (opacity01: number): number => {
        if (!isFinite(opacity01)) {
            return 100;
        }
        const clamped = Math.min(1, Math.max(0, opacity01));
        return Math.round(clamped * 100);
    };
    const opacityPercentTo01 = (opacityPct: number): number => {
        if (!isFinite(opacityPct)) {
            return 1;
        }
        const clamped = Math.min(100, Math.max(0, opacityPct));
        return clamped / 100;
    };

    const componentContainerId = randomId();
    const collapseButtonContainerId = randomId();
    const collapsiblePanelId = randomId();
    const legendCollapseButtonContainerId = randomId();
    const legendCollapsibleElemId = randomId();
    const paintIconClass = randomId();
    const nameInputElemId = randomId();
    const nameDifferentElemId = randomId();
    const opacityTextInputTableId = randomId();
    const opacityDifferentElemId = randomId();
    const opacityRangeInputElemId = randomId();
    const opacityTextInputElemId = randomId();
    const opacityResetButtonId = randomId();
    const legendPanelNoRangeElemId = randomId();
    const variableSelectElemId = randomId();
    const legendPanelRangeContainerId = randomId();
    const propertyTabIconContainerId = randomId();
    const legendTabIconContainerId = randomId();
    const propertyTabTextContainerId = randomId();
    const legendTabTextContainerId = randomId();
    const propertyTabElemId = randomId();
    const legendTabElemId = randomId();
    const propertyPanelElemId = randomId();
    const propertyPanelNoPartsElemId = randomId();
    const propertyPanelBodyElemId = randomId();
    const legendPanelBodyElemId = randomId();
    const legendPanelElemId = randomId();
    const legendOverlayElemId = randomId();
    const legendOverlayTitleContainerId = randomId();
    const legendGradientElemId = randomId();
    const legendOverlayElemId_alt = randomId();
    const legendOverlayTitleContainerId_alt = randomId();
    const legendGradientElemId_alt = randomId();
    const legendGradientMinTextContainerId = randomId();
    const legendGradientMidTextContainerId = randomId();
    const legendGradientMaxTextContainerId = randomId();
    const legendGradientMinTextContainerId_alt = randomId();
    const legendGradientMidTextContainerId_alt = randomId();
    const legendGradientMaxTextContainerId_alt = randomId();
    const legendPanelMinInputId = randomId();
    const legendPanelMaxInputId = randomId();
    const legendPanelMinResetButtonId = randomId();
    const legendPanelMaxResetButtonId = randomId();
    const constantRgbInputContainerId = randomId();
    const diffuseColorResetButtonId = randomId();
    const diffuseColorInputId = randomId();
    const diffuseColorDifferentElemId = randomId();
    const propertyPanelComponentContainerId = randomId();
    const componentSelectElemId = randomId();
    const legendPanelNoPartsElemId = randomId();
    const propertyPanelNoComponentContainerId = randomId();
    const legendPanelApplyRangeButtonId = randomId();
    useEffect(() => {
        const componentContainer = document.getElementById(componentContainerId) as HTMLDivElement;
        const collapseButtonContainer = document.getElementById(
            collapseButtonContainerId
        ) as HTMLTableCellElement;
        const collapsiblePanel = document.getElementById(collapsiblePanelId) as HTMLDivElement;
        const legendCollapseButtonContainer = document.getElementById(
            legendCollapseButtonContainerId
        ) as HTMLTableCellElement;
        const legendCollapsibleElem = document.getElementById(
            legendCollapsibleElemId
        ) as HTMLDivElement;
        const nameInputElem = document.getElementById(nameInputElemId) as HTMLInputElement;
        const nameDifferentElem = document.getElementById(nameDifferentElemId) as HTMLDivElement;
        const opacityTextInputTable = document.getElementById(
            opacityTextInputTableId
        ) as HTMLElement;
        const opacityDifferentElem = document.getElementById(
            opacityDifferentElemId
        ) as HTMLDivElement;
        const opacityRangeInputElem = document.getElementById(
            opacityRangeInputElemId
        ) as HTMLInputElement;
        const opacityTextInputElem = document.getElementById(
            opacityTextInputElemId
        ) as HTMLInputElement;
        const opacityResetButton = document.getElementById(opacityResetButtonId) as HTMLElement;
        const legendPanelNoRangeElem = document.getElementById(
            legendPanelNoRangeElemId
        ) as HTMLDivElement;
        const variableSelectElem = document.getElementById(
            variableSelectElemId
        ) as HTMLSelectElement;
        const legendPanelRangeContainer = document.getElementById(
            legendPanelRangeContainerId
        ) as HTMLDivElement;
        const propertyTabIconContainer = document.getElementById(
            propertyTabIconContainerId
        ) as HTMLDivElement;
        const legendTabIconContainer = document.getElementById(
            legendTabIconContainerId
        ) as HTMLDivElement;
        const propertyTabTextContainer = document.getElementById(
            propertyTabTextContainerId
        ) as HTMLDivElement;
        const legendTabTextContainer = document.getElementById(
            legendTabTextContainerId
        ) as HTMLDivElement;
        const propertyTabElem = document.getElementById(propertyTabElemId) as HTMLDivElement;
        const legendTabElem = document.getElementById(legendTabElemId) as HTMLDivElement;
        const propertyPanelElem = document.getElementById(propertyPanelElemId) as HTMLDivElement;
        const legendPanelElem = document.getElementById(legendPanelElemId) as HTMLDivElement;
        const propertyPanelNoPartsElem = document.getElementById(
            propertyPanelNoPartsElemId
        ) as HTMLDivElement;
        const propertyPanelBodyElem = document.getElementById(
            propertyPanelBodyElemId
        ) as HTMLDivElement;
        const legendPanelBodyElem = document.getElementById(
            legendPanelBodyElemId
        ) as HTMLDivElement;
        const legendOverlayElem = document.getElementById(legendOverlayElemId) as HTMLDivElement;
        const legendOverlayTitleContainer = document.getElementById(
            legendOverlayTitleContainerId
        ) as HTMLDivElement;
        const legendGradientElem = document.getElementById(legendGradientElemId) as HTMLDivElement;
        const legendOverlayElem_alt = document.getElementById(
            legendOverlayElemId_alt
        ) as HTMLDivElement;
        const legendOverlayTitleContainer_alt = document.getElementById(
            legendOverlayTitleContainerId_alt
        ) as HTMLDivElement;
        const legendGradientElem_alt = document.getElementById(
            legendGradientElemId_alt
        ) as HTMLDivElement;
        const legendGradientMinTextContainer = document.getElementById(
            legendGradientMinTextContainerId
        ) as HTMLDivElement;
        const legendGradientMidTextContainer = document.getElementById(
            legendGradientMidTextContainerId
        ) as HTMLDivElement;
        const legendGradientMaxTextContainer = document.getElementById(
            legendGradientMaxTextContainerId
        ) as HTMLDivElement;
        const legendGradientMinTextContainer_alt = document.getElementById(
            legendGradientMinTextContainerId_alt
        ) as HTMLDivElement;
        const legendGradientMidTextContainer_alt = document.getElementById(
            legendGradientMidTextContainerId_alt
        ) as HTMLDivElement;
        const legendGradientMaxTextContainer_alt = document.getElementById(
            legendGradientMaxTextContainerId_alt
        ) as HTMLDivElement;
        const legendPanelMinInput = document.getElementById(
            legendPanelMinInputId
        ) as HTMLInputElement;
        const legendPanelMaxInput = document.getElementById(
            legendPanelMaxInputId
        ) as HTMLInputElement;
        const legendPanelMinResetButton = document.getElementById(
            legendPanelMinResetButtonId
        ) as HTMLAnchorElement;
        const legendPanelMaxResetButton = document.getElementById(
            legendPanelMaxResetButtonId
        ) as HTMLAnchorElement;
        const constantRgbInputContainer = document.getElementById(
            constantRgbInputContainerId
        ) as HTMLDivElement;
        const diffuseColorResetButton = document.getElementById(
            diffuseColorResetButtonId
        ) as HTMLAnchorElement;
        const propertyPanelComponentContainer = document.getElementById(
            propertyPanelComponentContainerId
        ) as HTMLDivElement;
        const componentSelectElem = document.getElementById(
            componentSelectElemId
        ) as HTMLSelectElement;
        const diffuseColorInput = document.getElementById(diffuseColorInputId) as HTMLInputElement;
        const diffuseColorDifferentElem = document.getElementById(
            diffuseColorDifferentElemId
        ) as HTMLDivElement;
        const legendPanelNoPartsElem = document.getElementById(
            legendPanelNoPartsElemId
        ) as HTMLDivElement;
        const propertyPanelNoComponentContainer = document.getElementById(
            propertyPanelNoComponentContainerId
        ) as HTMLDivElement;
        const legendPanelApplyRangeButton = document.getElementById(
            legendPanelApplyRangeButtonId
        ) as HTMLButtonElement;

        const fontSize: number = getRootFontSize(14);

        let collapsePanel: () => void;
        let expandPanel: () => void;
        let getIsPanelCollapsed: () => boolean;
        let collapseLegend: () => void;
        let expandLegend: () => void;
        let getIsLegendCollapsed: () => boolean;

        {
            // set up top right panel collapse/expand buttons
            const collapseButton = AwcIcons.getArrowHeadDownIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            const expandButton = AwcIcons.getArrowHeadUpIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            const componentMinHeight: string = componentContainer.style.minHeight;
            let isCollapsed = false;
            collapseButton.onclick = (e) => {
                componentContainer.style.width = `${componentContainer.offsetWidth}px`;
                componentContainer.style.removeProperty('min-height');
                collapsiblePanel.style.display = 'none';
                collapseButton.remove();
                collapseButtonContainer.appendChild(expandButton);
                isCollapsed = true;
            };
            expandButton.onclick = (e) => {
                componentContainer.style.removeProperty('width');
                componentContainer.style.minHeight = componentMinHeight;
                collapsiblePanel.style.removeProperty('display');
                expandButton.remove();
                collapseButtonContainer.appendChild(collapseButton);
                isCollapsed = false;
            };
            expandButton.click();
            collapsePanel = () => {
                collapseButton.click();
            };
            expandPanel = () => {
                expandButton.click();
            };
            getIsPanelCollapsed = () => {
                return isCollapsed;
            };
        }
        {
            // set up legend overlay collapse/expand buttons
            const collapseButton = AwcIcons.getArrowHeadDownIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            const expandButton = AwcIcons.getArrowHeadUpIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            let isCollapsed = false;
            collapseButton.onclick = (e) => {
                legendOverlayElem.style.width = `${legendOverlayElem.offsetWidth}px`;
                legendCollapsibleElem.style.display = 'none';
                collapseButton.remove();
                legendCollapseButtonContainer.appendChild(expandButton);
                isCollapsed = true;
            };
            expandButton.onclick = (e) => {
                legendOverlayElem.style.removeProperty('width');
                legendCollapsibleElem.style.removeProperty('display');
                expandButton.remove();
                legendCollapseButtonContainer.appendChild(collapseButton);
                isCollapsed = false;
            };
            expandButton.click();
            collapseLegend = () => {
                collapseButton.click();
            };
            expandLegend = () => {
                expandButton.click();
            };
            getIsLegendCollapsed = () => {
                return isCollapsed;
            };
        }

        const propertyTabIcon = AwcIcons.getEdgeOnIcon(24, 10, true);
        const legendTabIcon = AwcIcons.getLegendIcon(24, 10, true);
        propertyTabIconContainer.appendChild(propertyTabIcon);
        legendTabIconContainer.appendChild(legendTabIcon);
        let tabIndex = 0;

        propertyTabElem.onclick = () => {
            propertyTabElem.classList.add('theme-background-1');
            propertyPanelElem.style.removeProperty('display');
            propertyTabTextContainer.style.removeProperty('display');
            legendTabElem.classList.remove('theme-background-1');
            legendPanelElem.style.display = 'none';
            legendTabTextContainer.style.display = 'none';
            tabIndex = 0;
        };
        legendTabElem.onclick = () => {
            propertyTabElem.classList.remove('theme-background-1');
            propertyPanelElem.style.display = 'none';
            propertyTabTextContainer.style.display = 'none';
            legendTabElem.classList.add('theme-background-1');
            legendPanelElem.style.removeProperty('display');
            legendTabTextContainer.style.removeProperty('display');
            tabIndex = 1;
        };
        propertyTabElem.onclick(null!);

        function fixValue(val: number): string {
            if (val >= 100000 || val <= -100000) {
                return val.toExponential(5);
            }
            return formatNumber(val, 5, true);
        }

        function updateMinLabel(min?: string | number | null | undefined, typing?: boolean): void {
            let minStr: string = '';
            let placeholderMin: string = '';
            if (typeof min === 'number') {
                minStr = min.toString();
            } else if (typeof min === 'string') {
                minStr = min;
            } else if (min === null) {
                placeholderMin = '(not set)';
            } else if (min === undefined) {
                placeholderMin = '(different)';
            }
            legendPanelMinInput.placeholder = placeholderMin;
            if (typing !== true && legendPanelMinInput.value != minStr) {
                legendPanelMinInput.value = minStr;
            }
        }

        function updateMaxLabel(max?: string | number | null | undefined, typing?: boolean): void {
            let maxStr: string = '';
            let placeholderMax: string = '';
            if (typeof max === 'number') {
                maxStr = max.toString();
            } else if (typeof max === 'string') {
                maxStr = max;
            } else if (max === null) {
                placeholderMax = '(not set)';
            } else if (max === undefined) {
                placeholderMax = '(different)';
            }
            legendPanelMaxInput.placeholder = placeholderMax;
            if (typing !== true && legendPanelMaxInput.value != maxStr) {
                legendPanelMaxInput.value = maxStr;
            }
        }

        const verticalBackgroundImageString = (() => {
            // base64 for the color gradient
            let s: string = '';
            s +=
                'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAKNCAIAAABumpZUAAABEElEQVR4nK1RQRLDIAhcrNf';
            s +=
                '+/2299xmJ1k40RSKKpgdmEZZdVP96wpM7AiTwW6e6XmpVv8yUPtOQtWpemeH+FUfbzwkvqr0u/vxe0sspXuyegIIyp0F9';
            s +=
                'ND/SXeH2eC3OrL+mYdVc9bdytT+c9XIT72zdafL/Yj6HhHtMmPINR75n3HIeMpbzLnjWmtQ/scc3+m9SS9NtzWevwPV69';
            s +=
                '2q8TYDzEZTikd43RUGec4RnucLjfYgzecZztR5l/bTTr8b4aPE7/tWsdp8GH9puiv7ZJ49YAkdAoKyv1DTdEfeu1z/mtf';
            s +=
                'cYadzZdTV6WrIXDO8iOWC1mf3Dwl8F1DuMsHW3Hq+lo3G0vsWrp2+ZsXAvs+8PuGpfK7VoY4AAAAAASUVORK5CYII=';
            return `url('${s}')`;
        })();

        const horizontalBackgroundImageString = (() => {
            // base64 for the color gradient
            let s: string = '';
            s +=
                'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAo0AAAABCAIAAAA0IgOQAAABBElEQVR4nJ2TWxLDIAhFLya';
            s +=
                '/3f/a+t9lJNioVVGUmHYYhsfliHZC7xfIBQMJf1WoVlJa60mW6nlEplWvZIVfW/pcJ4BUgQ2/bCiBTgHztuHXeRnQpDLT';
            s +=
                'zwiLgmEXJnCI1SP2+DrfFugnXQG6u9ewj1t4Tx9jJpweDBwIwRn9EQOOPsWn6Nrp0bX8RGPyDzmoCej5l57L7HDD9lIM5';
            s +=
                '0EeG2hD8iUoHnsOVLfUIWLac9fVWYqc8KW1GnSaEb+K9W6tBvpQxfnV4x8fDMEgvFfxbaoJM8FT4B96fZfZyKMF1m04KI';
            s += 's8v5FsIae3+/DaA7I4Yua7JYfdbkq3dN0ADjmGzBA04s8X9epU+Fr1e90AAAAASUVORK5CYII=';
            return `url('${s}')`;
        })();

        legendGradientElem.style.backgroundImage = verticalBackgroundImageString;
        legendGradientElem_alt.style.backgroundImage = horizontalBackgroundImageString;

        (async () => {
            for (const elem of componentContainer.getElementsByClassName(paintIconClass)) {
                const icon = AwcIcons.getAppearanceIcon(20);
                elem.appendChild(icon);
            }
            const treeViewUtil = await visorState.treeViewUtilPromise;
            treeViewUtil.addSelectionChangeListener(onSelectionChangeAsync);
            visorState.addViewerClickedListener(async (node, ctrlKey, shiftKey) => {
                // Only handle part selection in 'part' mode
                if (visorState.getSelectionMode() !== 'part') {
                    return;
                }
                if (!ctrlKey && !shiftKey) {
                    const promises: Promise<void>[] = [];
                    for (const row of treeViewUtil.rows) {
                        row.deselectRow(false);
                        const promise = row.node.setSelectedAsync(false);
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                }
                if (node != null) {
                    const row = treeViewUtil.rowUtilsMap.get(node.id)!;
                    if (node.selected) {
                        row.deselectRow(false);
                        await node.setSelectedAsync(false);
                    } else {
                        row.selectRow(false);
                        await node.setSelectedAsync(true);
                    }
                }
                treeViewUtil.updateSelectedNodesArray();
                await onSelectionChangeAsync(treeViewUtil.selectedNodes);
            });

            // Reset part selection when switching away from 'part' mode
            visorState.addSelectionModeChangedListener(async (_mode) => {
                const promises: Promise<void>[] = [];
                for (const row of treeViewUtil.rows) {
                    row.deselectRow(false);
                    promises.push(row.node.setSelectedAsync(false));
                }
                await Promise.all(promises);
                treeViewUtil.updateSelectedNodesArray();
                await onSelectionChangeAsync([]);
                await visorState.render();
            });

            await onSelectionChangeAsync([]);
            const util = new Panel_TopRight_Util(
                expandPanel,
                collapsePanel,
                expandLegend,
                collapseLegend,
                getIsPanelCollapsed,
                getIsLegendCollapsed,
                (tabIndex: number) => {
                    if (tabIndex === 0) {
                        propertyTabElem.click();
                    } else if (tabIndex === 1) {
                        legendTabElem.click();
                    }
                },
                () => tabIndex
            );
            visorState.setPanelTopRightUtil(util);
            onLoad(util);
        })();

        async function onSelectionChangeAsync(selectedNodes: VisorSceneNodeExtended[]) {
            const actorNodes = selectedNodes.filter((node) => {
                return node.isActorNode;
            });
            if (actorNodes.length > 0) {
                propertyPanelBodyElem.style.removeProperty('display');
                legendPanelBodyElem.style.removeProperty('display');
                propertyPanelNoPartsElem.style.display = 'none';
                legendPanelNoPartsElem.style.display = 'none';
                const aggregateSelectionInfo =
                    await AggregateSelectionInfo.getInstanceAsync(actorNodes);

                aggregateSelectionInfo.events.onSpectrumComponentChange = async (spectrumInfo) => {
                    await spectrumComponentChangeHandler(spectrumInfo);
                    await applySpectrumAsync(spectrumInfo?.currentComponentInfo);
                };

                aggregateSelectionInfo.events.onSpectrumChange = async (spectrumInfo) => {
                    await spectrumChangeHandler(spectrumInfo);
                    await applySpectrumAsync(spectrumInfo?.currentComponentInfo);
                };

                await spectrumChangeHandler(aggregateSelectionInfo.currentSpectrumInfo);
                await spectrumComponentChangeHandler(aggregateSelectionInfo.currentSpectrumInfo);

                async function spectrumComponentChangeHandler(
                    spectrumInfo: AggregateSpectrumInfo | null | undefined
                ) {
                    const componentInfo = spectrumInfo?.currentComponentInfo;
                    if (spectrumInfo == null || componentInfo == null) {
                        legendPanelNoRangeElem.style.removeProperty('display');
                        legendPanelRangeContainer.style.display = 'none';
                        legendOverlayElem.style.display = 'none';
                        legendOverlayElem_alt.style.display = 'none';
                        if (spectrumInfo === null) {
                            legendPanelNoRangeElem.innerHTML = `No data array is selected.`;
                        } else if (spectrumInfo === undefined) {
                            const msg = `Selected parts must all have the same data array and component`;
                            legendPanelNoRangeElem.innerHTML = `${msg} in order to edit min/max values.`;
                        } else if (componentInfo === null) {
                            legendPanelNoRangeElem.innerHTML = `No component is selected.`;
                        } else if (componentInfo === undefined) {
                            const msg = `Selected parts must all have the same data array and component`;
                            legendPanelNoRangeElem.innerHTML = `${msg} in order to edit min/max values.`;
                        }
                    } else {
                        componentInfo.events.onMinChange = () => {
                            updateMinLabel(componentInfo.displaySpectrumMin);
                            updateLegend(spectrumInfo);
                        };
                        componentInfo.events.onMaxChange = () => {
                            updateMaxLabel(componentInfo.displaySpectrumMax);
                            updateLegend(spectrumInfo);
                        };
                        updateMinLabel(componentInfo.displaySpectrumMin);
                        updateMaxLabel(componentInfo.displaySpectrumMax);
                        updateLegend(spectrumInfo);
                    }
                }

                function updateLegend(spectrumInfo: AggregateSpectrumInfo) {
                    const componentInfo = spectrumInfo.currentComponentInfo;
                    if (componentInfo == null) {
                        throw new Error('componentInfo should not be null here');
                    }
                    legendPanelNoRangeElem.style.display = 'none';
                    legendPanelRangeContainer.style.removeProperty('display');
                    legendOverlayElem.style.removeProperty('display');
                    legendOverlayElem_alt.style.removeProperty('display');
                    const spectrumMetadata = spectrumInfo.metadata;
                    const overlayTitle = `
                        <div class="">
                        <table class="shrink right list pad-h-5 pad-v-10">
                        <tr>
                        <th>Array Type:</th>
                        <td>${escapeHtml(spectrumMetadata.type)}</td>
                        </tr>
                        <tr>
                        <th>Array Name:</th>
                        <td>${escapeHtml(spectrumMetadata.name)}</td>
                        </tr>
                        <tr>
                        <th>Array Shape:</th>
                        <td>${escapeHtml(spectrumMetadata.shape)}</td>
                        </tr>
                        ${
                            spectrumMetadata.numComponents > 1
                                ? `
                        <tr>
                        <th>Component:</th>
                        <td>${escapeHtml(componentInfo.metadata.name)}</td>
                        </tr>
                        `
                                : ``
                        }
                        </table>
                        </div>
                        `;
                    legendOverlayTitleContainer.innerHTML = overlayTitle;
                    legendOverlayTitleContainer_alt.innerHTML = overlayTitle;
                    {
                        const min = componentInfo.displaySpectrumMin;
                        const max = componentInfo.displaySpectrumMax;
                        const minRounded =
                            typeof min === 'number'
                                ? fixValue(min)
                                : legendPanelMinInput.placeholder;
                        const maxRounded =
                            typeof max === 'number'
                                ? fixValue(max)
                                : legendPanelMaxInput.placeholder;
                        legendGradientMinTextContainer.innerHTML = minRounded;
                        legendGradientMinTextContainer_alt.innerHTML = minRounded;
                        legendGradientMaxTextContainer.innerHTML = maxRounded;
                        legendGradientMaxTextContainer_alt.innerHTML = maxRounded;
                        if (typeof min === 'number' && typeof max === 'number') {
                            const midNum = (max - min) / 2 + min;
                            const midRounded = fixValue(midNum);
                            legendGradientMidTextContainer.innerHTML = midRounded;
                            legendGradientMidTextContainer_alt.innerHTML = midRounded;
                        } else {
                            legendGradientMidTextContainer.innerHTML = '&nbsp;';
                            legendGradientMidTextContainer_alt.innerHTML = '&nbsp;';
                        }
                    }
                }

                async function spectrumChangeHandler(
                    spectrumInfo: AggregateSpectrumInfo | null | undefined
                ) {
                    await spectrumComponentChangeHandler(spectrumInfo);
                    componentSelectElem.options.length = 0;
                    if (spectrumInfo != null) {
                        constantRgbInputContainer.style.display = 'none';
                        propertyPanelComponentContainer.style.removeProperty('display');
                        propertyPanelNoComponentContainer.style.display = 'none';
                        if (spectrumInfo.displayComponentId === undefined) {
                            const optionElem = document.createElement('option');
                            optionElem.value = '';
                            optionElem.text = '';
                            componentSelectElem.options.add(optionElem);
                        }
                        for (const item of spectrumInfo.componentOptions.values()) {
                            const option = document.createElement('option');
                            option.value = item.id.toString();
                            option.text = item.metadata.name;
                            option.selected = item.id === spectrumInfo.displayComponentId;
                            componentSelectElem.options.add(option);
                        }
                        componentSelectElem.disabled = componentSelectElem.options.length === 1;
                        const originalOptionCount = componentSelectElem.options.length;
                        componentSelectElem.onchange = async () => {
                            if (spectrumInfo.displayComponentId === undefined) {
                                if (originalOptionCount === componentSelectElem.options.length) {
                                    if (componentSelectElem.selectedIndex !== 0) {
                                        componentSelectElem.options[0].remove();
                                    }
                                }
                            }
                            spectrumInfo.setDisplayComponentId(componentSelectElem.value);
                        };
                    } else {
                        propertyPanelComponentContainer.style.display = 'none';
                        if (spectrumInfo === null) {
                            constantRgbInputContainer.style.removeProperty('display');
                            propertyPanelNoComponentContainer.style.display = 'none';
                            await clearSpectrumAsync();
                        } else if (spectrumInfo === undefined) {
                            constantRgbInputContainer.style.display = 'none';
                            propertyPanelNoComponentContainer.style.removeProperty('display');
                            const msg = `Selected parts must all have the same data array in order to`;
                            propertyPanelNoComponentContainer.innerHTML = `${msg} change the component.`;
                        }
                    }
                }

                if (aggregateSelectionInfo.displayName === undefined) {
                    nameInputElem.style.display = 'none';
                    nameDifferentElem.style.removeProperty('display');
                } else {
                    nameInputElem.value = escapeHtml(aggregateSelectionInfo.displayName);
                    nameInputElem.style.removeProperty('display');
                    nameDifferentElem.style.display = 'none';
                }
                if (aggregateSelectionInfo.displayOpacity === undefined) {
                    opacityRangeInputElem.style.display = 'none';
                    opacityDifferentElem.style.removeProperty('display');
                    opacityTextInputTable.style.visibility = 'hidden';
                    opacityResetButton.onclick = async () => {
                        await applyOpacityAsync(1);
                        await onSelectionChangeAsync(actorNodes);
                    };
                } else {
                    if (aggregateSelectionInfo.displayOpacity == null) {
                        throw new Error(`displayOpacity should not be null here`);
                    }
                    const opacityPct = opacity01ToPercent(aggregateSelectionInfo.displayOpacity);
                    opacityRangeInputElem.value = opacityPct.toString();
                    opacityTextInputElem.value = opacityPct.toString();
                    opacityRangeInputElem.style.removeProperty('display');
                    opacityDifferentElem.style.display = 'none';
                    opacityTextInputTable.style.visibility = 'visible';
                }
                if (aggregateSelectionInfo.displayDiffuseColor === undefined) {
                    diffuseColorInput.style.display = 'none';
                    diffuseColorDifferentElem.style.removeProperty('display');
                    diffuseColorDifferentElem.innerHTML = '(different)';
                } else {
                    diffuseColorInput.style.removeProperty('display');
                    diffuseColorDifferentElem.style.display = 'none';
                    if (aggregateSelectionInfo.displayDiffuseColor == null) {
                        throw new Error(`displayDiffuseColor should not be null here`);
                    }
                    diffuseColorInput.value = aggregateSelectionInfo.displayDiffuseColor;
                }
                opacityRangeInputElem.oninput = async () => {
                    // Range input is always a percent [0..100]
                    const percent = isNumeric(opacityRangeInputElem.value)
                        ? parseFloat(opacityRangeInputElem.value)
                        : 100;
                    opacityTextInputElem.value = Math.round(percent).toString();
                    await applyOpacityAsync(opacityPercentTo01(percent));
                };
                opacityTextInputElem.oninput = async () => {
                    // Text input is shown as percent; tolerate decimals and clamp.
                    const raw = opacityTextInputElem.value?.trim();
                    const percent = isNumeric(raw) ? parseFloat(raw) : 100;
                    const percentClamped = Math.min(100, Math.max(0, percent));
                    opacityRangeInputElem.value = Math.round(percentClamped).toString();
                    // Keep the text as the user typed (except empty), but apply clamped.
                    await applyOpacityAsync(opacityPercentTo01(percentClamped));
                };
                legendPanelMinInput.onkeyup = async (e) => {
                    e.key === 'Enter' && legendPanelApplyRangeButton.onclick!(null!);
                };
                legendPanelMaxInput.onkeyup = async (e) => {
                    e.key === 'Enter' && legendPanelApplyRangeButton.onclick!(null!);
                };
                legendPanelApplyRangeButton.onclick = async () => {
                    const componentInfo =
                        aggregateSelectionInfo.currentSpectrumInfo?.currentComponentInfo;
                    if (componentInfo == null) {
                        throw new Error(
                            `min/max should not be edited if the current component info is null or undefined`
                        );
                    } else if (componentInfo.setDisplaySpectrumMin(legendPanelMinInput.value)) {
                        if (componentInfo.setDisplaySpectrumMax(legendPanelMaxInput.value)) {
                            const {
                                id: componentId,
                                spectrumInfo: { id: spectrumId },
                                displaySpectrumMin: min,
                                displaySpectrumMax: max,
                            } = componentInfo;
                            await visorState.setSpectrumRangeAsync(
                                spectrumId,
                                componentId,
                                min!,
                                max!
                            );
                            await visorState.render();
                        }
                    }
                };
                legendPanelMinResetButton.onclick = async (e) => {
                    e.preventDefault();
                    const componentInfo =
                        aggregateSelectionInfo.currentSpectrumInfo?.currentComponentInfo;
                    if (componentInfo == null) {
                        throw new Error(
                            `min/max should not be edited if the current component info is null or undefined`
                        );
                    }
                    updateMinLabel(componentInfo.displaySpectrumDefaultMin);
                };
                legendPanelMaxResetButton.onclick = async (e) => {
                    e.preventDefault();
                    const componentInfo =
                        aggregateSelectionInfo.currentSpectrumInfo?.currentComponentInfo;
                    if (componentInfo == null) {
                        throw new Error(
                            `min/max should not be edited if the current component info is null or undefined`
                        );
                    }
                    updateMaxLabel(componentInfo.displaySpectrumDefaultMax);
                };
                diffuseColorResetButton.onclick = async (e) => {
                    e.preventDefault();
                    await resetDiffuseColorAsync();
                    await onSelectionChangeAsync(actorNodes);
                };
                diffuseColorInput.oninput = async (e) => {
                    e.preventDefault();
                    await applyDiffuseColorAsync(diffuseColorInput.value);
                };

                async function resetDiffuseColorAsync() {
                    const promises = [];
                    for (const node of actorNodes) {
                        const promise = node.resetDiffuseColorAsync();
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                    await visorState.render();
                }

                async function applyDiffuseColorAsync(hex: string) {
                    const promises = [];
                    for (const node of actorNodes) {
                        const promise = node.setDiffuseColorHexAsync(hex);
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                    await visorState.render();
                }

                async function applyOpacityAsync(opacity: number) {
                    const promises = [];
                    for (const node of actorNodes) {
                        const promise = node.setOpacityAsync(opacity);
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                    await visorState.render();
                }

                async function clearSpectrumAsync() {
                    const promises = [];
                    for (const node of actorNodes) {
                        const promise = node.clearColorVariableAsync();
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                    await visorState.render();
                }

                async function applySpectrumAsync(
                    componentInfo?: AggregateSpectrumComponentInfo | null,
                    defaultMin?: boolean,
                    defaultMax?: boolean,
                    typing?: boolean
                ) {
                    if (componentInfo == null) {
                        return;
                    }
                    const {
                        spectrumInfo,
                        displaySpectrumDefaultMin,
                        displaySpectrumDefaultMax,
                        displaySpectrumMin,
                        displaySpectrumMax,
                    } = componentInfo;
                    const min =
                        defaultMin === true ? displaySpectrumDefaultMin : displaySpectrumMin;
                    const max =
                        defaultMax === true ? displaySpectrumDefaultMax : displaySpectrumMax;
                    updateMinLabel(min, typing);
                    updateMaxLabel(max, typing);
                    updateLegend(spectrumInfo);
                    const promises = [];
                    for (const node of actorNodes) {
                        const promise = node.setColorVariableAsync(
                            spectrumInfo.id,
                            componentInfo.id
                        );
                        promises.push(promise);
                    }
                    await Promise.all(promises);
                    await visorState.render();
                }

                variableSelectElem.options.length = 0;
                variableSelectElem.append(
                    ...(() => {
                        const arr: HTMLOptionElement[] = [];
                        arr.push(
                            (() => {
                                const optionElem = document.createElement('option');
                                optionElem.text = 'Constant';
                                return optionElem;
                            })()
                        );
                        if (aggregateSelectionInfo.displaySpectrumId === undefined) {
                            arr.unshift(
                                (() => {
                                    const optionElem = document.createElement('option');
                                    optionElem.value = '';
                                    optionElem.text = '';
                                    return optionElem;
                                })()
                            );
                        }
                        return arr;
                    })()
                );
                aggregateSelectionInfo.spectrumOptions.forEach((item) => {
                    const { id, metadata } = item;
                    const { type, name, fullName, numComponents } = metadata;
                    const optionElem = document.createElement('option');
                    optionElem.text = fullName;
                    optionElem.value = id.toString();
                    optionElem.dataset.name = name;
                    optionElem.dataset.type = type;
                    optionElem.selected = id === aggregateSelectionInfo.displaySpectrumId;
                    variableSelectElem.options.add(optionElem);
                });
                const originalOptionCount = variableSelectElem.options.length;
                variableSelectElem.onchange = async () => {
                    if (aggregateSelectionInfo.displaySpectrumId === undefined) {
                        if (originalOptionCount === variableSelectElem.options.length) {
                            if (variableSelectElem.selectedIndex !== 0) {
                                variableSelectElem.options[0].remove();
                            }
                        }
                    }
                    aggregateSelectionInfo.setDisplaySpectrumId(variableSelectElem.value);
                };
            } else {
                propertyPanelBodyElem.style.display = 'none';
                legendPanelBodyElem.style.display = 'none';
                propertyPanelNoPartsElem.style.removeProperty('display');
                propertyPanelNoPartsElem.innerHTML = `No part(s) selected.`;
                legendPanelNoPartsElem.style.removeProperty('display');
                legendPanelNoPartsElem.innerHTML = `No part(s) selected.`;
                legendOverlayElem.style.display = 'none';
                legendOverlayElem_alt.style.display = 'none';
            }
        }

        // Dynamically constrain legend height and respond to resizes.
        const updateLegendPosition = () => {
            let clipAncestor: HTMLElement | null = componentContainer.parentElement;
            while (clipAncestor && clipAncestor !== document.body) {
                const oy = getComputedStyle(clipAncestor).overflowY;
                if (oy === 'hidden' || oy === 'clip') break;
                clipAncestor = clipAncestor.parentElement;
            }
            if (clipAncestor && clipAncestor !== document.body) {
                const containerHeight = componentContainer.offsetHeight;
                const scale =
                    containerHeight > 0
                        ? componentContainer.getBoundingClientRect().height / containerHeight
                        : 1;
                const clipRect = clipAncestor.getBoundingClientRect();
                const containerRect = componentContainer.getBoundingClientRect();
                // Space from component bottom to scaffold bottom, in unscaled CSS units
                const available = (clipRect.bottom - containerRect.bottom) / scale - 20;
                legendOverlayElem.style.maxHeight = `${Math.max(50, available)}px`;
            }
        };

        const legendResizeObserver = new ResizeObserver(updateLegendPosition);
        legendResizeObserver.observe(componentContainer);
        window.addEventListener('resize', updateLegendPosition);
        updateLegendPosition();

        // cleanup observer/listener on unmount
        return () => {
            legendResizeObserver.disconnect();
            window.removeEventListener('resize', updateLegendPosition);
        };
    }, []);
    return (
        <div
            id={componentContainerId}
            style={{
                position: 'relative',
                minWidth: '250px',
                minHeight: '350px',
            }}
        >
            <div className={'theme-border-radius'} style={{}}>
                <table className={'theme-background-2 no-wrap'} style={{}}>
                    <tbody>
                        <tr>
                            <td>
                                <div id={propertyTabElemId} className={''} style={{}}>
                                    <table>
                                        <tbody>
                                            <tr>
                                                <td
                                                    id={propertyTabIconContainerId}
                                                    className={'shrink'}
                                                ></td>
                                                <td
                                                    id={propertyTabTextContainerId}
                                                    className={'padding-right'}
                                                >
                                                    Part Properties
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </td>
                            <td>
                                <div id={legendTabElemId} className={''} style={{}}>
                                    <table>
                                        <tbody>
                                            <tr>
                                                <td
                                                    id={legendTabIconContainerId}
                                                    className={'shrink'}
                                                ></td>
                                                <td
                                                    id={legendTabTextContainerId}
                                                    className={'padding-right'}
                                                >
                                                    Legend Settings
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </td>
                            <td
                                id={collapseButtonContainerId}
                                className={'shrink padding-all'}
                            ></td>
                        </tr>
                    </tbody>
                </table>
                <div id={collapsiblePanelId}>
                    <div id={propertyPanelElemId} className={'padding-all'}>
                        <div id={propertyPanelNoPartsElemId} className={'text-center'}></div>
                        <div id={propertyPanelBodyElemId}>
                            <label className={''}>
                                <span>Name</span>
                                <div className={'text-input-height'} id={nameDifferentElemId}>
                                    Names are different
                                </div>
                                <input type={'text'} className={''} id={nameInputElemId} readOnly />
                            </label>
                            <label className={'margin-top'}>
                                <span>Opacity</span>
                                <div id={opacityDifferentElemId}>
                                    <table>
                                        <tbody>
                                            <tr>
                                                <td className={'stretch'}>
                                                    <div className={'range-input-height'}>
                                                        Opacities are different
                                                    </div>
                                                </td>
                                                <td>
                                                    <a className={''} id={opacityResetButtonId}>
                                                        Reset
                                                    </a>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                                <div
                                    id={opacityTextInputTableId}
                                    style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                                >
                                    <input
                                        type={'range'}
                                        className={''}
                                        min={0}
                                        max={100}
                                        step={1}
                                        id={opacityRangeInputElemId}
                                        style={{ flex: '1 1 auto', minWidth: '0' }}
                                    />
                                    <input
                                        type={'text'}
                                        id={opacityTextInputElemId}
                                        style={{ width: '3em' }}
                                    />
                                    <span>%</span>
                                </div>
                            </label>
                            <div className={'margin-top float-container-left'} style={{}}>
                                <table className={'padh10'}>
                                    <tbody>
                                        <tr>
                                            <td className={`${paintIconClass}`}></td>
                                            <td>Color by Variable</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div className={'margin-top'}>
                                <select
                                    id={variableSelectElemId}
                                    style={{ minWidth: '100%' }}
                                ></select>
                            </div>
                            <div
                                id={propertyPanelNoComponentContainerId}
                                className={'margin-top text-center'}
                            ></div>
                            <div
                                id={propertyPanelComponentContainerId}
                                className={'margin-top float-container-right'}
                                style={{}}
                            >
                                <label style={{}}>
                                    <span>Component</span>
                                    <select id={componentSelectElemId} style={{}}></select>
                                </label>
                            </div>
                            <div
                                id={constantRgbInputContainerId}
                                className={'margin-top text-right'}
                                style={{}}
                            >
                                <label className={'inline-block'} style={{}}>
                                    <table className={'shrink no-wrap'}>
                                        <tbody>
                                            <tr>
                                                <td className={'padding-right-20'}>
                                                    Constant Color
                                                </td>
                                                <td>
                                                    <a
                                                        id={diffuseColorResetButtonId}
                                                        className={'no-select'}
                                                    >
                                                        Reset
                                                    </a>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                    <div
                                        id={diffuseColorDifferentElemId}
                                        className={'color-input-height text-center'}
                                    ></div>
                                    <input type={'color'} id={diffuseColorInputId} style={{}} />
                                </label>
                            </div>
                        </div>
                    </div>
                    <div id={legendPanelElemId} className={'padding-all'}>
                        <div id={legendPanelNoPartsElemId} className={'text-center'}></div>
                        <div id={legendPanelBodyElemId}>
                            <div id={legendPanelNoRangeElemId} className={'text-center'}></div>
                            <div id={legendPanelRangeContainerId}>
                                <label className={''}>
                                    <div className={'float-container-left'}>
                                        <div style={{ width: '50%' }}>Max</div>
                                        <div style={{ width: '50%', textAlign: 'right' }}>
                                            <a
                                                id={legendPanelMaxResetButtonId}
                                                className={'no-select'}
                                            >
                                                Reset to default
                                            </a>
                                        </div>
                                    </div>
                                    <input
                                        id={legendPanelMaxInputId}
                                        type={'text'}
                                        className={''}
                                    />
                                </label>
                                <label className={'margin-top'}>
                                    <div className={'float-container-left'}>
                                        <div style={{ width: '50%' }}>Min</div>
                                        <div style={{ width: '50%', textAlign: 'right' }}>
                                            <a
                                                id={legendPanelMinResetButtonId}
                                                className={'no-select'}
                                            >
                                                Reset to default
                                            </a>
                                        </div>
                                    </div>
                                    <input
                                        id={legendPanelMinInputId}
                                        type={'text'}
                                        className={''}
                                    />
                                </label>
                                <div className={'margin-top text-right'}>
                                    <button id={legendPanelApplyRangeButtonId}>Apply</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div
                style={{
                    position: 'absolute',
                    inset: '0 auto auto 0',
                    width: '0',
                    height: '100%',
                    opacity: '0',
                    pointerEvents: 'none',
                }}
            >
                <div
                    id={legendOverlayElemId_alt}
                    className={'no-wrap'}
                    style={{
                        position: 'absolute',
                        inset: '0 30px 10px auto',
                        overflowY: 'auto',
                        pointerEvents: 'none',
                    }}
                >
                    <div
                        style={{
                            position: 'relative',
                            textAlign: 'center',
                        }}
                    >
                        <div
                            id={legendGradientMidTextContainerId_alt}
                            className={'hard-wrap'}
                            style={{
                                display: 'inline-block',
                                verticalAlign: 'top',
                            }}
                        ></div>
                        <div
                            id={legendGradientMinTextContainerId_alt}
                            className={'hard-wrap'}
                            style={{
                                position: 'absolute',
                                inset: '0 auto auto 0',
                            }}
                        ></div>
                        <div
                            id={legendGradientMaxTextContainerId_alt}
                            className={'hard-wrap'}
                            style={{
                                position: 'absolute',
                                inset: '0 0 auto auto',
                            }}
                        ></div>
                    </div>
                    <div
                        id={legendGradientElemId_alt}
                        className={'margin-top-5'}
                        style={{
                            width: '300px',
                            height: '10px',
                            backgroundSize: '100% 100%',
                            borderRadius: '999px',
                        }}
                    ></div>
                    <div
                        id={legendOverlayTitleContainerId_alt}
                        className={'margin-top-5 theme-border-color'}
                        style={{ textAlign: 'center' }}
                    ></div>
                </div>
            </div>
            <div
                style={{
                    position: 'absolute',
                    inset: 'auto 0 0 auto',
                    width: '0',
                    height: '0',
                }}
            >
                <div
                    id={legendOverlayElemId}
                    className={'padding-all theme-legend-overlay'}
                    style={{
                        position: 'absolute',
                        inset: '10px 0 auto auto',
                        minWidth: '150px',
                        borderRadius: '6px',
                        overflowY: 'auto',
                    }}
                >
                    <table>
                        <tbody>
                            <tr>
                                <td>Legend</td>
                                <td id={legendCollapseButtonContainerId} className={'shrink'}></td>
                            </tr>
                        </tbody>
                    </table>
                    <div
                        id={legendCollapsibleElemId}
                        className={'margin-top'}
                        style={{
                            textAlign: 'right',
                        }}
                    >
                        <div
                            style={{ textAlign: 'right' }}
                            id={legendOverlayTitleContainerId}
                        ></div>
                        <div
                            className={'float-container-left margin-top no-wrap'}
                            style={{
                                display: 'inline-block',
                                verticalAlign: 'top',
                                height: '200px',
                            }}
                        >
                            <div
                                className={'margin-right'}
                                style={{
                                    position: 'relative',
                                    height: '100%',
                                }}
                            >
                                <div
                                    id={legendGradientMaxTextContainerId}
                                    className={''}
                                    style={{
                                        position: 'absolute',
                                        inset: '0 0 auto auto',
                                    }}
                                >
                                    Min
                                </div>
                                <table style={{ height: '100%' }}>
                                    <tbody>
                                        <tr>
                                            <td>
                                                <div
                                                    id={legendGradientMidTextContainerId}
                                                    className={''}
                                                >
                                                    Mid
                                                </div>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                                <div
                                    id={legendGradientMinTextContainerId}
                                    className={''}
                                    style={{
                                        position: 'absolute',
                                        inset: 'auto 0 0 auto',
                                    }}
                                >
                                    Max
                                </div>
                            </div>
                            <div
                                style={{
                                    width: '30px',
                                    height: '100%',
                                }}
                            >
                                <div
                                    id={legendGradientElemId}
                                    className={''}
                                    style={{
                                        width: '100%',
                                        height: '100%',
                                        backgroundSize: '100% 100%',
                                    }}
                                ></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
