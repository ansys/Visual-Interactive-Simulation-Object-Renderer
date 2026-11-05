import type { ColorVariableDescriptor, NodeId, TrameTriggerSender } from './IRenderer';

/** The VISOR scene-mutation triggers: each method builds one payload and sends it; a failed send is logged, never thrown; a null sender sends nothing. */
export class SceneTriggerSends {
    constructor(triggerSender: TrameTriggerSender | null) {
        this.#triggerSender = triggerSender;
    }

    readonly #triggerSender: TrameTriggerSender | null;

    /**
     * Send one per-part payload to its server trigger.
     *
     * No sender injected -> no-op. This is the state every non-browser context
     * is in, and it is deliberate rather than defensive: the renderer is
     * constructible without a transport.
     *
     * A rejection is logged and swallowed, never rethrown. These sends run
     * inside UI handlers that behaved a certain way before this call existed,
     * and both stacks currently apply the same mutation independently, so a
     * transport failure must not change what the user sees or break an
     * interaction. The catch is deliberately unnarrowed: any rejection, of any
     * shape, is a failed send. The log line below is therefore the *only*
     * signal that a send failed -- the render will look correct either way --
     * so its prefix is fixed and greppable, and it names both the trigger and
     * the node so a failure can be attributed without a debugger.
     */
    async #sendTriggerAsync(
        triggerName: string,
        nodeId: NodeId,
        payload: Record<string, unknown>
    ): Promise<void> {
        if (this.#triggerSender == null) {
            return;
        }
        try {
            await this.#triggerSender(triggerName, payload);
        } catch (err) {
            console.error(
                `[VISOR] per-part trigger send failed: trigger='${triggerName}' nodeId=${nodeId}`,
                err
            );
        }
    }

    /**
     * Send one view-level widget payload to its server trigger.
     *
     * Sibling of `#sendTriggerAsync` above; same no-sender/no-op and
     * logged-and-swallowed-rejection rationale, not repeated here.
     *
     * Separate only because a widget trigger has no `nodeId` to name in the
     * error line, so the log prefix here is distinct and greppable on its own.
     */
    async #sendWidgetTriggerAsync(
        triggerName: string,
        payload: Record<string, unknown>
    ): Promise<void> {
        if (this.#triggerSender == null) {
            return;
        }
        try {
            await this.#triggerSender(triggerName, payload);
        } catch (err) {
            console.error(`[VISOR] widget trigger send failed: trigger='${triggerName}'`, err);
        }
    }

    // ---- Per-part ---------------------------------------------------------------
    async sendPartVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void> {
        await this.#sendTriggerAsync('set_part_visibility', nodeId, {
            nodeId,
            visible,
        });
    }

    async sendPartOpacityAsync(nodeId: NodeId, opacity: number): Promise<void> {
        await this.#sendTriggerAsync('set_part_opacity', nodeId, {
            nodeId,
            opacity,
        });
    }

    async sendPartDiffuseColorAsync(
        nodeId: NodeId,
        diffuseRgb: readonly number[] | null
    ): Promise<void> {
        // The key is always present: `diffuseRgb: null` is how a reset is
        // expressed. Omitting it is a different message, and not a valid one.
        await this.#sendTriggerAsync('set_part_diffuse_color', nodeId, {
            nodeId,
            diffuseRgb,
        });
    }

    async sendPartSelectedAsync(nodeId: NodeId, selected: boolean): Promise<void> {
        // No colour crosses this trigger by design; the server reads the
        // part's stored colour from its own record.
        await this.#sendTriggerAsync('set_part_selected', nodeId, {
            nodeId,
            selected,
        });
    }

    async sendPartColorVariableAsync(
        nodeId: NodeId,
        descriptor: ColorVariableDescriptor
    ): Promise<void> {
        // `variableId` is the client-built opaque token, forwarded verbatim;
        // nothing on either side parses it. The association travels as its own
        // typed 'POINT'|'CELL' field, and the array name as its own field,
        // precisely so that no one has to. The range is not sent: the server
        // applies its own record's range for the referenced slot.
        await this.#sendTriggerAsync('set_part_color_variable', nodeId, {
            nodeId,
            variableId: descriptor.variableId,
            association: descriptor.variableType,
            arrayName: descriptor.variableName,
            component: descriptor.component,
        });
    }

    async sendClearPartColorVariableAsync(nodeId: NodeId): Promise<void> {
        await this.#sendTriggerAsync('clear_part_color_variable', nodeId, {
            nodeId,
        });
    }

    // ---- View-level widgets -------------------------------------------------
    // Every payload is absolute, never a toggle or delta, so a send that is
    // suppressed, duplicated, or reordered is harmless.
    async sendCrossSectionVisibilityAsync(visible: boolean): Promise<void> {
        await this.#sendWidgetTriggerAsync('set_cross_section_visibility', { visible });
    }

    async sendBoundingBoxVisibilityAsync(visible: boolean): Promise<void> {
        await this.#sendWidgetTriggerAsync('set_bounding_box_visibility', { visible });
    }

    async sendProjectionAsync(parallel: boolean): Promise<void> {
        await this.#sendWidgetTriggerAsync('set_projection', { parallel });
    }

    async sendEdgesVisibleAsync(visible: boolean): Promise<void> {
        await this.#sendWidgetTriggerAsync('set_edges_visible', { visible });
    }

    /** The keys are `origin` and `normal`, three floats each, as the server's payload model requires. */
    async sendCrossSectionPlaneAsync(
        origin: readonly number[],
        normal: readonly number[]
    ): Promise<void> {
        await this.#sendWidgetTriggerAsync('sync_cross_section_plane', { origin, normal });
    }
}
