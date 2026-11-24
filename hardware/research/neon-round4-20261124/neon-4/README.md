# 智元跃动 AI/AR 智能眼镜 V1.0（EVT-1 H03-R8）PCB1 接口设计与空间冲突解决交付包

- **继承基线**：
  - [PR #55（R7 原生基线，NOT FOR FAB）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/55)
  - [PR #57（Neon Round2 / `neon-4` 接口与 ERC 规划）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/57)
  - [PR #58（R8 Codex 原生布线与验证，STATE.md 确认 PCB1 尾段实宽约 5.8 mm）](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/58)
- **交付范围**：纯本地 ZIP 交付（**不上传 GitHub**；停止重复尝试受管理员策略限制的云端 `.epro2` 导入）。
- **门禁声明**：继续保持 **`NOT FOR FAB`**；凡缺少相机模组原厂 FPC 图纸、3D 壳体净空或实物通断/磁极证据的项目均维持 **`BLOCKED`**，严禁猜测极性或虚构料号。

## 文件目录清单

| 文件名 | 内容说明 |
| :--- | :--- |
| `README.md` | 本总览文件、继承关系与核心决策摘要 |
| `J3_5P8MM_CONFLICT_RESOLUTION.md` | 解决 J3 候选 `6.86 mm` 本体与 PCB1 尾段 `5.8 mm` 实宽冲突的可装配替代器件与布局方案、封装尺寸及保护电路设计 |
| `J2_CAMERA_FPC_AND_PROCUREMENT_AUDIT.md` | J2 摄像头 FPC 连接器 28↔26 逐针映射、配对插头、原厂焊盘规范、多渠道（DigiKey/JLCPCB）实际采购条件与保护/摆放建议 |
| `BLOCKED_AND_VERIFICATION_GATE.md` | 外部缺失资料 `BLOCKED` 清单（`PV-01 ~ PV-06`）与实物验证放行门禁 |
| `VERIFIED_PARTS_BOM.csv` | 全部经远程浏览器核验的真实器件 MPN、供应商料号、外形尺寸、库存、单价与原始验证 URL |

## 核心工程结论摘要

1. **J3 `6.86 mm` vs `5.8 mm` 空间冲突已定位根因并给出两套可立即落地的可装配方案**：
   - 核验证实所有通用一体化 4P 磁吸座因内嵌磁铁与壳壁，宽度普遍 `≥ 5.8–7.7 mm`（`C6276862` 宽 `7.70 mm`、`C41361286` 宽 `6.86 mm`、甚至 `ATTEND 303C-321018-30-04` 亦达 `5.80 ± 0.25 mm` 零余量且超差），无法无损装入 `5.8 mm` 尾段。
   - **方案 1（首选 — 板载超窄 SMD 4P 靶板 + 镜腿壳体独立 N52 磁铁）**：PCB1 尾段采用 **[Mill-Max `856-10-004-30-051000`](https://www.digikey.com/en/products/detail/mill-max-manufacturing-corp/856-10-004-30-051000/2349903)**（SMD，宽仅 **`2.21 mm`** × 长 `5.46 mm` × 高 `2.46 mm`，每侧板边余量达 **`1.795 mm`**，DigiKey 现货 `49` 颗），配对充电线端 **[Mill-Max `854-22-004-30-001101`](https://www.digikey.com/en/products/detail/mill-max-manufacturing-corp/854-22-004-30-001101/2349873)**（`2 A` 连续 / `3 A` 峰值，宽 `2.21 mm`），磁铁移至外壳纵向两端实现左 N 右 S 防反插。
   - **方案 2（备选 — FPC 尾线引出 + 独立磁吸充电小板）**：在 PCB1 `5.8 mm` 尾段仅保留 4 焊盘/超窄 FPC 出口（宽 `<4.0 mm`），将已核验现货的 **[SAMZO `PR5L2820-4P-C-F`（C41361286）](https://jlcpcb.com/partdetail/SAMZO-PR5L2820_4P_CF/C41361286)** 移至镜腿壳体宽腔体内的 2 层独立小板，免改 6 层 PCB1 板框。
2. **J2 配对插头采购瓶颈已解除，极性与 FPC 针序维持 `BLOCKED`**：
   - 虽然配对插头 `BM28B0.6-24DP/2-0.35V(53)` 在嘉立创 `C3653707` 为 0 库存预购，但 **[DigiKey `H125591CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DP-2-0-35V-53/7793554)** 现有 **`2,862` 颗现货**（Active，MOQ 1，`$1.65`），主板插座 **[DigiKey `H125603CT-ND`](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/BM28B0-6-24DS-2-0-35V-53/7793566)** 现有 **`4,544` 颗现货**（Active，MOQ 1，`$1.67`）且 JLCPCB `C5577343` 有 `153` 颗现货。
   - 因 `BM28B0.6-24DS/2-0.35V(53)` 100% 中心对称无防呆键且缺模组原厂 FPC 图纸，端部电源 `[25, 26]` vs `[27, 28]` 极性与 `1–24` 针序维持 **`BLOCKED`**。
