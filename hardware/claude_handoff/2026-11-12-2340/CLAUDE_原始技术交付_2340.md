# ZY AI/AR 硬件研发 · R5 / EVT-1 续接交付（2026-11-12 23:05 断点之后）

本轮**无法打开附件 ZIP、没有原生 KiCad、也没有 GitHub 凭据**。因此 STATE 未读，PR #3（24facfb）未核验，没有任何工程文件被实际修改或执行。真正交付的是一个可直接放进新目录 `R5/` 的差异包：参数化 CadQuery 装配源码、逐项重量与热预算、原生 KiCad 复核脚本（全部**未执行**）。按设计计算，50 g 工程目标可以达到（43.8 g + 10% 余量 = 48.2 g）；40 g 挑战目标只有换 0.35 mm SiC 波导并把壳体减薄才勉强够到。

## TL;DR
- **环境如实声明**：附件 ZIP、STATE_FOR_NEXT_SESSION.md、R4 工程、已恢复布线器、隔离 POC、自检脚本，本会话都访问不到。下文所有"测试结果"都是手算或待执行命令，不是运行记录；/CHG_PGOOD_N 的 58→57 仍然只是自检结论，没有原生 DRC 确认。
- **P0 EVT-1**：按占位 ID 包络（银灰 ID 母版 STEP 到位后替换）手算，基线 43.8 g，加 10% 余量 48.2 g，满足 50 g；40 g 路线需要 0.35 mm SiC 波导（每片 1.98 g，预印本级技术）加 0.6 mm 壁厚。热：HUD 模式全机约 0.95 W，左镜腿必须铺满石墨均热，否则估算 46 °C；拍摄模式左镜腿估算 42.4 °C，超过 40 °C 舒适线，必须做拍摄时长限制和热降频。
- **P1 R5**：给出 `run_native_checks.sh` 和 `summarize_native.py`，用 kicad-cli 生成真实 ERC/DRC 的 JSON/RPT，并从网表里核对 /CHG_PGOOD_N 的节点。12 个孔径错误优先改成激光微孔或调整孔径，**禁止下调板级约束来掩盖**；3 个库警告用项目库修复，**禁止把严重性设为 ignore**。

## Key Findings

| 项 | 状态 | 结论 |
|---|---|---|
| 附件 / STATE / PR #3 | ❌ 不可达 | 未读未核验；本交付按"新目录、新分支、不碰 R4"来写 |
| EVT-1 参数化装配 | ⚠️ 源码交付，未运行 | CadQuery 源码，含干涉/间隙/质量/STEP 导出\[1\]\[2\] |
| 重量 | ✅ 手算 | 基线 43.78 g；加 10% 余量 48.16 g ≤ 50 g（余 1.84 g）；40 g 需 SiC 0.35 mm 加 0.6 mm 壁厚 |
| 空间 | ⚠️ 手算 | 电池 4.0×9.0 放进镜腿内腔 4.9×9.9，各边余 0.45 mm，过 0.30 mm 门槛；相机与隐私 LED 在 12 mm 高端件里只余约 0.05 mm，需要端件 ≥12.5 mm |
| 热 | ⚠️ 集总估算 | HUD 模式有均热则通过（34 °C）；拍摄模式左镜腿 42.4 °C，超舒适线 |
| /CHG_PGOOD_N | ❌ 未原生复核 | 脚本已就绪，58→57 仍算自检结论 |
| 12 孔径 / 3 库警告 / 未连接 | ❌ 未整改 | 给出判定规则与验收标准 |
| GitHub Draft PR | ❌ 无法推送 | 交付差异包和应用命令，SHA 未生成 |

**外部基准**（用来支撑假设参数）：
- 光机：JBD 官方页给出 Hummingbird II 全彩光机 0.2 cc、0.5 g，典型功耗 95 mW，光通量 3 lm，FOV 25°，分辨率 500×380。LEDinside 2025-12-16 的 CES 2026 创新奖报道写的是"典型工况低至 50 mW"，与官方不一致，本预算取 95 mW。Avegant（竞品方，立场有偏）指出 MicroLED 光机标称体积不含散热片、FPC 和防鬼影所需的约 15° 倾角，因此本预算给每台光机另加 0.6 g 支架/散热。\[3\]
- 波导：TrendForce（2026-08-18）称 Goolton、AAC 已把波导镜片做到每片约 4 g、透过率超过 90%。SiC 单层波导封装后 3.795 g、0.75 mm（eLight 2025）。0.35\[4\] mm SiC 波导 1.98 g（arXiv 2609.07648，预印本）。\[5\]
- 竞品重量：Rokid 官方规格为 49 g（TR90 镜框、单色绿光显示、30° FOV、Snapdragon AR1、210 mAh）。Meta-Bounds 在 CES 2026 声称双目全彩 38 g（厂商宣传口径）。TrendForce\[6\] 统计 2026 年新发布的 MicroLED 机型中，≤40 g 约占七成。\[7\]
- 热限值：IEC 62368-1:2018 Table 38 规定，贴肤佩戴超过 8 h 的 TS1 限值为 43–48 °C，金属、玻璃、塑料一律相同。UL\[8\] Solutions 的影响分析指出，Ed.4（2023，现为 Table 37）要求可穿戴设备在正常、异常**和单一故障**条件下都不得超过 TS1。Meta\[9\] Reality Labs 的 Lee 等人（arXiv 2512.16045，2025-12-18）指出 IEC 62368-1 的 43–48 °C 安全限值不满足眼镜的舒适要求，认为舒适上限约 40 °C，对应可持续功耗约 1–2 W。
- 材料：EMS Grilamid TR 90 数据表给出密度 1.00 g/cm³（ISO 1183）。\[10\]
- 充电：TI 应用笔记 SLUAAJ8（BQ25180，2023-01）给出 JEITA 阈值 0/10/45/60 °C（其示例电路实际 warm 阈值落在 44 °C）。

