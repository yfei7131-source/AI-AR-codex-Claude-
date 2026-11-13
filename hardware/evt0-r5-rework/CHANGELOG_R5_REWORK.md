# evt0-r5-rework 变更日志（基线：R4 PCB sha256 8bd12a6f…，只读未改；R5实验板 229d4790…，只读未改）
工具均为文本级编辑，自检用 zy_pcb（**非 KiCad 原生**）。
| 步骤 | 改动 | 自检(zy_pcb) |
|---|---|---|
| S0 | 复制R4工程到 evt0-r5-rework（去 evidence/gen） | 基线 58缺口 / 12孔径错误 |
| S1 | /CHG_PGOOD_N 9段+1过孔自R5实验板原样迁入（块文本逐字一致，UUID不变）；清空2块平面 filled_polygon（zone定义/规则保留），须KiCad重铺 | 58→57 |
| S2 | U1.41 的12个孔 0.20→0.30mm（焊盘0.6不变，环宽0.15，孔间净距≥0.69）；0.30板规未改 | 孔径错误 12→0 |
| S3 | 新建 aiar_fp.pretty（U1/J3/J1实际封装），fp-lib-table、PCB lib id、原理图实例+符号缓存、aiar.kicad_sym、BOM封装列同步；PCB与原理图84个位号封装ID无不一致 | — |
| S4 | J3 GND：J3.2/J3.15/MP×2 各加0.3mm F.Cu短线+独立过孔（非via-in-pad） | 57→53 |
工具修复：pcb_edit 补 clear_zone_fills、set_fp_lib 头部匹配；verify_rework 编码/JSON键。
相对R4：新增18个seg/via，删除0；UUID无重复；filled_polygon 2→0。
## 验证状态
- 原生 ERC/DRC：**NOT RUN**（沙箱无 kicad-cli）。必须在KiCad中 `--refill-zones` 后跑 ERC/DRC（--severity-all --schematic-parity）；原理图版本头仍为 eeschema 8.0 格式，KiCad 10 打开会升级。
- 未重铺的板不含内层铜；**禁止直接出Gerber**。新PGOOD过孔/J3过孔与In1/In2铺铜间距、短路均未经原生验证。
- 未做：VBUS、USB DP/DM、其余53个未连接。非生产放行。

## 第二轮（本窗口；S0–S4 未重做，输入PCB ec8419f1…）
- 原生检查脚本修复：run_native_checks.sh 在临时副本上跑、加 --refill-zones/--save-board、记录各步退出码、校验输入哈希、无 kicad-cli 写 NOT RUN 并退出2；summarize_native.py 缺文件时报 NOT RUN、修正 PGOOD 节点正则。已实跑：**NOT RUN**（evidence/native_NOTRUN/）。
- S5 VBUS：J1.A4/B9 经 7 段 0.3mm F.Cu 并入主 VBUS（缺口 1→0）。
- S5 VSYS：J4.2(DNP实验排针) 经 8 段 0.3mm F.Cu 并入 VSYS（缺口 1→0）。使用现有 r5_route/rw_route，未重写布线器；UUID见 evidence/step5_vbus_vsys/added_copper.json。
- 缺口 53→51；zy_pcb 违规 0；新PCB sha256 前缀 dc5f98a7。
- USB DP/DM（各4缺口）：**未布线**。现有布线器不具备差分耦合、等长与阻抗控制，叠层/阻抗仍未确认，单根自动布线不能当作合规差分对。

## 第三轮（PCB不变，前缀 dc5f98a7）
- 原生 ERC/DRC/覆铜重铺：再次执行 run_native_checks.sh → **NOT RUN**（无 kicad-cli），证据 evidence/native_NOTRUN_r3/NATIVE_STATUS.txt，退出码2。
- USB_DP/DM：**阻断，未布线**，见 USB_DIFF_BLOCKERS.md（无叠层/阻抗参数；USB类过孔钻孔0.25低于板规0.30）。
- 1处悬空线：GND 短线 (130.5,117.95)-(130.25,118.0) 末端 (130.25,118.0)，R4既有，未改动，待原生DRC确认。
- GitHub Draft PR：未创建（无网络/gh）。

