#!/usr/bin/env bash
# 原生 KiCad ERC/DRC。用法: run_native_checks.sh <evt0_core_dir> [out_dir]
# 在临时副本上执行(输入文件不被改写); DRC 带 --refill-zones; 无 kicad-cli 则写 NOT RUN 并以非0退出。
set -uo pipefail
PRJ="$(cd "${1:?project dir}" && pwd)"; OUT="${2:-$PRJ/../evidence/native_$(date +%Y%m%d_%H%M)}"; mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
PRO="$(ls "$PRJ"/*.kicad_pro | head -1)"; BASE="${PRO%.kicad_pro}"; SCH="$BASE.kicad_sch"; PCB="$BASE.kicad_pcb"
sha256sum "$SCH" "$PCB" > "$OUT/input_sha256.txt"
if ! command -v kicad-cli >/dev/null 2>&1; then
  printf 'NOT RUN: kicad-cli not available (%s)\nERC: NOT RUN\nDRC: NOT RUN\nzone refill: NOT RUN\n' "$(date -Is)" | tee "$OUT/NATIVE_STATUS.txt"; exit 2; fi
kicad-cli version > "$OUT/kicad_version.txt"
W="$(mktemp -d)"; cp -r "$PRJ"/. "$W"/; WS="$W/$(basename "$SCH")"; WP="$W/$(basename "$PCB")"
: > "$OUT/exit_codes.txt"
kicad-cli sch erc --severity-all --units mm --format json -o "$OUT/erc.json" "$WS"; echo "erc_json_exit=$?" >> "$OUT/exit_codes.txt"
kicad-cli sch erc --severity-all --units mm --format report -o "$OUT/erc.rpt" "$WS"; echo "erc_rpt_exit=$?" >> "$OUT/exit_codes.txt"
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --save-board --units mm --format json -o "$OUT/drc.json" "$WP"; echo "drc_json_exit=$?" >> "$OUT/exit_codes.txt"
cp "$WP" "$OUT/evt0_core.refilled.kicad_pcb"     # 重铺后的板(仅供审查, 不覆盖输入)
kicad-cli pcb drc --severity-all --schematic-parity --units mm --format report -o "$OUT/drc_after_refill.rpt" "$WP"; echo "drc_rpt_exit=$?" >> "$OUT/exit_codes.txt"
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/netlist.net" "$WS"; echo "netlist_exit=$?" >> "$OUT/exit_codes.txt"
sha256sum -c "$OUT/input_sha256.txt" >> "$OUT/exit_codes.txt" 2>&1   # 证明输入未被改写
python3 "$(dirname "$0")/summarize_native.py" "$OUT" ${SC_BEFORE:+--selfcheck-before $SC_BEFORE} ${SC_AFTER:+--selfcheck-after $SC_AFTER}