## Details

### 1. 交付物清单（差异包，全部为新增文件；R4 不改动）

```
R5/
├─ STATE_FOR_NEXT_SESSION.md          # 下轮状态（见第 6 节）
├─ evt1/cad/zy_evt1_asm.py            # 参数化装配 + 干涉/间隙/质量 + STEP
├─ evt1/thermal/thermal_budget.py     # 集总热预算
├─ evt1/ASSUMPTIONS.md                # 假设清单（即第 5 节）
├─ native/run_native_checks.sh        # 原生 kicad-cli ERC/DRC/网表
├─ native/summarize_native.py         # 报告解析：孔径/库警告/未连接/CHG_PGOOD_N
└─ TEST_LOG.md                        # 本轮测试记录：全部 "NOT RUN"
```
应用方式（需在有仓库权限的机器上执行）：`git fetch && git switch -c r5/evt1-native 24facfb`，把文件复制到 `R5/` 后 `git add R5 && git commit`，再运行 `gh pr create --draft --base <PR#3 分支>`，最后用 `git rev-parse HEAD` 和 `gh pr view --json headRefOid` 核对两边 SHA 是否一致。完整 ZIP 用 `zip -r ZY_R5_EVT1_$(date +%m%d_%H%M).zip R5` 打包；本环境无法生成文件，所以本轮**没有 ZIP**。

### 2. P0 EVT-1 参数化装配源码（`evt1/cad/zy_evt1_asm.py`）

坐标系：X 为左右（+ 为佩戴者右侧），Y 为前后（+ 为前方），Z 为上下；单位 mm、g。标志 S 表示有来源，A 表示假设。

