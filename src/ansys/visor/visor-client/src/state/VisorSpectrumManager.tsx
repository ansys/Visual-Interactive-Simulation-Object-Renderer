import VisorVtkDataArray, { FieldAssociation } from './appstate/vtkInfo/VisorVtkDataArray.tsx';

/**
 * Describes a selectable component of a spectrum.
 *
 * @remarks
 * The magnitude component uses an ID of `-1`. Individual array components
 * begin at `0`.
 */
export type VisorSpectrumComponentMetadata = Readonly<{
    /** Numeric identifier used to select the component. */
    id: number;

    /** Human-readable component label, such as `"Magnitude"`, `"X"`, or `"Y"`. */
    name: string;
}>;

/**
 * Describes a spectrum derived from one or more compatible VTK data arrays.
 *
 * @remarks
 * Spectrum objects are immutable, although their custom ranges can be changed
 * through {@link VisorSpectrumInfo.setCustomRange}.
 */
export type VisorSpectrumInfo = Readonly<{
    /**
     * Unique spectrum identifier.
     *
     * @remarks
     * The identifier has the format
     * `"<type>::<name>::<number-of-components>"`.
     */
    id: string;

    /** Data-array association type, can be either 'POINT' or 'CELL'. */
    type: FieldAssociation;

    /** Name of the underlying data array. */
    name: string;

    /** Human-readable shape name, such as `"Scalar"` or `"Vector3"`. */
    shape: string;

    /** Display name containing the association type, array name, and shape. */
    fullName: string;

    /** Number of components in the underlying data array. */
    numComponents: number;

    /** Components that can be selected when displaying the spectrum. */
    componentOptions: VisorSpectrumComponentMetadata[];

    /**
     * Gets the default and custom ranges for a component.
     *
     * @param component - Component index. Use `-1` for magnitude, `0` for the
     * first array component, or `null`/`undefined` when no component is selected.
     * @returns Cloned default and custom ranges, or `null` when the component is
     * missing or outside the supported range.
     */
    getRangeInfo: (component: number | null | undefined) => null | {
        /** Aggregate range calculated from all matching data arrays. */
        defaultRange: number[];

        /** User-configurable range for the selected component. */
        customRange: number[];
    };

    /**
     * Updates the custom range for a component.
     *
     * @param component - Component index. Use `-1` for magnitude.
     * @param min - New minimum value.
     * @param max - New maximum value.
     *
     * @remarks
     * No change is made when the component index is outside the supported range.
     */
    setCustomRange: (component: number, min: number, max: number) => void;
}>;

/**
 * A collection of spectra associated with a group of data arrays.
 */
export type VisorSpectrumCollection = Readonly<{
    /** Spectra in collection order. */
    array: VisorSpectrumInfo[];

    /**
     * Finds a spectrum by its unique identifier.
     *
     * @param id - Spectrum identifier, or `null` when no spectrum is selected.
     * @returns The matching spectrum, or `null` when no match exists.
     */
    getSpectrum: (id: string | null) => VisorSpectrumInfo | null;
}>;

/**
 * Coordinates spectrum metadata across multiple groups of VTK data arrays.
 *
 * @remarks
 * Call {@link VisorSpectrumManager.addDataArrayMetadata} for every relevant
 * group of arrays, then call
 * {@link VisorSpectrumManager.finishAddingDataArrayMetadata} once. The global
 * collection is unavailable until finalization is complete.
 */
export type VisorSpectrumManager = Readonly<{
    /**
     * Adds metadata for a group of VTK data arrays.
     *
     * @param dataArrays - Data arrays from which spectrum metadata is derived.
     * @returns A collection containing one spectrum for each supplied data array.
     *
     * @remarks
     * Arrays with the same type, name, and component count share a global
     * spectrum. Their default ranges are expanded to include all observed values.
     */
    addDataArrayMetadata: (dataArrays: VisorVtkDataArray[]) => VisorSpectrumCollection;

    /**
     * Finalizes the global spectrum collection.
     *
     * @throws Error if this method has already been called.
     */
    finishAddingDataArrayMetadata: () => void;

    /**
     * Finalized collection of all globally registered spectra.
     *
     * @throws Error if
     * {@link VisorSpectrumManager.finishAddingDataArrayMetadata} has not yet
     * been called.
     */
    globalSpectrumCollection: VisorSpectrumCollection;
}>;

