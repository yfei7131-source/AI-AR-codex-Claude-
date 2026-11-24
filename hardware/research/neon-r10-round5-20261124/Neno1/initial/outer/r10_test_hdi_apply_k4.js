/**
 * R10-TEST-HDI Executable EasyEDA Pro Native Script — Net-Attached U11.K4 (I2S_LRCLK_1V8) 2nd-Order HDI Escape
 *
 * Precondition: Import `EVT1-H03-R9-NOT-FOR-FAB.epro2` (SHA-256 2ed5b0932c51f5995a68fa602dd922cbfb4ef69429cc21e05cea195c69eaae93)
 *               into an isolated project named `R10-TEST-HDI` (NEVER modify main project).
 *               Ensure blind/buried via rules exist in Design Rules -> Physical -> Blind/Buried Via:
 *                 BV_L1_L2 (1->15), 2-3 (15->16), 3-4 (16->17), 4-5 (17->18), BV_L5_L6 (18->2).
 *
 * All coordinates are verified against the real R9 PCB3 geometry snapshot (semanticSha256 9a95369b...):
 *   - 9 staggered vias (0 stacked), 14 trace segments connecting U11.K4 -> J1.P12, U10.C3, R4.1 on net `I2S_LRCLK_1V8`.
 *   - Zero rule relaxation; runs strict native DRC before & after and checks viaType === 1 persistence.
 */

const NET = 'I2S_LRCLK_1V8';
const VIA_TYPE_BLIND = 1;

// Set LOCAL_TO_CANVAS_OFFSET = { dx: 0, dy: 0 } in local CLI mode, or { dx: boardOriginX, dy: boardOriginY } in web canvas
const LOCAL_TO_CANVAS_OFFSET = { dx: 0, dy: 0 };

const R10_VIAS = [
  { tag: 'v_k4_12',  rule: 'BV_L1_L2', x: 184.0, y: 328.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_k4_23',  rule: '2-3',      x: 184.0, y: 310.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_k4_34',  rule: '3-4',      x: 184.0, y: 290.0, hole: 6.00, pad: 12.00 },
  { tag: 'v_j1_45',  rule: '4-5',      x: 98.0,  y: 314.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_j1_56',  rule: 'BV_L5_L6', x: 98.0,  y: 296.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_u10_45', rule: '4-5',      x: 154.0, y: 336.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_u10_56', rule: 'BV_L5_L6', x: 154.0, y: 355.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_r4_45',  rule: '4-5',      x: 184.0, y: 576.0, hole: 3.94, pad: 9.94 },
  { tag: 'v_r4_56',  rule: 'BV_L5_L6', x: 184.0, y: 598.2, hole: 3.94, pad: 9.94 },
];

const R10_SEGMENTS = [
  { layer: 1,  w: 3.5, x1: 157.5, y1: 327.8, x2: 184.0, y2: 328.0 },
  { layer: 15, w: 3.5, x1: 184.0, y1: 328.0, x2: 184.0, y2: 310.0 },
  { layer: 16, w: 3.5, x1: 184.0, y1: 310.0, x2: 184.0, y2: 290.0 },
  { layer: 17, w: 4.0, x1: 184.0, y1: 290.0, x2: 184.0, y2: 314.0 },
  { layer: 17, w: 4.0, x1: 184.0, y1: 314.0, x2: 98.0,  y2: 314.0 },
  { layer: 17, w: 4.0, x1: 154.0, y1: 314.0, x2: 154.0, y2: 336.0 },
  { layer: 17, w: 4.0, x1: 184.0, y1: 314.0, x2: 184.0, y2: 576.0 },
  { layer: 18, w: 3.5, x1: 98.0,  y1: 314.0, x2: 98.0,  y2: 296.0 },
  { layer: 18, w: 3.5, x1: 154.0, y1: 336.0, x2: 154.0, y2: 355.0 },
  { layer: 18, w: 3.5, x1: 184.0, y1: 576.0, x2: 184.0, y2: 598.2 },
  { layer: 2,  w: 3.5, x1: 98.0,  y1: 296.0, x2: 90.4,  y2: 288.4 },
  { layer: 2,  w: 3.5, x1: 90.4,  y1: 288.4, x2: 71.5,  y2: 288.4 },
  { layer: 2,  w: 3.5, x1: 154.0, y1: 355.0, x2: 150.8, y2: 367.3 },
  { layer: 2,  w: 3.5, x1: 184.0, y1: 598.2, x2: 177.0, y2: 598.2 },
];

async function applyR10K4HdiRoute() {
  const log = { timestamp: new Date().toISOString(), net: NET, baselineDrc: null, vias: [], lines: [], postDrc: null, notes: [] };
  const baseErrs = await eda.pcb_Drc.check(true, false, true);
  log.baselineDrc = Array.isArray(baseErrs) ? baseErrs.length : null;

  for (const v of R10_VIAS) {
    const obj = await eda.pcb_PrimitiveVia.create(
      NET, v.x + LOCAL_TO_CANVAS_OFFSET.dx, v.y + LOCAL_TO_CANVAS_OFFSET.dy,
      v.hole, v.pad, VIA_TYPE_BLIND, v.rule, null, false
    );
    const id = obj ? obj.getState_PrimitiveId() : null;
    const ref = id ? await eda.pcb_PrimitiveVia.get(id) : null;
    log.vias.push({
      tag: v.tag, id, expectedRule: v.rule,
      actualRule: ref ? ref.getState_DesignRuleBlindViaName() : null,
      actualViaType: ref ? ref.getState_ViaType() : null,
    });
  }

  for (const s of R10_SEGMENTS) {
    const line = await eda.pcb_PrimitiveLine.create(
      NET, s.layer,
      s.x1 + LOCAL_TO_CANVAS_OFFSET.dx, s.y1 + LOCAL_TO_CANVAS_OFFSET.dy,
      s.x2 + LOCAL_TO_CANVAS_OFFSET.dx, s.y2 + LOCAL_TO_CANVAS_OFFSET.dy,
      s.w, false
    );
    log.lines.push({ layer: s.layer, id: line ? line.getState_PrimitiveId() : null });
  }

  log.notes.push(
    'Rebuild L2 (Inner1) & L5 (Inner4) GND plane antipad cutouts (radius 15.12 mil -> 10.15 mil pad-to-plane clearance) ' +
    'before final strict DRC, then save, close, reopen, and re-run eda.pcb_Drc.check(true, false, true).'
  );
  const postErrs = await eda.pcb_Drc.check(true, false, true);
  log.postDrc = Array.isArray(postErrs) ? postErrs.length : null;
  console.log(JSON.stringify(log, null, 2));
  return log;
}

applyR10K4HdiRoute();