// Run via the official lceda-pro CLI in the existing project's PCB tab.
// This is a single-footprint placement, independently linked by the original SCH unique ID.
const { projectId, boardId, expectedIds, apply } = __CLI__.args;
const footprintId = "34c183bc51cfb609";
const uniqueId = "81689f1d3303caec";
const netByPad = { K: "GND", A: "PRIV_LED_ANODE" };
const x = 2.1 / 0.0254;
const y = 1.4 / 0.0254;
const context = async () => {
    const project = await eda.dmt_Project.getCurrentProjectInfo();
    const board = await eda.dmt_Pcb.getCurrentPcbInfo();
    if (project?.uuid !== projectId || board?.uuid !== boardId || board?.parentProjectUuid !== projectId) {
        throw new Error("Unexpected PCB or project");
    }
};

await context();
const before = await eda.pcb_PrimitiveComponent.getAll();
const actualIds = Array.isArray(before) ? before.map(part => part.getState_PrimitiveId()).sort() : [];
if (expectedIds.length !== 10 || JSON.stringify(actualIds) !== JSON.stringify([...expectedIds].sort()) ||
    before.some(part => part.getState_Designator() === "D3" || part.getState_UniqueId() === uniqueId)) {
    throw new Error("Bridge component inventory changed");
}
const footprint = await eda.lib_Footprint.get(footprintId, "project");
if (footprint?.uuid !== footprintId || footprint?.name !== "Kingbright_APHD1608LCGCK_1608") {
    throw new Error("The exact project footprint is unavailable");
}
if (apply !== true) {
    return { projectId, boardId, footprintId, checkedComponents: actualIds.length, x, y, netByPad };
}
await context();
let createdId;
try {
    const placed = await eda.pcb_PrimitiveComponent.create(footprint, 1, x, y, 90, false);
    createdId = placed?.getState_PrimitiveId();
    if (!createdId || actualIds.includes(createdId)) {
        throw new Error("No new PCB component ID returned");
    }
    let component = await eda.pcb_PrimitiveComponent.get(createdId);
    const pads = component?.getState_Pads();
    if (!Array.isArray(pads) || pads.length !== 2 ||
        pads.map(pad => pad.padNumber).sort().join(",") !== "A,K" ||
        pads.some(pad => pad.net)) {
        throw new Error("Created footprint does not have the expected unassigned A/K pads");
    }
    await eda.pcb_PrimitiveComponent.modify(createdId, {
        designator: "D3", uniqueId, manufacturer: "Kingbright", manufacturerId: "APHD1608LCGCK",
    });
    for (const pad of pads) {
        await eda.pcb_PrimitivePad.modify(pad.primitiveId, { net: netByPad[pad.padNumber] });
    }
    component = await eda.pcb_PrimitiveComponent.get(createdId);
    const readback = component?.getState_Pads();
    if (component?.getState_Designator() !== "D3" || component?.getState_UniqueId() !== uniqueId ||
        !Array.isArray(readback) || readback.length !== 2 ||
        readback.some(pad => netByPad[pad.padNumber] !== pad.net)) {
        throw new Error("D3 designator, schematic link or pad net failed readback");
    }
    return { projectId, boardId, footprintId, createdId, uniqueId, readback, verified: true };
} catch (error) {
    await context();
    const after = await eda.pcb_PrimitiveComponent.getAll();
    const added = after.filter(part => !actualIds.includes(part.getState_PrimitiveId()));
    let rolledBack = added.length === 0;
    if (added.length === 1 && added[0].getState_PrimitiveId() === createdId) {
        await eda.pcb_PrimitiveComponent.delete([createdId]);
        const restored = await eda.pcb_PrimitiveComponent.getAll();
        rolledBack = JSON.stringify(restored.map(part => part.getState_PrimitiveId()).sort()) === JSON.stringify(actualIds);
    }
    return {
        projectId, boardId, footprintId, createdId, rolledBack, verified: false,
        error: error?.message ?? String(error),
        errorDetails: typeof error === "object" ? JSON.stringify(error) : null,
    };
}
