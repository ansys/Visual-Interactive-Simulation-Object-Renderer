import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { AggregateVariableInfo } from './AggregateVariableInfo.tsx';
import { tryParseFloat } from '../utils/JsHelpers';

/**
 * Event handlers emitted when aggregate variable selections change.
 */
class AggregateSelectionEvents {
    /**
     * Called when the selected variable changes.
     *
     * A value of `undefined` generally represents a mixed selection, while
     * `null` represents no selected variable.
     */
    onVariableChange!: ((variableInfo: AggregateVariableInfo | null | undefined) => void) | null;

    /**
     * Called when a component of the selected variable changes.
     *
     * A value of `undefined` generally represents a mixed selection, while
     * `null` represents no selected variable.
     */
    onVariableComponentChange!:
        ((variableInfo: AggregateVariableInfo | null | undefined) => void) | null;
}

/**
 * Represents the shared editable state of a collection of selected scene nodes.
 *
 * Properties contain a concrete value when all selected nodes share that
 * value. A value of `undefined` indicates that the selected nodes have
 * different values, while `null` indicates that the value is not set.
 *
 * Instances must be created with {@link AggregateSelectionInfo.getInstanceAsync}.
 */
export class AggregateSelectionInfo {
    /**
     * Prevents direct construction.
     *
     * Use {@link AggregateSelectionInfo.getInstanceAsync} instead.
     */
    private constructor() {}

    /**
     * Display name shared by the selected nodes.
     */
    #displayName: string | null | undefined = null;

    /**
     * Display opacity shared by the selected nodes.
     */
    #displayOpacity: number | null | undefined = null;

    /**
     * Variable identifier shared by the selected nodes.
     */
    #displayVariableId: string | null | undefined = null;

    /**
     * Custom diffuse color shared by the selected nodes, represented as a
     * hexadecimal color string.
     */
    #displayDiffuseColor: string | null | undefined = null;

    /**
     * Available variables collected from all selected nodes, keyed by variable ID.
     */
    #variableOptions: Map<string, AggregateVariableInfo> = new Map();

    /**
     * Aggregate information for the currently selected variable.
     */
    #currentVariableInfo: AggregateVariableInfo | null | undefined = null;