```python
#!/usr/bin/env python3
"""ZY EVT-1 parametric assembly (R5). Run: python zy_evt1_asm.py [resin|sic075|sic035]"""
import sys, json, csv, itertools, pathlib
import cadquery as cq

OUT = pathlib.Path(__file__).resolve().parent / "out"; OUT.mkdir(exist_ok=True)
VARIANT = sys.argv[1] if len(sys.argv) > 1 else "resin"
ID_MASTER = pathlib.Path(__file__).resolve().parent / "id_master_silvergrey.step"  # 银灰ID母版(存在则叠加校核)

P = {  # value, flag
 "lens_w":(50.0,"A"), "lens_h":(38.0,"A"), "bridge":(18.0,"A"),
 "rim_face":(4.0,"A"), "rim_depth":(5.0,"A"),
 "end_w":(10.0,"A"), "end_l":(12.0,"A"), "end_h":(12.5,"A"),
 "temple_len":(145.0,"A"), "temple_w":(6.5,"A"), "temple_h":(11.5,"A"), "wall":(0.8,"A"),
 "wg_t":({"resin":1.0,"sic075":0.75,"sic035":0.35}[VARIANT], "S/A"),
 "eng_x":(6.0,"A"), "eng_y":(7.0,"A"), "eng_z":(5.0,"A"),      # 含支架包络; 核心0.2cc(S)
 "pcbL_len":(40.0,"A"), "pcbR_len":(28.0,"A"), "pcb_w":(8.5,"A"), "pcb_stack":(2.4,"A"),
 "bat_len":(28.0,"A"), "bat_w":(9.0,"A"), "bat_t":(4.0,"A"),  # ~100mAh级
 "cam_xy":(6.5,"S"), "cam_d":(4.5,"A"), "led":(1.6,"A"),
 "spk_len":(12.0,"A"), "spk_t":(3.5,"A"), "spk_h":(8.0,"A"),
 "ear_bend_y":(-107.0,"A"), "min_gap":(0.30,"A"),
}
v = lambda k: P[k][0]
TR90 = 1.00                                   # g/cm3 Grilamid TR90 ISO1183 (S)
WG_MASS = {"resin":4.0, "sic075":3.795, "sic035":1.98}[VARIANT]   # g/片 (S)

def box(x0,x1,y0,y1,z0,z1):
    return cq.Workplane("XY").box(x1-x0,y1-y0,z1-z0,centered=False).translate((x0,y0,z0)).val()

def shell(x0,x1,y0,y1,z0,z1,w,open_front=False,open_back=False):
    inner = box(x0+w,x1-w, y0-1 if open_back else y0+w, y1+1 if open_front else y1-w, z0+w,z1-w)
    return box(x0,x1,y0,y1,z0,z1).cut(inner)

parts = []   # name, shape|None, mass_g, flag, kind(shell|comp|optic|massonly), side
def add(n,s,m,f,k,side): parts.append(dict(name=n,shape=s,mass=m,flag=f,kind=k,side=side))

hw = v("bridge")/2 + v("lens_w") + v("rim_face")
add("bridge", box(-v("bridge")/2,v("bridge")/2,0,v("rim_depth"),v("lens_h")/2-4,v("lens_h")/2), None,"S*V","shell","C")
for side, sx in (("L",-1),("R",1)):
    cx = sx*(v("bridge")/2+v("lens_w")/2)
    ow, oh = v("lens_w")+2*v("rim_face"), v("lens_h")+2*v("rim_face")
    rim = box(cx-ow/2,cx+ow/2,0,v("rim_depth"),-oh/2,oh/2).cut(
          box(cx-v("lens_w")/2,cx+v("lens_w")/2,-1,v("rim_depth")+1,-v("lens_h")/2,v("lens_h")/2))
    add(f"rim_{side}", rim, None, "S*V", "shell", side)
    i = 0.35
    add(f"waveguide_{side}", box(cx-v("lens_w")/2+i,cx+v("lens_w")/2-i,
        v("rim_depth")/2-v("wg_t")/2, v("rim_depth")/2+v("wg_t")/2, -v("lens_h")/2+i, v("lens_h")/2-i),
        WG_MASS, "S", "optic", side)
    ex = sx*(hw+v("end_w")/2)
    add(f"endpiece_{side}", shell(ex-v("end_w")/2,ex+v("end_w")/2,-v("end_l"),v("rim_depth"),
        -v("end_h")/2,v("end_h")/2,v("wall"),open_back=True), None,"S*V","shell",side)
    ty1 = -v("end_l"); ty0 = ty1 - v("temple_len")
    add(f"temple_{side}", shell(ex-v("temple_w")/2,ex+v("temple_w")/2,ty0,ty1,
        -v("temple_h")/2,v("temple_h")/2,v("wall"),open_front=True), None,"S*V","shell",side)
    # 光机(端件内, 后置对准耦入区)
    ey0 = -v("end_l")+v("wall")+0.5
    add(f"light_engine_{side}", box(ex-v("eng_x")/2,ex+v("eng_x")/2,ey0,ey0+v("eng_y"),
        -v("eng_z")/2,v("eng_z")/2), 0.5+0.6, "S+A", "comp", side)
    if side == "L":   # 相机 + 隐私LED(硬连相机供电, 防篡改检测)
        cy1 = v("rim_depth")-v("wall")
        add("camera_L", box(ex-v("cam_xy")/2,ex+v("cam_xy")/2,cy1-v("cam_d"),cy1,
            -v("cam_xy")/2,v("cam_xy")/2), 0.60, "A", "comp", side)
        lz0 = v("cam_xy")/2 + v("min_gap")
        add("privacy_led_L", box(ex-v("led")/2,ex+v("led")/2,cy1-1.0,cy1,lz0,lz0+v("led")),
            0.10, "A", "comp", side)
    # FPC 跨铰链
    fx = ex - sx*1.9
    add(f"fpc_{side}", box(fx-0.075,fx+0.075,ty1-6.0,ey0-0.4,-2.5,2.5), 0.30, "A", "comp", side)
    pl = v("pcbL_len") if side=="L" else v("pcbR_len")
    py1 = ty1-2.0; py0 = py1-pl
    add(f"pcb_{side}", box(ex-v("pcb_stack")/2,ex+v("pcb_stack")/2,py0,py1,-v("pcb_w")/2,v("pcb_w")/2),
        2.60 if side=="L" else 1.40, "A", "comp", side)
    by1 = py0-2.0; by0 = by1-v("bat_len")
    add(f"battery_{side}", box(ex-v("bat_t")/2,ex+v("bat_t")/2,by0,by1,-v("bat_w")/2,v("bat_w")/2),
        2.50, "A(2-3g S)", "comp", side)
    sy1 = by0-2.0
    add(f"speaker_{side}", box(ex-v("spk_t")/2,ex+v("spk_t")/2,sy1-v("spk_len"),sy1,
        -v("spk_h")/2,v("spk_h")/2), 0.90, "A", "comp", side)
    for n,m in (("hinge",0.60),("graphite_spreader",0.30)):
        add(f"{n}_{side}", None, m, "A", "massonly", side)
for n,m in (("mics_x4",0.20),("nose_pads",0.80),("adhesive_screws_gaskets",1.00),
            ("touch_hall_pogo",0.40),("silvergrey_finish",0.30)):
    add(n, None, m, "A", "massonly", "C")

# ---- 质量 ----
for p in parts:
    if p["mass"] is None: p["mass"] = p["shape"].Volume()/1000.0*TR90
total = sum(p["mass"] for p in parts)
side_m = {s: sum(p["mass"] for p in parts if p["side"]==s) for s in "LRC"}

# ---- 空间校核 ----
geo = [p for p in parts if p["shape"] is not None]
issues = []
for a,b in itertools.combinations(geo,2):
    if a["kind"]=="shell" and b["kind"]=="shell": continue
    iv = a["shape"].intersect(b["shape"]).Volume()
    if iv > 1e-6: issues.append(("INTERFERENCE",a["name"],b["name"],round(iv,4)))
    elif a["kind"]!="shell" and b["kind"]!="shell" and a["side"]==b["side"]:
        d = a["shape"].distance(b["shape"])
        if d < v("min_gap"): issues.append(("GAP<min",a["name"],b["name"],round(d,3)))
for p in geo:
    if p["kind"]=="comp" and p["name"].startswith(("speaker","battery","pcb")):
        y_min = p["shape"].BoundingBox().ymin
        if y_min < v("ear_bend_y"): issues.append(("PAST_EAR_BEND",p["name"],"",round(y_min,2)))

res = dict(variant=VARIANT, total_g=round(total,2), reserve_10pct_g=round(total*1.10,2),
           pass_50g=total*1.10<=50.0, pass_40g_no_reserve=total<=40.0,
           side_g={k:round(x,2) for k,x in side_m.items()},
           LR_imbalance_g=round(side_m["L"]-side_m["R"],2), issues=issues,
           assumptions={k:f for k,(_,f) in P.items()})
(OUT/f"evt1_check_{VARIANT}.json").write_text(json.dumps(res,indent=2,ensure_ascii=False))
with open(OUT/f"mass_budget_{VARIANT}.csv","w",newline="") as fh:
    w = csv.writer(fh); w.writerow(["part","side","mass_g","flag"])
    for p in parts: w.writerow([p["name"],p["side"],round(p["mass"],3),p["flag"]])

assy = cq.Assembly(name=f"ZY_EVT1_{VARIANT}")
COL = {"shell":cq.Color(0.75,0.76,0.78,1),"optic":cq.Color(0.6,0.8,1,0.4),"comp":cq.Color(0.2,0.6,0.3,1)}
for p in geo: assy.add(cq.Workplane().add(p["shape"]), name=p["name"], color=COL[p["kind"]])
if ID_MASTER.exists():
    assy.add(cq.importers.importStep(str(ID_MASTER)), name="ID_master_ref", color=cq.Color(1,0,0,0.15))
(assy.export if hasattr(assy,"export") else assy.save)(str(OUT/f"ZY_EVT1_{VARIANT}.step"))
print(json.dumps({k:res[k] for k in ("total_g","reserve_10pct_g","pass_50g","LR_imbalance_g")}))
sys.exit(1 if any(i[0]=="INTERFERENCE" for i in issues) else 0)
```

