# EVT-1 H02 → H03 研发 BLOCKED / CONDITIONAL 清单（NOT FOR FAB）

> 当前整机及三块 PCB 均处于 **NOT FOR FAB** 状态，以下任一 `BLOCKED` 项未关闭前禁止释放 Gerber/BOM/贴片生产文件。

| 类别 | 编号 | 状态 | 阻断项描述 | 解除条件 |
| --- | --- | --- | --- | --- |
| **原生封装与严格 ERC** | `BLK-01` | **BLOCKED** | 三板仍余 `228` 项 `MISSFOOTPRINT`（`M-MAIN-L 105`, `M-OPT-BRIDGE 72`, `M-AUD-R 51`）：含 `93` 颗 0201/0402 无源通用件、`125` 颗源侧未冻封装 IC/连接器/天线、`6` 颗 DNP、`4` 颗 Off-board 器件；另有 `18` 项 `ONLYSYMBOL` 为嘉立创分层页代理对象。 | 冻结无源件采购 MPN、完成剩余 IC/连接器原厂焊盘核验并绑定，确认 DNP/Off-board 排 BOM/排 PCB 策略。 |
| **改网表型 P0/P1 ECO** | `BLK-02` | **BLOCKED** | `ECO-03`（FPGA `TPS3895ADRYR` 上电时序）、`ECO-07`（USB `TPS2553DRVR` + **修正 `61.9 kΩ 1%`**）、`ECO-08`（nRF5340 `32.768 kHz` LFXO）、`ECO-09`（删重复 `R_ESP_BOOT` + 浮空下拉）、`ECO-14`（`U12_ESD_USB` 原理图符号缺 GND 脚）均涉及增删器件或修改网络，本轮未单边破坏 201/1075/92 受控基线。 | 在下一轮 H02 Rev E 同步变更窗口中统一更新原理图、Protel2 网表与受控基线清单，重跑全三板对账。 |
| **光学与相机原厂 NDA** | `BLK-03` | **BLOCKED** | JBD013VG 真实 FPC 针位/上电掉电 AVDD 时序、波导光机耦合公差、以及相机模组 SKU 选型（`ECO-04` 1.2V vs 1.5V DVDD 与 `J_CAM` 引脚定义）仍待原厂 NDA 资料。 | 获取 JBD 与相机模组原厂正式图纸，冻结 `J1_OPT_L / J2_OPT_R / J_CAM` 连接器针位和电源时序。 |
| **桥板 PCB2 物理布局与 DRC** | `BLK-04` | **BLOCKED** | 实时原生 `PCB2` 严格 DRC 仍存 `66` 项（59 飞线、4 项 `MK2` 焊盘距声孔槽 `5.3 mil < 6 mil`、2 项内层负片平面距声孔槽 `< 10 mil`、1 项 `Import Changes` UniqueID 未配对）；BOT 面最大连续空档仅 `3.34 mm`，无法放入 `J_BRIDGE_IN`（20+2P `5.47 mm` / 30+2P `7.22 mm`）；83 器件按严格 `22.0×4.2 mm`（含 ECO-05/06 缩封）Courtyard 利用率高达 `91.6%`。 | 联合 ID 决策 `22.0×4.2`（需迁移 U8/Y1 并冻结 ECO-05/06）或 `25.0×4.6`（73.1% 利用率）；重做 MK2 Ø0.80 mm 声孔封装与 L2/L5 防焊盘；对齐 SCH/PCB UniqueID 并完成 6L VIPPO 实走线与 0 DRC。 |
| **主板 / 右音频板 H03 PCB** | `BLK-05` | **BLOCKED** | `M-MAIN-L`（`PCB1`）与 `M-AUD-R`（`PCB3`）尚未进入完整 H03 布局布线；`ANT1 / ANT2`（`2450AT18B100E` 实测厚 `1.50 mm`）与 `L1_BB`（`DFE201612E-R47M=P2` 厚 `1.20 mm`、`Isat=5.5 A`）需整机 ID Z-高度与 EVT1 实测确认。 | 冻结 6L 0.60–0.63 mm Tier-1 HDI 叠层 EQ（`ECO-11`）、3D STEP 装配干涉检查及 EVT1 实板 VNA/温升/瞬态测试。 |
| **本地仿真工具链** | `BLK-06` | **CONDITIONAL** | 本机 Windows 环境未安装 `iverilog` 与 `ngspice`（已执行全部 Python 电气/AVDD/H02 回归验证；FPGA Verilog 测试台由 GitHub Actions `.github/workflows/fpga_eda_ci.yml` 在 PR 上运行）。 | 查看本 PR 远端 GitHub Actions FPGA CI 运行结果，并在 EVT1 硬件回板后完成实测示波器验收。 |
