#!/usr/bin/env python3
"""Verify corrected audio/translator topology and eight negative fixtures."""
import copy
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    path = ROOT / '00_Rev_D1_Change_Record/audio_translator_corrections.py'
    spec = importlib.util.spec_from_file_location('audio_helper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (ROOT / '02_BOM_PINMAP_ICD_Blocked/NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv').open(
            encoding='utf-8-sig', newline='') as f:
        net = list(csv.DictReader(f))
    result = module.verify_audio_translators(net)
    faults = {
        'wrong_amp_bump': lambda rs: next(r for r in rs if r['RefDes'] == 'U10_AMP_L' and r['Pin'] == 'A2').update(Pin_Function='OUTP'),
        'missing_translator_ground': lambda rs: rs.remove(next(r for r in rs if r['RefDes'] == 'U8_LS1' and r['Pin'] == '11')),
        'missing_camera_EN_clamp': lambda rs: next(r for r in rs if r['RefDes'] == 'U8_CAM_SCCB_EN' and r['Pin'] == '4').update(Net='NC'),
        'mic_on_delayed_rail': lambda rs: next(r for r in rs if r['RefDes'] == 'MK2_C' and r['Pin'] == '2').update(Net='1V8_FPGA_IO'),
        'wrong_SD_resistor': lambda rs: next(r for r in rs if r['RefDes'] == 'R_SDR' and r['Pin'] == '1').update(Pin_Function='1k'),
        'missing_amp_cap_ground': lambda rs: rs.remove(next(r for r in rs if r['RefDes'] == 'C_U10_AMP_L_HF' and r['Pin'] == '2')),
        'wrong_camera_direction': lambda rs: next(r for r in rs if r['RefDes'] == 'U8_CAM_ISO2' and r['Pin'] == '10').update(Net='CAM_DOVDD_1V8'),
        'SD_OFF_switch_not_grounded': lambda rs: next(r for r in rs if r['RefDes'] == 'U10_SD_BUF' and r['Pin'] == '3').update(Net='1V8_SYS'),
    }
    caught = []
    for name, mutate in faults.items():
        broken = copy.deepcopy(net)
        mutate(broken)
        try:
            module.verify_audio_translators(broken)
        except (AssertionError, KeyError):
            caught.append(name)
        else:
            raise AssertionError('Negative fixture escaped: ' + name)
    result.update(result='PASS', fault_injections_caught=caught,
                  devices_with_physical_pin_coverage=len(module.PHYSICAL_PINS),
                  scope='source topology, settled DC bounds and negative fixtures; NOT FOR FAB')
    print(json.dumps(result, indent=2))
    evidence = ROOT / '04_Verification_Evidence/rev_d1_audio_translator_verification.json'
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