## 第四轮（2026-11-13 新窗口）：S6 GND悬空短线整改 → R5 S0–S6 r4
- P0：入包PCB SHA256 `dc5f98a7b45f…`、SCH `81d599e6d107…` 与STATE一致；R4/R5-experimental 历史工程未触碰。
- P1 原生检查：`tools/run_native_checks.sh` → **NOT RUN**（全盘搜索无 kicad-cli/pcbnew/KiCad安装，无网络），退出码2。证据 `evidence/native_NOTRUN_r4_1357/`（对r3板；目录后缀1357仅为标签，非时间，权威时间戳见其 NATIVE_STATUS.txt，UTC 06:40:26）与 `evidence/native_NOTRUN_S6/`（对本版r4板，input_sha256 已记录新哈希）。ERC/DRC/覆铜重铺/parity 均未运行，不得称通过。
- **S6**：删除 /GND F.Cu 短线 uuid `40b55a19-717e-4c55-bdad-0284887652bf`，(130.5,117.95)→(130.25,118.0)，宽0.3，长0.255mm。依据：起点在焊盘 D1.2（GND）中心；终点距 D1.2 焊盘边缘 0.025mm 在焊盘外、不触任何同网对象 → 悬空；D1.2 另由 uuid 8cfd814c（→(131,117.75)）连入唯一GND簇，故冗余。仅删除一个segment块（-157字节/-8行，见 `evidence/step6_gnd_stub/S6_diff.patch`），未新增任何铜、未改任何规则/封装/原理图。
- S6 模型内验证（zy_pcb，**非KiCad原生**）：缺口 51→51（逐网一致）；悬空 1→0；违规 0→0；GND 簇仍为单簇(217项)含 D1.2；uuid 无重复；verify_rework S1–S4 回归项不变。证据 `evidence/step6_gnd_stub/`、`evidence/verify_rework_after_step6.json`。
- 新 PCB SHA256 `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`（前缀 c0f1ca5c）；SCH 不变。
- 同时撤销本窗口早先误放的 `STATE_R5_REWORK_session4_addendum.md`（重复且过时的STATE副本）。
- 未新增任何替代检查器；仅复用项目自带 pcb_edit/zy_pcb/selfcheck/verify_rework。
- USB_DP/DM 仍阻断；GitHub 无网络，未创建 Draft PR，无 Commit SHA。

## 第五轮（2026-11-13 H02，Kimi 窗口，独立分支 hardware/evt0-r5-h02h03-kimi-20261113）
- P0 基线核对：PCB `c0f1ca5c…`、SCH `81d599e6…` 与 PR#5 记录一致；R3/R4 原版、DNP、规则、隐私联锁均未触碰。
- P1 原生检查：`tools/run_native_checks.sh` → **NOT RUN**（本机无 KiCad/kicad-cli，退出码2），证据 `evidence/native_NOTRUN_h02_20261113/`。ERC/DRC/覆铜重铺/parity 均未运行，不得以自检代替。
- 优先项实测（zy_pcb，非原生）：J3 两条GND短线净距恰=规则0.200mm（0.5mm排距+DRU电源最小线宽0.3几何强制，缩线宽违规、移过孔不改y向净距）→ 保留并标记原生复核；PGOOD 最差为两段对 CHG_EN1 过孔净距0.185（规则0.15，余量+0.035）合规；S5 VSYS/VBUS 新铜15项最小余量+0.05，/VSYS /VBUS 缺口0。
- H02 route A（rw_route，既有工具）：CAM_PWDN/RST_N/SIOC/SIOD/HREF 连通，51→43；CAM_VSYNC 未布。
- H02 route B：CAM_DOVDD 连通1/6，43→42；CAM_2V8/CAM_DVDD 未布。
- H03 route C：电源 plane 模式重试无进展（42→42，回滚）。
- H03 route D：AUD_UART_RX/TX、DISP_CLK/CS/D0/D3/RST 连通，42→34；DISP_D1/D2 未布、DISP_PWR_EN 余1。
- H03 route E：CAM_Y2/Y3/Y4/Y5、CAM_XCLK_R、CAM_PCLK_R 连通，34→28；Y6–Y9/XCLK/PCLK 未布。
- 手动绕行评估（manual_copper --dry 干跑，未写入）：CAM_2V8 北侧绕行14项违规（GND/PWDN/SIOD阻挡、穿越J3焊盘），确认拥堵，放弃手动布线，不留未验证铜。
- 每批次自检：drc_lite(new)=0、dangling(new)=0、verify_rework S1–S4 回归通过；UUID 1694 无重复。
- PCB SHA256 演进：c0f1ca5c → f611f228(A) → 0a5dbabc(B) → 44f17fe5(D) → c8aceeaf(E)。
- USB_DP/DM 仍阻断（USB_DIFF_BLOCKERS.md）；原生 ERC/DRC/重铺仍 NOT RUN；**不得出Gerber，非生产放行**。