    /**
     * Event handlers associated with this aggregate selection.
     */
    #events: AggregateSelectionEvents = {
        onVariableChange: null,
        onVariableComponentChange: null,
    };

    /**
     * Creates aggregate selection information for a collection of scene nodes.
     *
     * The resulting display properties contain a shared value when every node
     * has the same value. Properties are set to `undefined` when the nodes have
     * differing values.
     *
     * Variable options from all supplied nodes are also collected and converted
     * into {@link AggregateVariableInfo} instances.
     *
     * @param actorNodes - Scene nodes included in the aggregate selection.
     * @returns A promise resolving to the initialized aggregate selection.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[]
    ): Promise<AggregateSelectionInfo> {
        const obj = new AggregateSelectionInfo();

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const thisName: string | null = node.name;
            const thisOpacity: number | null = node.opacity;
            const thisVariableId: string | null = node.variableId;
            const thisDiffuseColor: string | null = node.customDiffuseColorHex;

            for (const variableInfo of node.variableCollection.array) {
                const idStr = variableInfo.id.toString();

                if (!obj.#variableOptions.has(idStr)) {
                    const val = await AggregateVariableInfo.getInstanceAsync(
                        actorNodes,
                        obj,
                        variableInfo
                    );
                    obj.#variableOptions.set(idStr, val);
                }
            }

            if (i === 0) {
                obj.#displayName = thisName;
                obj.#displayOpacity = thisOpacity;
                obj.#displayVariableId = thisVariableId;
                obj.#displayDiffuseColor = thisDiffuseColor;
            } else {
                obj.#displayName !== thisName && (obj.#displayName = undefined);

                obj.#displayOpacity !== thisOpacity && (obj.#displayOpacity = undefined);

                obj.#displayVariableId !== thisVariableId && (obj.#displayVariableId = undefined);

                obj.#displayDiffuseColor !== thisDiffuseColor &&
                    (obj.#displayDiffuseColor = undefined);
            }
        }

        if (obj.#displayVariableId != null) {
            obj.#currentVariableInfo = obj.#variableOptions.get(obj.#displayVariableId.toString());

            if (obj.#currentVariableInfo == null) {
                console.warn(`invalid variableId: '${obj.#displayVariableId}'`);
            }
        } else {
            obj.#currentVariableInfo = obj.#displayVariableId;
        }

        return obj;
    }

    /**
     * Gets the display name shared by the selected nodes.
     *
     * @returns The shared name, `null` when unset, or `undefined` when mixed.
     */
    get displayName(): string | null | undefined {
        return this.#displayName;
    }

    /**
     * Gets the display opacity shared by the selected nodes.
     *
     * @returns The shared opacity, `null` when unset, or `undefined` when mixed.
     */
    get displayOpacity(): number | null | undefined {
        return this.#displayOpacity;
    }

    /**
     * Gets the custom diffuse color shared by the selected nodes.
     *
     * @returns The shared hexadecimal color, `null` when unset, or `undefined`
     * when mixed.
     */
    get displayDiffuseColor(): string | null | undefined {
        return this.#displayDiffuseColor;
    }

    /**
     * Gets the variable identifier shared by the selected nodes.
     *
     * @returns The shared variable ID, `null` when unset, or `undefined` when
     * mixed.
     */
    get displayVariableId(): string | null | undefined {
        return this.#displayVariableId;
    }

    /**
     * Gets information about the currently selected variable.
     *
     * @returns The current variable information, `null` when no valid variable
     * is selected, or `undefined` when the selection is mixed.
     */
    get currentVariableInfo(): AggregateVariableInfo | null | undefined {
        return this.#currentVariableInfo;
    }

    /**
     * Gets all available aggregate variable options.
     *
     * @returns A map of variable IDs to aggregate variable information.
     */
    get variableOptions(): ReadonlyMap<string, AggregateVariableInfo> {
        return this.#variableOptions;
    }

    /**
     * Gets the event handlers for this aggregate selection.
     *
     * @returns The aggregate selection event handlers.
     */
    get events(): AggregateSelectionEvents {
        return this.#events;
    }

    /**
     * Updates the aggregate display name.
     *
     * @param name - The new display name. Use `null` to clear the name or
     * `undefined` to represent a mixed selection.
     */
    setDisplayName = (name: string | null | undefined): void => {
        this.#displayName = name;
    };

    /**
     * Updates the aggregate display opacity.
     *
     * String values are parsed as floating-point numbers by
     * {@link tryParseFloat}.
     *
     * @param opacity - The new numeric opacity, a parseable string, `null`, or
     * `undefined`.
     */
    setDisplayOpacity = (opacity: number | string | null | undefined): void => {
        this.#displayOpacity = tryParseFloat(opacity);
    };

    /**
     * Selects a variable by its numeric or string identifier.
     *
     * When the identifier is not present in {@link variableOptions}, the
     * current variable and display variable ID are set to `null`. Passing
     * `null` or `undefined` preserves that value and clears or marks the
     * selection as mixed, respectively.
     *
     * The `onVariableChange` handler is invoked after the selection is updated.
     *
     * @param id - The variable identifier to select, `null` to clear the
     * selection, or `undefined` to represent a mixed selection.
     * @returns Information about the selected variable, `null` when no matching
     * variable exists, or `undefined` for a mixed selection.
     */
    setDisplayVariableId = (
        id: number | string | null | undefined
    ): AggregateVariableInfo | null | undefined => {
        if (id != null) {
            this.#currentVariableInfo = this.#variableOptions.get(id.toString()) ?? null;

            this.#displayVariableId = this.#currentVariableInfo?.id ?? null;
        } else {
            this.#currentVariableInfo = id;
            this.#displayVariableId = id;
        }

        if (this.#events.onVariableChange != null) {
            this.#events.onVariableChange(this.#currentVariableInfo);
        }

        return this.#currentVariableInfo;
    };
}
