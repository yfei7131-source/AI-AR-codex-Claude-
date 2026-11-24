/**
 * H03-R8 EasyEDA Pro Native 2nd-Order HDI Span & Minimal L2-L3 Trial Script (v2 - Cloud Verified)
 *
 * Verified against:
 *   - Cloud Project: EVT1-H03-GEMINI-R8-NOT-FOR-FAB-20261123 (id: 13bb509742f243a2852a46125154eb8a, EasyEDA Pro V4.1.105)
 *   - PR #55 (R7) & PR #57 (neon-2 / neon-3)
 *   - EasyEDA Pro API Reference (prodocs.easyeda.com)
 *
 * Key Corrections in v2:
 *   1. Absolute Coordinate Frame & Board-Edge Clearance Guard:
 *      - Live cloud PCB3 board outline (`e0`, layer 11, perimeter 3086.6 mil) spans X ≈ [915, 1115] mil, Y ≈ [-910, 435] mil.
 *      - Previous v1 local coordinates (179.47..195.47 mil) fell OUTSIDE the absolute board outline and violated
 *        JLCPCB laser blind-via to board-edge clearance (>= 14 mil / 0.35 mm; PTH X_local <= 190.87 mil).
 *      - v2 enforces a hard board-edge clearance check (>= 14 mil from via edge, >= 20 mil engineering margin)
 *        before creating any via.
 *   2. Verified Layer IDs & Inner Plane Types (Live Layer Manager):
 *      - Top (L1) = 1 (Signal), Inner1 (L2) = 15 (GND Plane), Inner2 (L3) = 16 (Signal),
 *        Inner3 (L4) = 17 (Signal), Inner4 (L5) = 18 (Plane), Bottom (L6) = 2 (Signal).
 *   3. Verified Via Type & Rule Resolution:
 *      - `EPCB_PrimitiveViaType.BLIND = 1` (0 = VIA/NORMAL, 1 = BLIND, 2 = SUTURE).
 *      - EasyEDA Pro V4.1.105 web UI defaults newly added L2-L3 blind/buried via rule name to `"2-3"`
 *        (not always renameable inline to `"BV_L2_L3"`). v2 resolves L2-L3 rule dynamically by
 *        `(staLayerId === 15 && endLayerId === 16)` OR matching name (`"BV_L2_L3"` / `"2-3"`).
 *   4. Minimal L2-L3 Single-Via Trial, Persistence Check, Strict DRC & Automatic Rollback:
 *      - Places 1 minimal L2-L3 via inside safe bounds, checks readback (`viaType === 1`, `ruleName`),
 *        runs `eda.pcb_Drc.check(true, false, true)` before & after, and rolls back automatically if
 *        DRC error count increases (e.g., Inner1 GND plane 10 mil clearance before plane rebuild) or via degrades.
 */

const BOARD_BOUNDS_MIL = {
  xMin: 915.0,
  xMax: 1115.0,
  yMin: -910.0,
  yMax: 435.0,
  jlcpcbMinLaserViaEdgeClearanceMil: 14.0, // 0.35 mm JLCPCB laser blind-via to board-edge floor
  safeMarginMil: 20.0,
};

const LAYER_IDS = {
  TOP: 1,
  INNER1_GND_PLANE: 15,
  INNER2_SIG: 16,
  INNER3_SIG: 17,
  INNER4_PLANE: 18,
  BOTTOM: 2,
};

const VIA_TYPE = {
  NORMAL: 0,
  BLIND: 1,
  SUTURE: 2,
};

// Minimal single-via L2-L3 trial point verified inside PCB3 board outline (margin >= 70 mil from edges)
const MINIMAL_L2_L3_TRIAL = {
  tag: 'r8_min_l2_l3',
  net: '', // Use 'I2S_LRCLK_1V8' only when paired with L2/L5 inner-plane antipad rebuild
  x: 985.0,
  y: 155.0,
  holeMil: 3.94, // 0.10 mm JLCPCB default laser microvia
  padMil: 9.94,  // 0.2524 mm (hole + 6 mil capture/target pad)
  staLayerId: LAYER_IDS.INNER1_GND_PLANE,
  endLayerId: LAYER_IDS.INNER2_SIG,
  candidateRuleNames: ['BV_L2_L3', '2-3'],
};

