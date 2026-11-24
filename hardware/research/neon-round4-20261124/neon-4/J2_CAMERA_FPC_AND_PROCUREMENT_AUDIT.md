# J2（摄像头 FPC 连接器）原厂依据、逐针映射、保护电路与多渠道采购核实

## 1. 原厂依据与双向配对关系核验

| 参数项 | 主板插座（PCB1 端） | FPC 配对插头（模组端） | 权威来源 |
| :--- | :--- | :--- | :--- |
| **MPN / Hirose CL 料号** | `BM28B0.6-24DS/2-0.35V(53)` / `CL0673-5025-0-53` | `BM28B0.6-24DP/2-0.35V(53)` / `CL0673-5024-0-53` | [Hirose CL0673-5025-0-53](https://www.hirose.com/en/product/p/CL0673-5025-0-53)<br>[DigiKey 7793566](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DS-2-0-35V-53/7793566) / [7793554](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DP-2-0-35V-53/7793554) |
| **官方双向配对验证** | 双向确认为官方 Mating Product | 双向确认为官方 Mating Product | DigiKey Associated Products & [Hirose BM28 Catalog](https://www.hirose.com/en/product/series/BM28/documents?path=%2Fapi%2Fv1%2Fseries%2FBM28%2Fdocuments%2Fproduct_series_catalog%2Fcontent%3Flang%3DEN) |
| **外形尺寸与合高** | `6.8 ± 0.2 × 1.7 ± 0.2 × 0.6 ± 0.1 mm`（DigiKey 标板高 `0.61 mm`） | 板高 `0.46 mm`（长宽需见原厂 DP 图纸）；**配对总高 `0.6 ± 0.1 mm`** | [Hirose 2D 图纸 EDC-364666-53-00](https://www.hirose.com/en/product/p/CL0673-5025-0-53/documents?path=%2Fapi%2Fv1%2Fproducts%2FCL0673-5025-0-53%2Fdocuments%2Fdrawing_2d%2Fcontent%3Flang%3DEN) |
| **额定电流 / 电压** | 信号 `0.3 A` / 电源 **`5.0 A`**；`AC/DC 50 V`（耐压 `150 V AC / 1 min`） | 同 BM28 系列规格 | [Hirose Spec Sheet](https://www.hirose.com/en/product/p/CL0673-5025-0-53/documents?path=%2Fapi%2Fv1%2Fproducts%2FCL0673-5025-0-53%2Fdocuments%2Fspec_sheet%2Fcontent%3Flang%3DEN)（注：嘉立创页面摘要 300 mA/30 V 偏保守，以原厂为准） |
| **接触电阻 / 温区 / 寿命** | 信号 `≤70 mΩ`、电源 `≤15 mΩ`；`-55°C ~ +85°C`；**插拔寿命仅 `10 次`** | 同系列规格 | Hirose Spec Sheet（**EVT 调试严禁频繁插拔**） |
| **防反插与内部连接** | 同端 2 电源焊盘（`[25, 26]`、`[27, 28]`）内部一体直通，两端 LCP 绝缘；**100% 中心对称、无防呆键、无 Pin 1 丝印** | 完全对称无防呆键 | Hirose 2D 图纸 Detail C & [PR #54 `J2_HIROSE_AUDIT.md`](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/hardware/evt1-h03-r6-codex-20261123/hardware/evt1-native-eda-20261118/h03-codex-r6-20261123/pcb1/J2_HIROSE_AUDIT.md) |

---

## 2. 实际采购条件多渠道核实（2026-11-23 远程浏览器实时数据）

| 器件 | 渠道 | 料号 | 状态 | 实时现货 | MOQ | 阶梯单价（USD） | 标称交期 / MSL / RoHS |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **J2 插座**<br>`BM28B0.6-24DS/2-0.35V(53)` | **JLCPCB** | [`C5577343`](https://jlcpcb.com/partdetail/6495731-BM28B0_6_24DS_2_0_35V_53/C5577343)（扩展库） | 在售 | `153`（可订 `151`） | `1` | 1+ `$1.5660`｜100+ `$0.9917`｜1k+ `$0.8853` | 现货直接贴片 |
| **J2 插座**<br>`BM28B0.6-24DS/2-0.35V(53)` | **DigiKey** | [`H125603CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DS-2-0-35V-53/7793566) | `Active` | **`4,544`** | `1`（TR `1,000`） | 1+ `$1.67`｜10+ `$1.423`｜100+ `$1.2092`｜1k+ `$1.0278` | 原厂 `20 Weeks` / MSL `1 (Unlimited)` / `ROHS3` |
| **J2 配对插头**<br>`BM28B0.6-24DP/2-0.35V(53)` | **JLCPCB** | [`C3653707`](https://jlcpcb.com/parts/componentSearch?searchTxt=BM28B0.6-24DP%2F2-0.35V%2853%29)（扩展库） | 预购 | **`0`** | `9` | 预估 `$1.0751` | 无现货，仅作备选 |
| **J2 配对插头**<br>`BM28B0.6-24DP/2-0.35V(53)` | **DigiKey** | [`H125591CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DP-2-0-35V-53/7793554) | `Active` | **`2,862`** | `1`（TR `1,000`） | 1+ `$1.65`｜10+ `$1.403`｜100+ `$1.1922`｜1k+ `$1.0133` | 原厂 `20 Weeks` / MSL `1 (Unlimited)` / `RoHS` |

**采购结论**：板端插座可直接走 JLCPCB `C5577343` 贴片（现货 `153`）；FPC 配对插头若需制作 EVT 测试转接板或供模组厂贴装，可直接从 DigiKey 采购 `H125591CT-ND`（现货 `2,862`，MOQ 1），不再受嘉立创 `C3653707` 零库存卡脖子。注意原厂标准交期为 **20 周**，进入 DVT 前须提前锁单。

---

## 3. 28 物理焊盘 ↔ 26 逻辑端子逐针映射（严禁猜测未确认极性）

- **封装几何基准（`EDC-364666-53-00`）**：信号焊盘 `1–24` 为 `0.18 × 0.31 mm`（节距 `0.35 mm`，跨距 `3.85 mm`，内距 `1.18 mm`，外距 `1.80 mm`）；端部电源焊盘 `25–28` 为 `0.53 × 0.33 mm`（中心距 `5.26 mm`，内距 `1.24 mm`，外距 `1.90 mm`）；钢网 `0.08 mm`（80 µm）；顶层两排焊盘之间强制加 **`NO CONDUCTIVE TRACE`** 禁布区；阻焊开窗（`0.17 mm` 间隙）提交板厂 EQ。

| 实体焊盘（`C5577343`） | 逻辑端子 | R6/R7/R8 网络名 | 额定电流 | 状态 |
| :---: | :---: | :--- | :---: | :--- |
| `1` | `P1` | `CAM_AVDD_2V8` | `0.3 A` | 待核对模组 FPC Pin 1 针序 |
| `2`, `7`, `9`, `11`, `24` | `P2, P7, P9, P11, P24` | `GND` | `0.3 A` | 待核对模组 FPC 针序 |
| `3`, `4` | `P3, P4` | `CAM_SCCB_SCL`, `CAM_SCCB_SDA` | `0.3 A` | 待核对模组 FPC 针序 |
| `5`, `6` | `P5, P6` | `CAM_RESET_N`, `CAM_PWDN` | `0.3 A` | 待核对模组 FPC 针序 |
| `8`, `10` | `P8, P10` | `CAM_XCLK_1V8`, `CAM_PCLK_1V8` | `0.3 A` | 待核对模组 FPC 针序 |
| `12`, `13` | `P12, P13` | `CAM_VSYNC_1V8`, `CAM_HREF_1V8` | `0.3 A` | 待核对模组 FPC 针序 |
| `14`, `15` | `P14, P15` | `CAM_DVDD_1V2`, `CAM_DOVDD_1V8` | `0.3 A` | 待核对模组 FPC 针序 |
| `16`–`23` | `P16`–`P23` | `CAM_D0_1V8` – `CAM_D7_1V8` | `0.3 A` | 待核对模组 FPC 针序 |
| **`25`, `26`（高 X 侧同端内部直通）** | **`PWR1` 或 `PWR2`** | **`CAM_AVDD_2V8` 或 `GND`**（必须同网） | `5.0 A` | **BLOCKED（需模组图纸与四线通断实测）** |
| **`27`, `28`（低 X 侧同端内部直通）** | **`PWR2` 或 `PWR1`** | **`GND` 或 `CAM_AVDD_2V8`**（必须同网且与 25/26 绝缘） | `5.0 A` | **BLOCKED（需模组图纸与四线通断实测）** |

---

## 4. 摄像头接口保护电路与 PCB1 摆放建议

1. **电源滤波与噪声隔离**：
   - `CAM_AVDD_2V8`（模拟供电）在 J2 近端配置独立 `0.1 µF + 4.7 µF` 去耦电容并单点/低阻回流至模拟地，避免与数字电源 `CAM_DVDD_1V2`、`CAM_DOVDD_1V8` 共用细长回流路径。
2. **DVP 并行时钟与 EMI 抑制**：
   - `CAM_XCLK_1V8`（主时钟输出）与 `CAM_PCLK_1V8`（像素时钟输入）建议在源端串联 `22–33 Ω` 阻尼电阻，并与相邻 `GND`（`P7/P9/P11`）紧耦合包地走线，降低高频辐射对镜腿 RF/蓝牙的干扰。
3. **产线装配 ESD 防护**：
   - J2 为机内 FPC 接口，非用户外露触点，无需在 8 位高速数据线上堆叠高电容 TVS；仅建议对低速控制线（`CAM_SCCB_SCL/SDA`、`CAM_RESET_N`、`CAM_PWDN`）按需预留超小封装（0201）低电容 ESD 防护位。
4. **PCB1 摆放建议**：
   - **首选纵向摆放（本体 `1.70 × 6.80 mm`，长边沿 Y 轴）**：即使放在收窄段（`5.80 mm`）或前宽段（`8.20 mm`），宽向余量均达 `3.9–6.3 mm`，且便于顶层严格落位 `NO CONDUCTIVE TRACE` 禁布区与丝印 `Pin 1` / `FPC OUT →` 防反标识；
   - **横向摆放（本体 `6.80 × 1.70 mm`）仅适用于前宽段（`8.20 mm`，每侧仅余 `0.70 mm`）**，严禁横向置于 `5.80 mm` 尾段。
