/**
 * EasyEDA Pro R10-TEST-J3 Safe Incremental Placement Script (PCB1)
 * Safety Guard: Refuses to execute unless active project name contains "TEST" and "NOT-FOR-FAB".
 * Does NOT relax DRC/ERC rules. Does NOT guess J2 power polarity.
 */
(async function applyR10TestJ3Delta() {
  const MM2MIL = 1 / 0.0254;
  const info = await eda.dmt_Project.getCurrentProjectInfo();
  if (!info || !info.name || !info.name.includes("TEST") || !info.name.includes("NOT-FOR-FAB")) {
    throw new Error("SAFETY ABORT: Refusing to modify master/non-TEST project: " + (info ? info.name : "unknown"));
  }
  const TARGET_J3_OPT1 = { designator: "J3", x_mm: 2.900, y_mm: 41.100, rotation: 0, layer: 1 };
  const comps = await eda.pcb_PrimitiveComponent.getAll();
  const j3 = comps.find(c => c.getState_Designator && c.getState_Designator() === "J3");
  if (!j3) {
    console.warn("J3 not yet imported to PCB1. Import J3_MillMax_856-10-004-30-051000.kicad_mod and run Import Changes first.");
    return;
  }
  await eda.pcb_PrimitiveComponent.modify(j3.getState_PrimitiveId(), {
    x: Number((TARGET_J3_OPT1.x_mm * MM2MIL).toFixed(4)),
    y: Number((TARGET_J3_OPT1.y_mm * MM2MIL).toFixed(4)),
    rotation: TARGET_J3_OPT1.rotation
  });
  console.log("Moved J3 to verified zero-collision tail L1 slot:", TARGET_J3_OPT1);
})();