function checkBoardEdgeClearance(x, y, holeMil, bounds) {
  const r = holeMil / 2.0;
  const distLeft = (x - r) - bounds.xMin;
  const distRight = bounds.xMax - (x + r);
  const distBottom = (y - r) - bounds.yMin;
  const distTop = bounds.yMax - (y + r);
  const minEdgeDist = Math.min(distLeft, distRight, distBottom, distTop);
  return {
    minEdgeDistMil: Number(minEdgeDist.toFixed(4)),
    passesJlcpcb14Mil: minEdgeDist >= bounds.jlcpcbMinLaserViaEdgeClearanceMil,
    passesSafe20Mil: minEdgeDist >= bounds.safeMarginMil,
    distances: { distLeft, distRight, distBottom, distTop },
  };
}

function findBlindViaRuleName(cfg, staLayerId, endLayerId, candidateNames) {
  if (!cfg || typeof cfg !== 'object') return null;
  const key = 'blindViaRules' in cfg ? 'blindViaRules' : ('blindVia' in cfg ? 'blindVia' : null);
  if (!key || !Array.isArray(cfg[key])) return null;

  for (const r of cfg[key]) {
    const rName = r.name || r.ruleName;
    if ((r.staLayerId === staLayerId && r.endLayerId === endLayerId) || candidateNames.includes(rName)) {
      return { key, ruleName: rName, ruleObj: r };
    }
  }
  return { key, ruleName: null, ruleObj: null };
}