/**
 * Creates a spectrum manager for aggregating metadata from VTK data arrays.
 *
 * @returns A new spectrum manager with no registered spectra.
 */
export function getSpectrumManager(): VisorSpectrumManager {
    /** Tracks spectrum IDs and their assigned lookup positions. */
    const spectrumIdLookup: Map<string, number> = new Map();

    /** Stores each globally unique spectrum by its ID. */
    const globalSpectrumMap: Map<string, VisorSpectrumInfo> = new Map();

    /** Stores aggregate default ranges for each spectrum. */
    const globalDefaultRanges: Map<string, number[][]> = new Map();

    /** Stores user-configurable ranges for each spectrum. */
    const globalCustomRanges: Map<string, number[][]> = new Map();

    /** Maps supported component counts to shape and component-label metadata. */
    const labelInfoMap: Map<
        number,
        {
            /** Human-readable shape name. */
            shape: string;

            /**
             * Component labels in display order.
             *
             * @remarks
             * The first label represents magnitude. Remaining labels correspond to
             * the underlying array components.
             */
            componentLabels: string[];
        }
    > = new Map();

    labelInfoMap.set(1, {
        shape: 'Scalar',
        componentLabels: ['Magnitude'],
    });

    labelInfoMap.set(2, {
        shape: 'Vector2',
        componentLabels: ['Magnitude', 'X', 'Y'],
    });

    labelInfoMap.set(3, {
        shape: 'Vector3',
        componentLabels: ['Magnitude', 'X', 'Y', 'Z'],
    });

    labelInfoMap.set(4, {
        shape: 'Vector4',
        componentLabels: ['Magnitude', 'X', 'Y', 'Z', 'W'],
    });

    labelInfoMap.set(9, {
        shape: 'Vector4',
        componentLabels: ['Magnitude', 'XX', 'XY', 'XZ', 'YX', 'YY', 'YZ', 'ZX', 'ZY', 'ZZ'],
    });

    /** Finalized global collection, or `null` until registration is complete. */
    let globalSpectrumCollection: VisorSpectrumCollection | null = null;

    return Object.freeze({
        addDataArrayMetadata,

        /**
         * Finalizes the global collection after all data-array metadata has been added.
         *
         * @throws Error if the global collection has already been finalized.
         */
        finishAddingDataArrayMetadata() {
            if (globalSpectrumCollection != null) {
                throw new Error(`finishAddingDataArrayMetadata() has already been called`);
            }

            const array = [];
            for (const item of globalSpectrumMap.values()) {
                array.push(item);
            }

            globalSpectrumCollection = Object.freeze({
                array,

                /**
                 * Finds a globally registered spectrum.
                 *
                 * @param id - Spectrum identifier, or `null`.
                 * @returns The matching spectrum, or `null` when none exists.
                 */
                getSpectrum(id: string | null) {
                    return id != null ? (globalSpectrumMap.get(id) ?? null) : null;
                },
            });
        },

        /**
         * Gets the finalized global spectrum collection.
         *
         * @throws Error if metadata registration has not yet been finalized.
         */
        get globalSpectrumCollection() {
            if (globalSpectrumCollection == null) {
                throw new Error(`finishAddingDataArrayMetadata() has not been called yet`);
            }

            return globalSpectrumCollection;
        },
    });

    /**
     * Creates or updates spectrum information for a data array.
     *
     * @param dataArray - Source data array metadata.
     * @returns The newly created spectrum, or the existing compatible spectrum.
     *
     * @remarks
     * When a compatible spectrum already exists, its default ranges are expanded
     * to include the new array's ranges. Its custom ranges are then reset to the
     * updated defaults.
     *
     * @throws Error if the data array has an unsupported component count.
     */
    function tryAddSpectrumInfo(dataArray: VisorVtkDataArray): VisorSpectrumInfo {
        const { type, name, numComponents, magnitudeRange, ranges } = dataArray;

        // Use a human-readable ID like 'point::displacement::3'
        const id = `${type}::${name}::${numComponents}`;

        if (globalSpectrumMap.has(id)) {
            // Update the existing ranges for this spectrum
            // with each subsequent new set of ranges.
            const defaultRanges = globalDefaultRanges.get(id)!;
            const customRanges = globalCustomRanges.get(id)!;

            magnitudeRange[0] < defaultRanges[0][0] && (defaultRanges[0][0] = magnitudeRange[0]);
            magnitudeRange[1] > defaultRanges[0][1] && (defaultRanges[0][1] = magnitudeRange[1]);

            ranges.forEach((range, i) => {
                range[0] < defaultRanges[i + 1][0] && (defaultRanges[i + 1][0] = range[0]);
                range[1] > defaultRanges[i + 1][1] && (defaultRanges[i + 1][1] = range[1]);
            });

            customRanges.forEach((range, i) => {
                range[0] = defaultRanges[i][0];
                range[1] = defaultRanges[i][1];
            });

            return globalSpectrumMap.get(id)!;
        }

        const labelInfo = labelInfoMap.get(numComponents);
        if (labelInfo == null) {
            const msg = `No label info was found for this data array. Do we support label info`;
            throw new Error(`${msg} for data arrays with ${numComponents} component(s)?`);
        }

        const componentOptions: VisorSpectrumComponentMetadata[] = [];
        for (let i = 0; i < labelInfo.componentLabels.length; i++) {
            componentOptions.push({
                id: i - 1,
                name: labelInfo.componentLabels[i],
            });
        }

        const [defaultRanges, customRanges] = (() => {
            const arr: number[][] = [];
            const arrClone: number[][] = [];

            arr.push([magnitudeRange[0], magnitudeRange[1]]);
            arrClone.push([magnitudeRange[0], magnitudeRange[1]]);

            for (let i = 0; i < numComponents; i++) {
                arr.push([ranges[i][0], ranges[i][1]]);
                arrClone.push([ranges[i][0], ranges[i][1]]);
            }

            return [arr, arrClone];
        })();

        globalDefaultRanges.set(id, defaultRanges);
        globalCustomRanges.set(id, customRanges);

        const info: VisorSpectrumInfo = Object.freeze({
            id,
            type,
            name,
            shape: labelInfo.shape,
            fullName: `${type} - ${name} (${labelInfo.shape})`,
            numComponents,
            componentOptions,

            /**
             * Gets cloned range information for a component.
             *
             * @param component - Component index, with `-1` representing magnitude.
             * @returns Range information, or `null` for an invalid component.
             */
            getRangeInfo: (component) => {
                if (component == null) {
                    return null;
                }

                const i = component + 1; // Add 1 because "magnitude" occupies index 0.

                return i >= 0 && i < customRanges.length
                    ? {
                          // Clone the arrays so they cannot be directly modified by the user.
                          defaultRange: [...defaultRanges[i]],
                          customRange: [...customRanges[i]],
                      }
                    : null;
            },

            /**
             * Changes the custom range for a component.
             *
             * @param component - Component index, with `-1` representing magnitude.
             * @param min - New minimum range value.
             * @param max - New maximum range value.
             */
            setCustomRange: (component, min, max) => {
                const i = component + 1; // Add 1 because "magnitude" occupies index 0.

                if (i >= 0 && i < customRanges.length) {
                    customRanges[i][0] = min;
                    customRanges[i][1] = max;
                }
            },
        });

        globalSpectrumMap.set(id, info);
        return info;
    }

    /**
     * Registers a group of data arrays and creates its local spectrum collection.
     *
     * @param dataArrays - Data arrays to register.
     * @returns An immutable collection containing spectra for the supplied arrays.
     */
    function addDataArrayMetadata(dataArrays: VisorVtkDataArray[]): VisorSpectrumCollection {
        const array: VisorSpectrumInfo[] = [];
        const map: Map<string, VisorSpectrumInfo> = new Map();

        for (let i = 0; i < dataArrays.length; i++) {
            const info = tryAddSpectrumInfo(dataArrays[i]);
            array.push(info);
            map.set(info.id, info);
        }

        Object.freeze(array);

        return Object.freeze({
            array,

            /**
             * Finds a spectrum within this local collection.
             *
             * @param id - Spectrum identifier, or `null`.
             * @returns The matching spectrum, or `null` when none exists.
             */
            getSpectrum(id: string | null) {
                return id != null ? (map.get(id) ?? null) : null;
            },
        });
    }
}