### 3. 重量预算（按上述参数手算，未运行；resin 基线）

| 部件 | 质量 g | 依据 |
|---|---|---|
| 前框镜圈 ×2（TR90，58×46×5 外框扣除 50×38 窗口） | 7.68 | 体积×1.00 g/cm³ |
| 鼻梁 | 0.36 | 体积×密度 |
| 端件壳 ×2 | 1.25 | 体积×密度 |
| 镜腿壳 ×2（0.8 mm 壁） | 7.69 | 体积×密度 |
| 树脂波导 ×2 | 8.00 | TrendForce：每片约 4 g |
| 光机 ×2（0.5 g 核心 + 0.6 g 支架/散热） | 2.20 | JBD 官方 0.5 g；支架为假设 |
| 主板 L（SoC/PMIC/存储，HDI）/ 副板 R（充电/传感） | 2.60 / 1.40 | 假设 |
| 电池 ×2（约 100 mAh） | 5.00 | 同类电芯 2–3 g（假设取 2.5 g）\[11\]\[12\] |
| 相机模组 + 隐私 LED/导光 | 0.70 | 模组尺寸参照 GC12C1 6.5×6.5 mm；质量为假设\[13\] |
| FPC ×2、扬声器 ×2、麦克风 ×4 | 2.60 | 假设 |
| 铰链 ×2、鼻托、石墨 ×2、胶/螺钉、触控/霍尔/pogo、银灰涂层 | 4.30 | 假设 |
| **合计** | **43.78** | |
| **+10% 成长余量** | **48.16** | ≤ 50 g ✅，余 1.84 g |

