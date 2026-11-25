# 智元跃动 AI/AR 智能眼镜 EVT-1 H03 — PR #47 接管实测与变更报告（NOT FOR FAB）

> **状态声明**：`NOT FOR FAB`（严禁未经审核流片/打样）｜保留 PR #40–#47 全部历史工程、40 g 整机目标与真实双目透明 AR 架构｜严禁降低制造规则或删除必要网络。

## 1. 基线与原生工程交付状态

- **基线来源**：GitHub [PR #47](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/47)（分支 `hardware/codex-evt1-h03-pr46-takeover-20261121`，commit `2c9c8dc6f4e2`，原生基线工程 [ZY_AIAR_EVT1_H03_CODEX_V4_NOT_FOR_FAB.epro2](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/codex-evt1-h03-pr46-takeover-20261121/hardware/evt1-native-eda-20261118/h03-v4-dfm-u11-2n2-route/native/ZY_AIAR_EVT1_H03_CODEX_V4_NOT_FOR_FAB.epro2)）
- **嘉立创 EDA 专业版云端实测工程**：[EVT1-H03-CODEX-PR46-20261121](https://pro.lceda.cn/editor#id=49218390f19d408e857f00938cbf6c78)（账号 `eda_luhqetwc`，网页端版本 V4.1.105，已完成全部保存）
- **操作前云端备份**：`main_PR47_baseline_before_CBB_fix`（在执行任何原理图修改前已通过 `文件 -> 工程备份 -> 创建备份...` 创建）
- **原生 `.epro2` 交付状态**：**未完成（Pending Manual Upload）**
  - **原因**：远程浏览器受管理员策略限制（`Access to local files on your machine is disabled by your administrator`），无法调用本地文件选择器上传二进制 `.epro2` 或在浏览器端执行本地文件独立重导入与 SHA-256 计算。
  - **云端导出路径**：在嘉立创 EDA 专业版中打开上述云端工程，点击顶部菜单 `文件 (F) -> 另存为 -> 工程另存为(本地)(A)...`。
  - **目标仓库存放路径**：`hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/native/ZY_AIAR_EVT1_H03_GEMINI_CBB_FIXED_NOT_FOR_FAB.epro2`
  - **本地 SHA-256**：`[待本地导出后填入 shasum -a 256 / sha256sum 结果]`

## 2. 孤立 CBB 层次引用审计与清理（Netlist Error 3 → 1）

在 PR #47 基线中，三板执行 `设计 -> 从原理图导入变更` 时均被原理图 DRC 致命错误直接拦截，导致 PCB2 与 PCB3 在实际零网表差异的情况下仍持续报 `PCB与原理图网表不一致`。

经逐页检查层级树、图页对象列表与连线状态，确认三板顶层汇总页上的 18 个 `CBB` 复用模块符号均**无底层原理图页、未连接任何导线/网络/端口**，而全部真实电路均位于同级平铺图页中：

| 板卡 | 顶层汇总页 | 已清理孤立 CBB 符号 | 保留的同级真实电路图页 | 工程库副本处理 |
| :--- | :--- | :--- | :--- | :--- |
| **PCB1** (`evt1-main-left`) | `8. evt1-main-left` | `CBB1` ~ `CBB7`（7 个） | 第 1 ~ 7 页完整保留 | 全部保留（取消删除库副本） |
| **PCB2** (`evt1-optical-bridge`) | `7. evt1-optical-bridge` | `CBB1` ~ `CBB6`（6 个） | 第 1 ~ 6 页完整保留 | 全部保留（取消删除库副本） |
| **PCB3** (`evt1-audio-right`) | `6. evt1-audio-right` | `CBB1` ~ `CBB5`（5 个） | 第 1 ~ 5 页完整保留 | 全部保留（取消删除库副本） |

## 3. 三板 ERC、Import Changes 与 DRC 实测对比

清理 18 个孤立 CBB 符号后，依次执行原理图 DRC（ERC）、`从原理图导入变更`、`设计 -> 检查DRC` 及 `文件 -> 保存全部`，未降低任何制造规则，未删除任何有效器件或网络：

| 板卡 | 器件数（前 / 后） | 未连通飞线（前 / 后） | 间距错误（前 / 后） | Netlist Error（前 → 后） | 原理图 ERC 致命错误（前 → 后） | Import Changes 实测结果 |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **PCB1** (`evt1-main-left`) | 118 / **118** | 358 / **358** | 0 / **0** | 1 → **1** | 11 → **4** | 被 `J2/J3/SPK1/BAT1` 缺封装阻断（保持 `J2`/`J3` 为 `BLOCKED` 且 `转到PCB=是`，未伪装闭环） |
| **PCB2** (`evt1-optical-bridge`) | 86 / **86** | 237 / **237** | 0 / **0** | 1 → **0** | 6 → **0** | 成功应用（仅含 `新增属性` 与 `修改属性`，无器件或网络增删） |
| **PCB3** (`evt1-audio-right`) | 53 / **53** | 134 / **134** | 0 / **0** | 1 → **0** | 7 → **0~2** | 成功应用（仅含 `新增属性` 与 `修改属性`，无器件或网络增删） |
| **三板合计** | **257 / 257** | **729 / 729** | **0 / 0** | **3 → 1** | **CBB 致命错误全部清零** | **总 DRC 错误 732 → 730，电气数据零丢失** |

- **PCB2 器件组成确认（86 个）**：`C: 33, D: 1, J: 3, MK: 1, R: 31, TP: 1, U: 15, Y: 1`。
- **PCB3 器件组成确认（53 个）**：`ANT: 1, C: 23, J: 1, L: 4, MK: 1, Q: 1, R: 10, TP: 6, U: 4, Y: 2`。

## 4. PCB1 `J2 (J_CAM)` 与 `J3 (J_CHG)` 核查记录

两颗接口器件均严格保持 **`BLOCKED`** 与 `转到PCB=是`，未通过修改 `转到PCB=否` 伪装网表闭环：

| 位号 | 器件名 / 唯一 ID | 原理图引脚与网络 | 料号与官方规格核查 | 当前状态 |
| :--- | :--- | :--- | :--- | :--- |
| **J2** (`J_CAM`) | `EVT1_J2_J_CAM` / `1fb9863844ab5169` | 26 引脚（`P1~P24` 信号 + `PWR1~PWR2` 电源，含 `CAM_AVDD_2V8`、`CAM_DVDD_1V2`、`CAM_DOVDD_1V8`、`CAM_SCCB_*`、`CAM_D0~D7` 等） | 核实广濑官方料号 [BM28B0.6-24DS/2-0.35V(53)](https://www.hirose.com/en/product/p/CL0673-5025-0-53)（CL0673-5025-0-53，参见 [Farnell 规格页](https://uk.farnell.com/hirose-hrs/bm28b0-6-24ds-2-0-35v-53/conn-stacking-rcpt-24s-2p-2row/dp/3361103)）：双排 SMT 堆叠母座，**24 路信号 + 2 路电源 = 26 脚**，`0.35 mm` 节距，`0.6 mm` 堆叠高度，镀金铜合金，支持 20 Gbps，10 次插拔寿命 | **BLOCKED**（引脚数与原理图一致，待传感器侧 FPC 针位与官方 Land Pattern 冻结后再建封装） |
| **J3** (`J_CHG`) | `EVT1_J3_J_CHG` / `bd3ee0abdb58119f` | 4 引脚（`1: VBUS_5V_USB`、`2: USB_DM`、`3: D+`、`4: GND`） | `MPN_TBD (4-pos magnetic pogo: VBUS, D-, D+, GND)`，当前工程库封装为 0 | **BLOCKED**（等待真实 4 针磁吸充电接口选型与机械图纸） |

## 5. PCB2 去耦告警与联合布局研究（保持 PR #47 零间距错误基线）

- **功能性 RC 保留**：`C2`（`U11.3` `AVDD_QUAL_RC` 定时 RC）与 `C3`（`U13.3` `AVDD_REQ_FILTER` 滤波 RC）全程未做任何改动。
- **实测约束分析**：
  - PCB2 为超窄光学桥板（板宽约 `160 mil` ≈ 4 mm，长约 `900 mil`），当前锁定间距规则为：导线-导线 `0.05 mm`，导线-贴片焊盘 / 贴片焊盘-贴片焊盘 / 过孔-其他 `0.152 mm`（6 mil），钻孔-其他 `0.176 mm`，铺铜/内电层 `0.254 mm`，板框-其他 `0.3 mm`。
  - 实测将 8 颗去耦电容（`C5`、`C8`、`C9`、`C10`、`C11`、`C12`、`C31`、`C32`）从顶层顶部区域移近对应底层 IC 时，由于顶层已被 QFN/0201 焊盘与走线占满、底层被 AVDD 逻辑 IC 与 `FPGA_C...` 竖向走线束占满，直接移位会引发 51~58 项间距错误并断开已有短线。
  - 已通过 `文件 -> 历史记录` 将 PCB2 完整恢复至 PR #47 干净基线（0 间距错误、237 未连通），随后结合 CBB 清理完成网表同步（Netlist Error `1 -> 0`）。
- **后续联合优化方案**：须将 `FPGA_C...` 竖向走线束整体迁移至内层信号层（配合完整内电层地参考），在底层为 `U5/U6/U10~U14` 释放紧邻 IC 电源引脚与就近 GND 回流孔的合法 0201 布局窗口；仅当联合重布后实测 DRC 零新增违规且回流阻抗满足约束时方可落盘。

## 6. PCB3 真实层叠核查与 U11（0.35 mm WLCSP）板厂 EQ 方案

严守“不得将默认 1.7873 mm 六层叠层认定为 0.80 mm HDI，也不得擅自切换 2+N+2 或降低制造规则”的要求，以下为嘉立创 EDA 专业版内实测参数与板厂 EQ 必备确认项：

### 6.1 实测现状（非 0.80 mm 2+N+2 HDI）
- **当前物理堆叠**：标准 6 层 **`JLC06161H-3313(默认)`**（1+4+1 结构，总厚 **`1.7873 mm`**；L1 顶层信号、L2 内层1内电、L3/L4 内层2/3信号、L5 内层4内电、L6 底层信号，各层铜厚 `0.035 mm`）。
- **当前盲孔定义（`blindVia [默认]`）**：仅定义 1 阶盲孔 `BV_L1_L2`（L1→L2）与 `BV_L5_L6`（L5→L6），且“过孔尺寸”绑定栏为空，**无 L2→L3 / L4→L5 二阶盲孔定义**。
- **当前锁定设计规则（`自定义配置2`）**：最小线宽 `0.05 mm`，最小过孔焊盘 `0.18 mm` / 孔径 `0.075 mm`，焊盘/过孔/导线间距 `0.152 mm`（6 mil），钻孔间距 `0.176 mm`，无 U11/BGA 专用区域规则。
- **U11 几何阻断**：[nRF5340-CMAA WLCSP95](https://www.yic-electronics.com/blog/QFN-vs-WLCSP-vs-BGA-Differences,PCB-Design,and-BLE-Applications.html) 封装尺寸 `4.390 × 3.994 mm`、95 球、`0.35 mm` 节距、标称高度 `0.449 mm`（MSL 1，且侧面与锡球侧需可见光/近红外避光防护）。在 `0.35 mm` 球距下，相邻焊盘边缘净距仅约 `0.15~0.17 mm`，在锁定 `0.152 mm` 铜距与 `0.18 mm` 过孔焊盘规则下，几何上无法完成内圈穿线或居中盲孔逃线。

### 6.2 板厂 EQ 必备参数清单（签核通过前保持 BLOCKED）
1. **目标叠层与板厚**：向板厂发起 `0.80 mm`（±10%）总厚 **2+N+2 顺序压合 HDI**（6 层或 8 层）叠层 EQ，明确各介质层厚度、玻纤型号与 50 Ω 单端 / 90–100 Ω 差分阻抗计算表。
2. **微盲孔与盘中孔（VIPPO）工艺**：确认 L1–L2 与 L2–L3 错位/叠孔激光微盲孔能力（目标激光孔径 `0.075~0.10 mm`、焊盘 `0.18~0.20 mm`），并确认 [盘中孔 VIPPO（IPC-4761 Type VII 树脂塞孔电镀填平）](https://jlcpcb.com/blog/via-in-pad-pcb) 良率、平整度与最小环宽公差。
3. **BGA 局部区域规则审批**：申请仅限于 U11 WLCSP 区域内的局部线宽/线距与铜距规则（如 `0.075 mm / 0.075 mm` 即 3/3 mil 或板厂 HDI 阶梯能力）书面 EQ 签核，全局其余区域维持现有锁定规则。
4. **避光与装配约束**：确认 WLCSP 侧面/底部避光方案（封装胶或结构遮光件）、ENIG 表面处理及 X-Ray 抽检要求，并评估对 40 g 整机重量目标的影响。

## 7. 本地一次性提交与创建 Draft PR 指引

请在本地完成以下步骤，将云端导出的 `.epro2`、本地计算的 SHA-256 与本目录下的 `README.md`、`BLOCKED.md` 一并提交至基于 PR #47 的独立 Draft PR：

```bash
# 1. 检出 PR #47 基线并创建独立分支
git fetch origin hardware/codex-evt1-h03-pr46-takeover-20261121
git checkout -b hardware/gemini-evt1-h03-pr47-takeover-20261121 origin/hardware/codex-evt1-h03-pr46-takeover-20261121

# 2. 放置文件（将本地导出的 .epro2 与本回复生成的 README.md / BLOCKED.md 放入目标目录）
mkdir -p hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/native
cp /path/to/README.md hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/README.md
cp /path/to/BLOCKED.md hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/BLOCKED.md
cp /path/to/exported.epro2 hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/native/ZY_AIAR_EVT1_H03_GEMINI_CBB_FIXED_NOT_FOR_FAB.epro2

# 3. 计算本地 SHA-256 并记录到 SHA256SUMS.txt（同步回填到 README.md 第 1 节）
shasum -a 256 hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/native/ZY_AIAR_EVT1_H03_GEMINI_CBB_FIXED_NOT_FOR_FAB.epro2 \
  > hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/SHA256SUMS.txt

# 4. 提交并推送分支
git add hardware/evt1-native-eda-20261118/h03-v4-gemini-pr47-takeover/
git commit -m "hardware(evt1-h03): clean 18 orphan CBB blocks (netlist errors 3->1), add J2/PCB2/PCB3 EQ audit"
git push -u origin hardware/gemini-evt1-h03-pr47-takeover-20261121

# 5. 创建基于 PR #47 的独立 Draft PR
gh pr create --draft \
  --base hardware/codex-evt1-h03-pr46-takeover-20261121 \
  --head hardware/gemini-evt1-h03-pr47-takeover-20261121 \
  --title "[Draft][NOT FOR FAB] EVT-1 H03 PR #47 Takeover: CBB Fix (Netlist Error 3->1) & J2/PCB2/PCB3 EQ Audit" \
  --body "基于 PR #47 (commit 2c9c8dc6f4e2) 清理 18 个孤立 CBB 模块符号，PCB2/PCB3 Netlist Error 清零（3->1），257 器件零丢失、0 间距错误，附 J2 料号核查、PCB2 联合布局研究、PCB3 真实层叠与板厂 EQ 清单及剩余 BLOCKED。保留 NOT FOR FAB、40g 目标与双目透明 AR。"
```
