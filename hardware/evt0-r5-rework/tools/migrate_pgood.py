"""Step 1: 把 R5 实验候选中经自检复核的 /CHG_PGOOD_N 10 个铜项原样 (同 UUID/几何/块文本) 迁入 rework 板。
R5 实验板未处理铺铜: 其新增过孔 (133.8,118.1) 落在 In1/GND 与 In2/3V3 的旧填充多边形内 = 文件内存储铜短路, 直到重铺。
这里清空两块平面的 filled_polygon (zone 定义不变), 强制 KiCad 重铺; 原生 DRC 必须 --refill-zones。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pcb_edit import Pcb
from r5_route import emit_blocks
D = Path(sys.argv[1]); exp = json.load(open(sys.argv[2]))
recs = exp['added_copper']
P = Pcb(D/'evt0_core.kicad_pcb')
P.insert_copper(recs, emit_blocks)
P.clear_zone_fills()
P.save()
print(json.dumps(P.log, default=str))