- **40 g 路线**：换成 sic035 波导（2×1.98 g，−4.04 g），镜腿壁厚从 0.8 mm 减到 0.6 mm（约 −1.76 g），得到 37.98 g；加 5% 余量为 39.9 g。代价有三：0.35 mm SiC 目前只有预印本级数据；145 mm 长的 0.6 mm TR90 薄壁有充填风险；余量从 10% 降到 5%。结论：**40 g 只能作为挑战目标，EVT-1 按 50 g 冻结。**
- **左右平衡**：左侧多出 PCB 差值 1.2 g、相机和 LED，左重约 1.9 g。建议把右电池加大到约 130 mAh（约 +0.8 g，从余量里出）。这样既改善平衡，也缓解续航问题（见未决项）。

### 4. 空间与热（手算，待脚本和实测确认）

**空间**
- 镜腿内腔 4.9×9.9 mm：电池 4.0×9.0 各边余 0.45 mm ✅；PCB 叠层 2.4×8.5 ✅。
- 左端件内腔 Z 高度：12.5 mm 外形对应内腔 10.9 mm（±5.45）。相机 6.5 mm 加 0.3 mm 间隙加 LED 1.6 mm，LED 顶在 5.15 mm，余 0.30 mm。如果端件只有 12 mm 高，LED 只余 0.05 mm，与壳体近乎相切，所以 **ID 母版端件高度必须 ≥12.5 mm**。
- 光机后端与 FPC 在 Y 向间隙 0.4 mm ✅。
- 镜腿器件末端：L 侧止于 −98 mm，R 侧止于 −86 mm，弯耳点 −107 mm，余量 ≥9 mm ✅。

**热**（集总模型，h=10 W/m²K 为假设，环境 25 °C）

| 模式 | 区域 | 功耗 W | 无均热 | 石墨均热（有效面积 0.0072 m²） | 判定（舒适 40 / TS1 43 °C） |
|---|---|---|---|---|---|
| HUD | 左镜腿（SoC 0.55 + 无线 0.10） | 0.65 | 46.0 °C | 34.0 °C | 必须铺均热 |
| HUD | 端件（光机 0.095） | 0.095 | — | <30 °C | ✅ |
| 拍摄 | 左镜腿（SoC 0.90 + ISP 0.20 + 无线 0.15） | 1.25 | 58+ °C | 42.4 °C | ❌ 超舒适线 → 降频 + 时长限制 |
| 拍摄 | 左端件（光机 0.095 + 传感器 0.10，支架导热） | 0.195 | — | 34.8 °C | ✅ |
| 充电 | 右镜腿（线性充电约 0.24） | 0.24 | — | 28.3 °C | ✅，但电池温度受 JEITA 门控 |

功耗依据：Qualcomm 称 AR 平台（不含显示）的目标功耗低于 1 W；\[14\]Lexar 给出相机加 ISP 约 0.2–0.4 W；\[15\]JBD 光机 95 mW。全机 HUD 约 0.95 W，拍摄约 1.6 W，落在 Meta 论文给出的 1–2 W 可持续区间内。**问题不在总量，而在热量集中在左镜腿。** 皮肤 NTC 降频阈值建议设在 39 °C；Ed.4 下单一故障（如降频失效）也不得超过 TS1，因此需要硬件过温切断，不能只靠软件。

### 5. 假设清单（全部标"假设"，银灰 ID 母版或实测到位后替换）
1. ID 包络：镜片 50×38、鼻梁 18、镜圈面宽 4/深 5、端件 10×12×12.5、镜腿 145×6.5×11.5、壁厚 0.8、弯耳点 −107（银灰 ID 母版尚未读到）。
2. 光机支架/散热 0.6 g/台，光机包络 6×7×5 mm。
3. PCB 质量 L 2.6 g / R 1.4 g，叠层厚 2.4 mm。
4. 电池 100 mAh、2.5 g、4.0×9×28 mm，左右各一，每颗独立保护 IC 和 NTC。
5. 相机 0.6 g，深 4.5 mm；隐私 LED 1.6 mm。
6. 散热系数 h=10 W/m²K；石墨均热有效面积 0.0072 m²；SoC 功耗 HUD 0.55 W / 拍摄 0.90 W。
7. 银灰表面处理 0.3 g（涂装或 PVD 尚未定）。

### 6. P1 R5 原生复核脚本

`native/run_native_checks.sh`（只读，不加 `--refill-zones/--save-board`，避免改写板文件）：\[16\]
```bash
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
```

