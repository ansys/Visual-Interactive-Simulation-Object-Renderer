import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { VisorVariableInfo } from '../state/VisorVariableManager.tsx';
import { AggregateVariableComponentInfo } from './AggregateVariableComponentInfo.tsx';
import { AggregateSelectionInfo } from './AggregateSelectionInfo.tsx';

/**
 * Represents aggregate variable information for a collection of selected scene
 * nodes.
 *
 * The class resolves the available variable components and determines whether
 * the selected nodes share a common component to display.
 *
 * Instances must be created with {@link AggregateVariableInfo.getInstanceAsync}.
 */
export class AggregateVariableInfo {
    /**
     * Creates an uninitialized aggregate variable information object.
     *
     * @private
     */
    private constructor() {}

    /** Metadata for the variable represented by this instance. */
    #variableInfo!: VisorVariableInfo;

    /** Selection state associated with this variable. */
    #selectionInfo!: AggregateSelectionInfo;

    /**
     * The component ID currently displayed by all selected nodes.
     *
     * - A number indicates that all nodes share the same component.
     * - `null` indicates that no component is selected.
     * - `undefined` indicates that the selected nodes have different components.
     */
    #displayComponentId: number | null | undefined = null;

    /**
     * Information for the currently displayed component.
     *
     * This follows the same nullability semantics as
     * {@link AggregateVariableInfo.displayComponentId}.
     */
    #currentComponentInfo: AggregateVariableComponentInfo | null | undefined = null;

    /**
     * Available component information, indexed by the component ID converted to
     * a string.
     */
    #componentOptions: Map<string, AggregateVariableComponentInfo> = new Map();

    /**
     * Creates and initializes aggregate variable information for a collection
     * of scene nodes.
     *
     * Component metadata is resolved asynchronously. The selected nodes are then
     * inspected to determine whether they share a common variable component.
     *
     * When a node's configured component is unavailable for the variable, the
     * first component option is used as its fallback.
     *
     * @param actorNodes - Scene nodes included in the aggregate selection.
     * @param selectionInfo - Selection state that owns this variable information.
     * @param variableInfo - Metadata describing the variable and its components.
     * @returns A fully initialized aggregate variable information instance.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[],
        selectionInfo: AggregateSelectionInfo,
        variableInfo: VisorVariableInfo
    ): Promise<AggregateVariableInfo> {
        const obj = new AggregateVariableInfo();
        obj.#selectionInfo = selectionInfo;
        obj.#variableInfo = variableInfo;

        for (const componentMetadata of variableInfo.componentOptions) {
            const val = await AggregateVariableComponentInfo.getInstanceAsync(
                actorNodes,
                obj,
                componentMetadata
            );
            obj.#componentOptions.set(componentMetadata.id.toString(), val);
        }

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const variable = node.variableCollection.getVariable(variableInfo.id);
            let thisComponentId: number | null = node.variableComponent;

            if (variable != null) {
                if (variable.getRangeInfo(node.variableComponent) == null) {
                    // Default to the first component option.
                    thisComponentId = variable.componentOptions[0].id;
                }
            }

            if (i === 0) {
                obj.#displayComponentId = thisComponentId;
            } else {
                obj.#displayComponentId !== thisComponentId &&
                    (obj.#displayComponentId = undefined);
            }
        }

        if (obj.#displayComponentId != null) {
            obj.#currentComponentInfo = obj.#componentOptions.get(
                obj.#displayComponentId.toString()
            );

            if (obj.#currentComponentInfo == null) {
                console.warn(`invalid componentId: '${obj.#displayComponentId}'`);
            }
        } else {
            obj.#currentComponentInfo = obj.#displayComponentId;
        }

        return obj;
    }

    /**
     * Gets the variable's unique identifier.
     *
     * @returns The variable identifier.
     */
    get id(): VisorVariableInfo['id'] {
        return this.#variableInfo.id;
    }

    /**
     * Gets the underlying variable metadata.
     *
     * @returns The variable metadata associated with this instance.
     */
    get metadata(): VisorVariableInfo {
        return this.#variableInfo;
    }

    /**
     * Gets the component ID currently shared by the selected nodes.
     *
     * @returns The shared component ID, `null` when no component is selected, or
     * `undefined` when the selected nodes use different components.
     */
    get displayComponentId(): number | null | undefined {
        return this.#displayComponentId;
    }

    /**
     * Gets all available variable components.
     *
     * The map is keyed by each component ID converted to a string.
     *
     * @returns A map of component IDs to component information.
     */
    get componentOptions(): Map<string, AggregateVariableComponentInfo> {
        return this.#componentOptions;
    }

    /**
     * Gets information about the currently displayed component.
     *
     * @returns The current component information, `null` when no valid component
     * is selected, or `undefined` when the selected nodes do not share a common
     * component.
     */
    get currentComponentInfo(): AggregateVariableComponentInfo | null | undefined {
        return this.#currentComponentInfo;
    }

    /**
     * Changes the component displayed for the current variable.
     *
     * The variable must be the current variable in the associated selection.
     * After the value is updated, the selection's variable-component-change
     * callback is invoked when one is registered.
     *
     * @param id - The component ID to display. Numeric and string IDs are
     * normalized to strings for lookup. Passing `null` or `undefined` clears or
     * marks the component state accordingly.
     * @returns Information for the selected component, `null` when the ID does
     * not match an available component, or `undefined` when explicitly passed.
     * @throws {Error} When there is no current variable.
     * @throws {Error} When this instance is not the current variable.
     */
    setDisplayComponentId = (
        id: number | string | null | undefined
    ): AggregateVariableComponentInfo | null | undefined => {
        if (this.#selectionInfo.currentVariableInfo == null) {
            throw new Error('component should not be changed when the current variable is null');
        } else if (this.#selectionInfo.currentVariableInfo !== this) {
            throw new Error('component should not be changed on a variable that is not current');
        }

        if (id != null) {
            this.#currentComponentInfo = this.#componentOptions.get(id.toString()) ?? null;
            this.#displayComponentId = this.#currentComponentInfo?.id ?? null;
        } else {
            this.#currentComponentInfo = id;
            this.#displayComponentId = id;
        }

        const events = this.#selectionInfo.events;

        if (events.onVariableComponentChange != null) {
            events.onVariableComponentChange(this.#selectionInfo.currentVariableInfo);
        }

        return this.#currentComponentInfo;
    };
}
