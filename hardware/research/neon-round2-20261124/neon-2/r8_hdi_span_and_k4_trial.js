/**
 * H03-R8 EasyEDA Pro Native 2nd-Order HDI Span & K4 Staggered Trial Script
 * Target: Isolated EasyEDA Pro 6-layer PCB3 trial project (NOT FOR FAB)
 * Run via: EasyEDA Pro Extension API / Built-in CLI bridge (prodocs.easyeda.com/cn/api/guide/cli.html)
 *
 * Root-Cause Fix for R7 Blocker:
 *   - R7 failed because `easyeda pcb via` / `.ses` import did NOT register `BV_L2_L3` in `blindViaRules`,
 *     causing EasyEDA Pro to fall back to `ruleName: ""`, `viaType: "NORMAL"` (through-hole).
 *   - Per EasyEDA Pro API (`PCB_PrimitiveVia.create`), blind/buried vias MUST reference an existing
 *     `designRuleBlindViaName` and pass `viaType = 1` (`EPCB_PrimitiveViaType.BLIND`).
 *   - This script inspects `eda.pcb_Drc.getCurrentRuleConfiguration()`, registers missing 2nd-order spans
 *     (`BV_L2_L3`, `BV_L3_L4`, `BV_L4_L5`) WITHOUT lowering any clearance/width/hole-to-hole rules,
 *     places staggered K4 trial vias (>= 16.0 mil / 17.0 mil c2c), verifies readback, and runs native DRC.
 */

const REQUIRED_SPANS = [
  { name: 'BV_L1_L2', staLayerId: 1, endLayerId: 15 },
  { name: 'BV_L2_L3', staLayerId: 15, endLayerId: 16 },
  { name: 'BV_L3_L4', staLayerId: 16, endLayerId: 17 },
  { name: 'BV_L4_L5', staLayerId: 17, endLayerId: 18 },
  { name: 'BV_L5_L6', staLayerId: 18, endLayerId: 2 },
];

// Coordinates in mil (EasyEDA Pro API uses mil unless project unit differs; verify unit before write)
const K4_STAGGERED_VIAS = [
  { tag: 'e53_r8', net: 'I2S_LRCLK_1V8', x: 179.47, y: 328.00, hole: 3.937, pad: 9.937, rule: 'BV_L1_L2' },
  { tag: 'e54_r8', net: 'I2S_LRCLK_1V8', x: 195.47, y: 328.00, hole: 3.937, pad: 9.937, rule: 'BV_L2_L3' },
  { tag: 'e55_r8', net: 'I2S_LRCLK_1V8', x: 195.47, y: 311.00, hole: 6.000, pad: 12.000, rule: 'BV_L3_L4' },
  { tag: 'e56_r8', net: 'I2S_LRCLK_1V8', x: 102.97, y: 301.00, hole: 3.937, pad: 9.937, rule: 'BV_L4_L5' },
  { tag: 'e57_r8', net: 'I2S_LRCLK_1V8', x: 118.97, y: 301.00, hole: 3.937, pad: 9.937, rule: 'BV_L5_L6' },
  { tag: 'e58_r8', net: 'I2S_LRCLK_1V8', x: 137.97, y: 376.00, hole: 3.937, pad: 9.937, rule: 'BV_L4_L5' },
  { tag: 'e59_r8', net: 'I2S_LRCLK_1V8', x: 153.97, y: 376.00, hole: 3.937, pad: 9.937, rule: 'BV_L5_L6' },
];

async function runH03R8NativeTrial() {
  const log = {
    timestamp: new Date().toISOString(),
    step1_ruleConfigAudit: null,
    step2_spanRegistration: null,
    step3_viaPlacementReadback: [],
    step4_nativeDrc: null,
    blocked: [],
  };

  // 1. Inspect current rule configuration (DO NOT lower any clearance or DRC threshold)
  const cfgName = await eda.pcb_Drc.getCurrentRuleConfigurationName();
  const cfg = await eda.pcb_Drc.getCurrentRuleConfiguration();
  log.step1_ruleConfigAudit = {
    cfgName,
    topLevelKeys: cfg ? Object.keys(cfg) : [],
  };

  // Locate blindVia rule container in BETA Record<string, any> schema
  const blindKey = cfg && ('blindViaRules' in cfg ? 'blindViaRules' : ('blindVia' in cfg ? 'blindVia' : null));
  if (!blindKey || !Array.isArray(cfg[blindKey])) {
    log.blocked.push(
      'BETA getCurrentRuleConfiguration() schema does not expose blindViaRules/blindVia array directly. ' +
      'Add BV_L2_L3 (Inner1->Inner2), BV_L3_L4 (Inner2->Inner3), BV_L4_L5 (Inner3->Inner4) via GUI: ' +
      'Design Rules -> Physical Rules -> Blind/Buried Via, then re-run Steps 3-4.'
    );
    console.log(JSON.stringify(log, null, 2));
    return log;
  }

  // 2. Append missing 2nd-order HDI spans only (preserve all existing clearance rules verbatim)
  const existingNames = new Set(cfg[blindKey].map((r) => r.name || r.ruleName));
  const added = [];
  for (const span of REQUIRED_SPANS) {
    if (!existingNames.has(span.name)) {
      cfg[blindKey].push({
        name: span.name,
        staLayerId: span.staLayerId,
        endLayerId: span.endLayerId,
      });
      added.push(span.name);
    }
  }
  if (added.length > 0) {
    await eda.pcb_Drc.overwriteCurrentRuleConfiguration(cfg);
    if (cfgName) {
      await eda.pcb_Drc.saveRuleConfiguration(cfgName, cfg);
    }
  }
  log.step2_spanRegistration = { blindKey, added };

  // 3. Create staggered blind/buried vias with EPCB_PrimitiveViaType.BLIND = 1
  const VIA_TYPE_BLIND = 1;
  for (const v of K4_STAGGERED_VIAS) {
    const created = await eda.pcb_PrimitiveVia.create(
      v.net,
      v.x,
      v.y,
      v.hole,
      v.pad,
      VIA_TYPE_BLIND,
      v.rule,
      null,
      false
    );
    if (!created) {
      log.blocked.push(`Failed to create via ${v.tag} with rule ${v.rule}`);
      continue;
    }
    const id = created.getState_PrimitiveId();
    const refetched = await eda.pcb_PrimitiveVia.get(id);
    const actualType = refetched ? refetched.getState_ViaType() : null;
    const actualRule = refetched ? refetched.getState_DesignRuleBlindViaName() : null;
    const fallbackDetected = actualType !== VIA_TYPE_BLIND || actualRule !== v.rule;
    log.step3_viaPlacementReadback.push({
      tag: v.tag,
      primitiveId: id,
      expectedRule: v.rule,
      actualRule,
      actualViaType: actualType,
      fallbackToNormalDetected: fallbackDetected,
    });
    if (fallbackDetected) {
      log.blocked.push(`Via ${v.tag} fell back (viaType=${actualType}, rule=${actualRule}); check GUI blindVia rule persistence.`);
    }
  }

  // 4. Run strict native DRC (includeVerboseError = true)
  const drcErrors = await eda.pcb_Drc.check(true, false, true);
  log.step4_nativeDrc = {
    totalErrorCount: Array.isArray(drcErrors) ? drcErrors.length : null,
    sampleErrors: Array.isArray(drcErrors) ? drcErrors.slice(0, 20) : drcErrors,
  };

  console.log(JSON.stringify(log, null, 2));
  return log;
}

runH03R8NativeTrial();