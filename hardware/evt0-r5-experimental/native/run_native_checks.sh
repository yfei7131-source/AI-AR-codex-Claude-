#!/usr/bin/env bash
set -uo pipefail
PRJ="${1:?R5 project dir}"; OUT="${2:-$PRJ/reports_native_$(date +%Y%m%d_%H%M)}"; mkdir -p "$OUT"
if ! command -v kicad-cli >/dev/null; then echo "NO_NATIVE_KICAD $(date -Is)" | tee "$OUT/NATIVE_STATUS.txt"; exit 2; fi
kicad-cli version | tee "$OUT/kicad_version.txt"
SCH="$(ls "$PRJ"/*.kicad_pro | sed 's/\.kicad_pro$/.kicad_sch/')"; PCB="${SCH%.kicad_sch}.kicad_pcb"
sha256sum "$SCH" "$PCB" > "$OUT/input_sha256.txt"
kicad-cli sch erc --severity-all --units mm --format json -o "$OUT/erc.json" "$SCH"; echo "erc_exit=$?" >> "$OUT/exit_codes.txt"
kicad-cli sch erc --severity-all --units mm -o "$OUT/erc.rpt" "$SCH"
kicad-cli pcb drc --severity-all --schematic-parity --units mm --format json -o "$OUT/drc.json" "$PCB"; echo "drc_exit=$?" >> "$OUT/exit_codes.txt"
kicad-cli pcb drc --severity-all --schematic-parity --units mm -o "$OUT/drc.rpt" "$PCB"
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/netlist.net" "$SCH"
sha256sum -c "$OUT/input_sha256.txt" >> "$OUT/exit_codes.txt"   # 证明未改写输入
python3 "$(dirname "$0")/summarize_native.py" "$OUT" --selfcheck-before 58 --selfcheck-after 57