`native/summarize_native.py`：
```python
#!/usr/bin/env python3
import json, re, sys, collections, pathlib, argparse
ap = argparse.ArgumentParser(); ap.add_argument("out")
ap.add_argument("--selfcheck-before", type=int); ap.add_argument("--selfcheck-after", type=int)
a = ap.parse_args(); out = pathlib.Path(a.out)
drc = json.loads((out/"drc.json").read_text()); erc = json.loads((out/"erc.json").read_text())
by = collections.Counter(v["type"] for v in drc.get("violations", []))
hole = [v for v in drc.get("violations", []) if v["type"] in ("drill_out_of_range","hole_size")
        or "Hole size out of range" in v.get("description","")]
lib = [v for v in drc.get("violations", []) if v["type"] in ("lib_footprint_issues","lib_footprint_mismatch")]
unc = drc.get("unconnected_items", [])
net = (out/"netlist.net").read_text()
m = re.search(r'\(net \(code "?\d+"?\) \(name "([^"]*CHG_PGOOD_N)"\)(.*?)\n\s*\(net ', net, re.S)
nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)) if m else []
pg_unc = [u for u in unc if "CHG_PGOOD_N" in json.dumps(u)]
summary = dict(kicad_version=(out/"kicad_version.txt").read_text().strip(),
  drc_by_type=dict(by), drc_unconnected=len(unc), drc_parity=len(drc.get("schematic_parity", [])),
  hole_size_errors=len(hole), lib_warnings=len(lib),
  erc_by_type=dict(collections.Counter(v["type"] for s in erc.get("sheets",[]) for v in s.get("violations",[]))),
  CHG_PGOOD_N=dict(found=bool(m), net=m.group(1) if m else None, nodes=nodes, unconnected_refs=len(pg_unc)),
  selfcheck_vs_native=dict(selfcheck=[a.selfcheck_before, a.selfcheck_after],
                           native_unconnected=len(unc), note="自检计数≠DRC; 以本文件native值为准"))
(out/"native_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)); print(json.dumps(summary, ensure_ascii=False))
```

**整改规则（执行时遵守）**
- **/CHG_PGOOD_N**：原生网表里必须同时出现充电 IC 的 PG 引脚、上拉电阻、MCU/GPIO 三个节点；DRC 里该网络的 unconnected 必须为 0，才能宣布闭合。上拉电阻**不得标 DNP**。
- **12 个孔径错误（KiCad 的 "Hole size out of range"）**：先在 drc.json 里区分过孔与焊盘孔。对 8.5 mm 宽的镜腿 HDI 板，优先把过孔改成激光微孔（KiCad 的孔径检查不含微孔）并核对叠层；做不到再把机械钻孔放大到板厂最小值以上（常见下限\[17\] 0.2 mm，稳妥值 0.3 mm）。**禁止下调\[18\] Board Setup 最小孔径来消错。**
- **3 个库警告**：`lib_footprint_issues`（库中找不到）的处理是把封装导出到项目库并写入项目 `fp-lib-table`；`lib_footprint_mismatch` 的处理是用 Inspect→Compare Footprint 对比后选定版本，再固化到项目库。**不设\[19\]\[20\] ignore。** 该警告依赖主机全局库配置，因此要固定 kicad 的 docker 镜像版本，并在报告里记录 `kicad_version.txt`。\[21\]
- **未连接**：只能用已恢复的布线器（按 STATE 里的路径调用，本轮不重写），在隔离 POC 的副本上运行；验收条件是 native unconnected 单调不增、shorting 为 0、parity 为 0，之后才合入 R5 主副本。

### 7. 安全门槛（本轮全部保持，未绕过）
- **隐私**：相机供电与隐私 LED 硬件串联或硬连；LED 开路/短路检测和遮挡检测任一触发即禁止录制。Google\[22\]\[23\] 的智能眼镜隐私承诺、Meta v26 更新（LED 被篡改即禁用相机）都是这一做法，可作行业基准。物理断电开关要切断相机和麦克风的供电。\[23\]\[24\]\[25\]
- **充电**：每颗电池配独立保护 IC 和 NTC，JEITA 阈值为 0/10/45/60 °C；两颗电芯不直接并联，除非是同批配对电芯并有均衡方案。另加皮肤侧过温硬件切断，以满足\[26\]\[27\]\[28\] Ed.4 的单一故障要求。
- **DNP**：BOM 用 `kicad-cli sch export bom --exclude-dnp` 导出后做差异检查；NTC、保护\[29\]\[30\] IC、隐私 LED 及其检测电路、PGOOD 上拉都列入"禁 DNP 白名单"，命中即判失败。

### 8. 测试记录（TEST_LOG.md，如实）

