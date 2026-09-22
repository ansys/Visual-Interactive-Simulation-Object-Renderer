import { CrossSectionWidget } from '../widgets/crossSectionWidget';
import type VtkScene from '../wasm/VtkScene';

/**
 * The client cross-section widget's **set** path.
 *
 * The widget holds two wasm objects: the plane, which is the clip function
 * every pipeline holds, and the representation, which is the draggable
 * handle. The read path deliberately reads the representation, because that
 * is what the handle moved. The write path used to write only the plane, and
 * that asymmetry is the defect pinned here: a load set the clip and left the
 * handle where it was, and the next end-of-drag report then carried the stale
 * handle to the server, so the server-authoritative plane would have been
 * *given* the wrong value rather than merely displaying one.
 *
 * Two tests, one per setter, because a fix applied to one of them only is a
 * shippable defect in its own right -- the clip would follow a dragged origin
 * and not a dragged normal -- and the two fail independently.
 *
 * Every value below is a hand-written literal, restated in the expectation
 * rather than read back off the double. Nothing here is derived from VTK, and
 * the doubles for the plane and the representation are separate objects, which
 * is the whole point: a single shared double could not tell the two writes
 * apart.
 */

const PLANE_ID = 202;
const PLANE_WIDGET_ID = 203;
const PLANE_REPRESENTATION_ID = 204;

function makeWidget() {
    const plane = {
        SetOrigin: jest.fn(async () => undefined),
        SetNormal: jest.fn(async () => undefined),
        GetOrigin: jest.fn(async () => [0, 0, 0]),
        GetNormal: jest.fn(async () => [0, 0, 1]),
    };
    const rep = {
        SetOrigin: jest.fn(async () => undefined),
        SetNormal: jest.fn(async () => undefined),
        GetOrigin: jest.fn(async () => [0, 0, 0]),
        GetNormal: jest.fn(async () => [0, 0, 1]),
    };
    const planeWidget = {
        On: jest.fn(async () => undefined),
        Off: jest.fn(async () => undefined),
        observe: jest.fn(),
    };
    const scene = {
        render: jest.fn(),
        getVtkObject: (wasmId: number) => {
            switch (wasmId) {
                case PLANE_ID:
                    return plane;
                case PLANE_REPRESENTATION_ID:
                    return rep;
                default:
                    return planeWidget;
            }
        },
    };
    const widget = new CrossSectionWidget(scene as unknown as VtkScene, {
        planeWasmId: PLANE_ID,
        representationWasmId: PLANE_REPRESENTATION_ID,
        widgetWasmId: PLANE_WIDGET_ID,
    });
    return { widget, plane, rep };
}

describe('CrossSectionWidget writes both plane objects on the set path', () => {
    test('setOriginAsync writes the representation and then the plane', async () => {
        const { widget, plane, rep } = makeWidget();

        await widget.setOriginAsync([1, 2, 3]);

        expect(rep.SetOrigin).toHaveBeenCalledTimes(1);
        expect(rep.SetOrigin).toHaveBeenCalledWith([1, 2, 3]);
        expect(plane.SetOrigin).toHaveBeenCalledTimes(1);
        expect(plane.SetOrigin).toHaveBeenCalledWith([1, 2, 3]);
        // Representation first, plane second, matching the order the server's
        // own set_origin writes them in.
        expect(rep.SetOrigin.mock.invocationCallOrder[0]).toBeLessThan(
            plane.SetOrigin.mock.invocationCallOrder[0]
        );
    });

    test('setNormalAsync writes the representation and then the plane', async () => {
        const { widget, plane, rep } = makeWidget();

        await widget.setNormalAsync([0, 1, 0]);

        expect(rep.SetNormal).toHaveBeenCalledTimes(1);
        expect(rep.SetNormal).toHaveBeenCalledWith([0, 1, 0]);
        expect(plane.SetNormal).toHaveBeenCalledTimes(1);
        expect(plane.SetNormal).toHaveBeenCalledWith([0, 1, 0]);
        expect(rep.SetNormal.mock.invocationCallOrder[0]).toBeLessThan(
            plane.SetNormal.mock.invocationCallOrder[0]
        );
    });
});