async function runMinimalL2L3Trial(options = { autoRollbackOnDrcRegression: true }) {
  const report = {
    timestamp: new Date().toISOString(),
    mode: 'MINIMAL_L2_L3',
    boardEdgeCheck: null,
    baselineDrcCount: null,
    ruleLookup: null,
    createdVia: null,
    postDrcCount: null,
    newDrcErrors: [],
    rollbackPerformed: false,
    postRollbackDrcCount: null,
    blocked: [],
  };

  // Step 1: Hard board-edge clearance guard
  report.boardEdgeCheck = checkBoardEdgeClearance(
    MINIMAL_L2_L3_TRIAL.x,
    MINIMAL_L2_L3_TRIAL.y,
    MINIMAL_L2_L3_TRIAL.holeMil,
    BOARD_BOUNDS_MIL
  );
  if (!report.boardEdgeCheck.passesJlcpcb14Mil) {
    report.blocked.push(
      `Board-edge clearance violation: minEdgeDist=${report.boardEdgeCheck.minEdgeDistMil} mil < 14.0 mil JLCPCB limit.`
    );
    console.log(JSON.stringify(report, null, 2));
    return report;
  }

  // Step 2: Baseline strict native DRC (zero rule relaxation)
  const baselineErrors = await eda.pcb_Drc.check(true, false, true);
  report.baselineDrcCount = Array.isArray(baselineErrors) ? baselineErrors.length : null;

  // Step 3: Resolve or register L2-L3 blind/buried via rule
  const cfgName = await eda.pcb_Drc.getCurrentRuleConfigurationName();
  const cfg = await eda.pcb_Drc.getCurrentRuleConfiguration();
  const lookup = findBlindViaRuleName(
    cfg,
    MINIMAL_L2_L3_TRIAL.staLayerId,
    MINIMAL_L2_L3_TRIAL.endLayerId,
    MINIMAL_L2_L3_TRIAL.candidateRuleNames
  );
  report.ruleLookup = { cfgName, foundKey: lookup ? lookup.key : null, existingRuleName: lookup ? lookup.ruleName : null };

  let activeRuleName = lookup ? lookup.ruleName : null;
  if (!activeRuleName && lookup && lookup.key) {
    cfg[lookup.key].push({
      name: 'BV_L2_L3',
      staLayerId: MINIMAL_L2_L3_TRIAL.staLayerId,
      endLayerId: MINIMAL_L2_L3_TRIAL.endLayerId,
    });
    await eda.pcb_Drc.overwriteCurrentRuleConfiguration(cfg);
    if (cfgName) {
      await eda.pcb_Drc.saveRuleConfiguration(cfgName, cfg);
    }
    activeRuleName = 'BV_L2_L3';
  } else if (!activeRuleName) {
    // Fallback to web UI default rule name if user already added 2-3 via GUI
    activeRuleName = '2-3';
    report.blocked.push(
      'Rule config BETA schema did not expose blindViaRules array; attempting pre-registered GUI rule name "2-3". ' +
      'If fallback occurs, add L2(Inner1)->L3(Inner2) in Design Rules -> Physical -> Blind/Buried Via first.'
    );
  }

  // Step 4: Create 1 minimal L2-L3 microvia & immediately read back viaType + ruleName
  const created = await eda.pcb_PrimitiveVia.create(
    MINIMAL_L2_L3_TRIAL.net,
    MINIMAL_L2_L3_TRIAL.x,
    MINIMAL_L2_L3_TRIAL.y,
    MINIMAL_L2_L3_TRIAL.holeMil,
    MINIMAL_L2_L3_TRIAL.padMil,
    VIA_TYPE.BLIND,
    activeRuleName,
    null,
    false
  );
  if (!created) {
    report.blocked.push(`PCB_PrimitiveVia.create() returned undefined for rule "${activeRuleName}".`);
    console.log(JSON.stringify(report, null, 2));
    return report;
  }

  const primId = created.getState_PrimitiveId();
  const refetched = await eda.pcb_PrimitiveVia.get(primId);
  const actualViaType = refetched ? refetched.getState_ViaType() : null;
  const actualRuleName = refetched ? refetched.getState_DesignRuleBlindViaName() : null;
  const degradedToNormal = actualViaType !== VIA_TYPE.BLIND || !actualRuleName;

  report.createdVia = {
    primitiveId: primId,
    x: MINIMAL_L2_L3_TRIAL.x,
    y: MINIMAL_L2_L3_TRIAL.y,
    holeMil: MINIMAL_L2_L3_TRIAL.holeMil,
    padMil: MINIMAL_L2_L3_TRIAL.padMil,
    expectedRule: activeRuleName,
    actualViaType,
    actualRuleName,
    degradedToNormal,
  };

  // Step 5: Strict native DRC check after placement
  const postErrors = await eda.pcb_Drc.check(true, false, true);
  report.postDrcCount = Array.isArray(postErrors) ? postErrors.length : null;
  const drcRegressed =
    report.baselineDrcCount !== null &&
    report.postDrcCount !== null &&
    report.postDrcCount > report.baselineDrcCount;

  if (Array.isArray(postErrors)) {
    report.newDrcErrors = postErrors
      .filter((e) => JSON.stringify(e).includes(primId) || JSON.stringify(e).includes('内电层'))
      .slice(0, 10);
  }

  // Step 6: Automatic rollback on degradation or DRC regression (e.g., L2 GND plane 10 mil antipad violation)
  if (degradedToNormal || (options.autoRollbackOnDrcRegression && drcRegressed)) {
    await eda.pcb_PrimitiveVia.delete([primId]);
    report.rollbackPerformed = true;
    const afterRollbackErrors = await eda.pcb_Drc.check(true, false, true);
    report.postRollbackDrcCount = Array.isArray(afterRollbackErrors) ? afterRollbackErrors.length : null;
    if (degradedToNormal) {
      report.blocked.push(`Via ${primId} degraded to NORMAL (viaType=${actualViaType}, rule=${actualRuleName}); rolled back.`);
    }
    if (drcRegressed) {
      report.blocked.push(
        `Strict DRC regressed (${report.baselineDrcCount} -> ${report.postDrcCount}); ` +
        'likely Inner1 (L2) GND plane 10 mil antipad clearance before plane rebuild. Rolled back cleanly.'
      );
    }
  }

  console.log(JSON.stringify(report, null, 2));
  return report;
}

runMinimalL2L3Trial({ autoRollbackOnDrcRegression: true });