| 测试 | 命令 | 结果 |
|---|---|---|
| 装配干涉/间隙/STEP | `python zy_evt1_asm.py resin / sic035` | NOT RUN（无 CadQuery 运行环境、无 ID 母版） |
| 热预算 | `python thermal_budget.py` | NOT RUN；表中数值为手算 |
| 原生 ERC/DRC | `run_native_checks.sh R5/<proj>` | NOT RUN（无 kicad-cli、无工程文件） |
| /CHG_PGOOD_N | summarize_native.py | NOT RUN；58→57 仍是**自检**结论 |
| GitHub | branch + Draft PR + SHA 核验 | NOT RUN（无凭据）；无 SHA |

### 9. 下轮 STATE_FOR_NEXT_SESSION.md
```
# STATE @ 2026-11-12 R5-EVT1 (session after 23:05)
base: PR #3 @ 24facfb (UNVERIFIED this session)   R4: untouched
new: R5/{evt1/cad,evt1/thermal,native}/*  — authored, NOT executed, NOT committed
P0 EVT-1: baseline 43.78 g (+10% = 48.16 g ≤ 50 ✅); 40 g needs sic035 + 0.6 mm wall (37.98 g, risk)
  hand-calc: endpiece_h ≥ 12.5 mm; L-temple graphite mandatory; capture mode 42.4 °C > 40 comfort
P1 R5: /CHG_PGOOD_N native NOT verified (selfcheck 58→57 only); 12 hole + 3 lib + unconnected OPEN
NEXT (in order):
 1. unzip pkg → read previous STATE → confirm tool paths (router, isolation POC, selfcheck)
 2. run native/run_native_checks.sh on R5 copy → commit erc/drc json+rpt as-is
 3. fix hole(→microvia) / lib(→project lib) / unconnected(router on POC copy); rerun native
 4. drop ID master STEP into evt1/cad/ → run zy_evt1_asm.py resin & sic035 → commit out/*
 5. branch r5/evt1-native from 24facfb → Draft PR → verify headRefOid == local HEAD
GATES: privacy LED hardwire+tamper; JEITA per cell + HW overtemp cut; DNP whitelist — never bypass
```

## Recommendations
1. 下一会话第一步：在有文件系统、kicad-cli（固定 docker 镜像）和 gh 凭据的环境里跑第 9 节第 1–2 步。在原生 DRC 给出 /CHG_PGOOD_N 结论之前，不宣布 57。
2. EVT-1 冻结在 **resin 波导 + 50 g 目标**；sic035 只作为并行的 40 g 挑战分支，不进 EVT-1 关键路径。
3. 拍摄模式默认加时长上限和 39 °C 皮肤 NTC 降频，并在 EVT 样机上用热电偶实测左镜腿，校正 h 值。
4. 把右电池加大到约 130 mAh，同时解决左右失衡和续航问题。

## Caveats
- 本轮**没有任何经执行的结果**。重量、空间、温度都是基于假设包络的手算，银灰 ID 母版可能整体改变结论。
- 续航风险：2×100 mAh 约 0.77 Wh，HUD 连续使用只有约 49 分钟，需要占空比策略或更大电池（未决）。\[31\]
- 光机功耗有两个说法：JBD 官方 95 mW，媒体报道 50 mW。0.35 mm SiC 波导数据来自预印本。竞品重量（38 g / 49 g）均为厂商口径。Avegant 对 MicroLED 有效体积的批评出自竞争方。
- 集总热模型忽略了皮肤导热、日照和接触热阻，只能用于排序和设计决策，不能作为合规证据；合规必须按 IEC 62368-1 实测。

## 来源

