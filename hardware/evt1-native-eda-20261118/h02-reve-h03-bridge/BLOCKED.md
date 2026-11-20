# H02 Rev E → H03 研发 BLOCKED / CONDITIONAL 清单（NOT FOR FAB）

> 当前整机及三块 PCB 仍为 **NOT FOR FAB**，以下 `BLOCKED` 项关闭前禁止投板或释放制造文件。

| 编号 | 类别 | 状态 | 阻断项描述 | 解除条件 |
| --- | --- | :---: | --- | --- |
| `BLK-E1` | **剩余 112 项 `MISSFOOTPRINT`** | **BLOCKED** | 三板严格 ERC 虽已由 `268 → 130`，但仍余 `112` 项 `MISSFOOTPRINT`（`M-MAIN-L 49`, `M-OPT-BRIDGE 28`, `M-AUD-R 35`）：主要包括未获 NDA 图纸的光机/相机连接器、源侧未冻结封装的阻容感、6 颗 DNP 与 4 颗 Off-board 器件；另有 `18` 项 `ONLYSYMBOL` 为嘉立创分层页代理。 | 获取 NDA 器件图纸并冻结全部剩余无源件封装/采购 MPN 后完成最终封装闭环。 |
| `BLK-E2` | **光学与相机原厂 NDA** | **BLOCKED** | JBD013VG 真实 FPC 针位/上电掉电 AVDD 时序、波导光机耦合公差，以及相机模组 SKU 冻结（`ECO-04` 1.2V vs 1.5V DVDD 与 `J_CAM` 引脚定义）均无原厂正式图纸，严禁推测。 | 原厂提供正式 ICD/规格书后冻结 `J1_OPT_L / J2_OPT_R / J_CAM`。 |
| `BLK-E3` | **桥板 `PCB2` 空间瓶颈与 `MECR-01`** | **BLOCKED** | 在严格 `22.0 × 4.2 mm` 原板框下，完成 `17` 颗核心器件实放后，剩余 `U11/U14`、`J_BRIDGE_IN`（即使 ECO-05 `5.47 × 1.70 mm`）及 60+ 无源件无可行槽位（利用率 `94.3%`），无法在原板框内闭环全部 86 器件与 6L VIPPO 布线。 | 结构/ID 审批 [MECR_01_BRIDGE_25x4_6MM.md](MECR_01_BRIDGE_25x4_6MM.md)（放宽至 `25.0 × 4.6 mm`，仅增重 `0.03 g`）并同步冻结 `ECO-05/06`，随后完成全 86 器件布局与 0 DRC 走线。 |
| `BLK-E4` | **`M-MAIN-L` / `M-AUD-R` H03 布局布线与叠层 EQ** | **BLOCKED** | 主板（`PCB1`）与右音频板（`PCB3`）尚未进入完整 H03 布局布线；`ECO-11`（Tier-1 6L 0.60–0.63 mm VIPPO 厂 EQ）、`ANT1/ANT2`（厚 `1.50 mm`）及 `L1_BB`（厚 `1.20 mm`、`Isat=5.5 A`）需整机 ID 3D STEP 干涉与 EVT1 实板 VNA/温升/瞬态验证。 | 冻结 6L 0.60 mm HDI 厂 EQ、完成三板 0 DRC 走线及 3D STEP 干涉签核。 |
| `BLK-E5` | **本地仿真工具链与实物回测** | **CONDITIONAL** | 本机 Windows 无 `iverilog` / `ngspice`，FPGA 仿真/综合/布局布线/STA 已接入 GitHub Actions（`.github/workflows/evt1_native_eda.yml`）在云端运行；硬件级隐私联锁瞬态、双电池切换跌落与 AVDD 掉电保护需 EVT1 实物示波器实测。 | 核验本 PR GitHub Actions `fpga` 与 `native-erc` 绿灯，并在 EVT1 硬件回板后完成示波器验证。 |