1. [Assemblies - CadQuery Documentation - Read the Docs](https://cadquery.readthedocs.io/en/latest/assy.html)
2. [cadquery/doc/primer.rst at master · CadQuery/cadquery · GitHub](https://github.com/CadQuery/cadquery/blob/master/doc/primer.rst)
3. [AR's Display Dilemma- A Comparative Study of LCOS vs ...](https://avegant.com/wp-content/uploads/2025/06/AR-Display-Dilemma-A-Comparative-Study-of-LCOS-vs-MicroLED_FINAL.pdf)
4. [SiC diffractive waveguides for augmented reality: single-layer, full-color, rainbow-artifact-free display with vision correction](https://link.springer.com/article/10.1186/s43593-025-00100-1)
5. [\[2609.07648\] A 0.35 mm Silicon Carbide Diffractive Waveguide with Dual Parameter Apodization for Full Color Augmented Reality](https://arxiv.org/abs/2609.07648)
6. [At CES 2026, Meta-Bounds Redefines Lightweight AR with 25g Monocular and 38g Full-Color Binocular Glasses](https://aijourn.com/at-ces-2026-meta-bounds-redefines-lightweight-ar-with-25g-monocular-and-38g-full-color-binocular-glasses/)
7. [\[News\] The Second Half of the AR Glasses Race Begins](https://www.trendforce.com/news/2026/08/18/news-the-second-half-of-the-ar-glasses-race-begins/)
8. [Iec 62368-1-2018 - PDFCOFFEE.COM](https://pdfcoffee.com/iec-62368-1-2018-pdf-free.html)
9. <https://collateral-library-production.s3.amazonaws.com/uploads/asset_file/attachment/61872/62368-1_Ed4_Impact_Analysis_Update_2024_05_10.pdf>
10. [EMS-Grivory Grilamid® TR 90 LS PAMACM12](https://matweb.com/search/DataSheet.aspx?MatGUID=073ae9ac81d64a6eaac120ff53dd7738)
11. [Lithium Ion Polymer Battery - 3.7v 100mAh : Adafruit Industries, Unique & fun DIY electronics and kits](https://www.adafruit.com/product/1570)
12. [Small lipo battery cell 100mAh PD551419](https://www.pdbattery.com/small-lipo-battery-cell-100mah-pd551419.html)
13. [GalaxyCore GC12C1: 12MP Image Sensor Redefining AI Glasses Camera Modules - News - Sincere Information Technology](https://www.cameramodule.com/news/galaxycore-gc12c1-12mp-image-sensor-redefinin-85449338.html)
14. [Qualcomm Is Finally Getting Serious About Non-Dorky Smart Glasses - SlashGear](https://www.slashgear.com/1101755/qualcomm-is-finally-getting-serious-about-non-dorky-smart-glasses/)
15. [Smart Glasses and AR Device Memory Requirements: ePOP5X for Next-Generation Wearable Computing](https://lexarenterprise.com/smart-glasses-and-ar-device-memory-requirements-epop5x-for-next-generation-wearable-computing/)
16. [kicad-copilot/docs/kicad-cli.md at main · biosshot/kicad-copilot · GitHub](https://github.com/biosshot/kicad-copilot/blob/main/docs/kicad-cli.md)
17. [PCB Editor](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)
18. [PCB DRC Checks: Design Rule Errors and How to Fix Them - Zbotic](https://zbotic.in/pcb-drc-checks-design-rule-errors-and-how-to-fix-them/)
19. [Arduino Nano template footprint bug? Error in DRC "Warning: 'EXAMPLE FOOTPRINT FROM ARDUINO' does not match copy in library" - Footprints - KiCad.info Forums](https://forum.kicad.info/t/arduino-nano-template-footprint-bug-error-in-drc-warning-example-footprint-from-arduino-does-not-match-copy-in-library/52700)
20. [Kicad 7 installation - problems - Footprints - KiCad.info Forums](https://forum.kicad.info/t/kicad-7-installation-problems/41308)
21. [Standardise KiCad footprint-library config so native DRC evidence is host-independent (board 03 gained 37 lib\_footprint\_issues from a missing global fp-lib-table) · Issue #6962 · rjwalters/kicad-tools · GitHub](https://github.com/rjwalters/kicad-tools/issues/6962)
22. [Systems and methods for detecting tampering with privacy notifiers in recording systems](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11671695)
23. [Intelligent Eyewear Security and Privacy Commitments - Google Safety Center](https://safety.google/intl/en_US/products/glasses/)
24. [Meta Smart Glasses Make Secret Recording Harder](https://www.androidheadlines.com/2026/07/meta-smart-glasses-secret-recording-privacy-led-cover.html)
25. [Meta Smart Glasses Privacy Update v26: Camera LED Tamper Detection Explained](https://www.smartwearables.io/blog/meta-smart-glasses-privacy-update-v26-camera-led-what-changed-who-should-care-2026)
26. [Application Note Maximizing the Full Potential of NTC Using BQ25180](https://www.ti.com/lit/an/sluaaj8/sluaaj8.pdf?ts=1793545069641)
27. [BQ25176K: 800mA JEITA-Compliant Linear Battery Charger For 1-Cell Li-Ion and](https://www.ti.com/lit/ds/symlink/bq25176k.pdf?ts=1761167512363&ref_url=https%3A%2F%2Fwww.ti.com%2Fsitesearch%2Fen-us%2Fdocs%2Funiversalsearch.tsp%3FlangPref%3Den-US&nr=3&searchTerm=BQ25176KDSGR)
28. [Linear Li-Ion Battery Charger with Power Path and USB Compatibility in LFCSP](https://www.analog.com/media/en/technical-documentation/data-sheets/ADP5062.pdf)
29. [KiCad Command-Line Interface](https://docs.kicad.org/9.0/en/cli/cli.html)
30. [KiCad Command-Line Interface](https://docs.kicad.org/10.0/en/cli/cli.html)
31. [Lithium Ion Polymer Battery - 3.7v 100mAh - Elmwood Electronics](https://elmwoodelectronics.ca/products/lithium-ion-polymer-battery-3-7v-100mah)
