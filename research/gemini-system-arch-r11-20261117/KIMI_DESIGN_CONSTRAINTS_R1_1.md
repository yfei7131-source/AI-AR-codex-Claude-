# 智元跃动 AI/AR 智能眼镜 V1.0 — KIMI 嘉立创 EDA 专业版 R1.1 设计约束（状态更新版）

**文档编号**：`ZY-AIAR-KIMI-CONSTRAINTS-R1.1-20261116`  
**重要状态声明**：
- **暂停依据 R1 旧表画板**：因 `BQ24074`、`TPS63802`、`24-Pin BTB` 及 `34.75 g` 预算已在 R1.1 中被正式撤销 `FROZEN` 标识（待合并 Codex `Rev D1` PR #21 与 Claude 光学 `R0.1` PR #22 源文件），**KIMI 在未完成 PR #21 / PR #22 三方 BOM/NETLIST 对账前，严禁按旧 Rev C 器件投板或回退设计！**

---

## 1. 本轮已确认保留的硬性制造与电气约束
1. **6 层 2+2+2 Type-III Stacked-VIPPO HDI 工艺底线（严禁降级）**：
   - 最小线宽/线距 **`50 μm / 50 μm` (`2 mil / 2 mil`)**，激光微盲孔 **`75 μm / 180 μm`** 铜浆塞孔电镀盖帽 VIPPO（确保 `0.35 mm` pitch `nRF5340-CMAA` 与 `0.40 mm` pitch `iCE40UP5K-UWG30` 内排焊球逃线）。
   - `U1_HOST (ESP32-S3-PICO-1)` 底部中央 `4×4 mm` 散热焊盘 (`Pin 57`) 背面严禁摆件，专留阵列散热 VIPPO。
2. **主控与 FPGA 公开规范防呆（已验证保留）**：
   - `ESP32-S3-PICO-1` `Pin 46 (VDD3P3_CPU)` 及 14 个禁用引脚（`28, 30..35, 38..42, 53..54`）严禁引出；`Ball F1 (SPI_SO)` 经 `U8_LS1 Bank 1 (DIR1 = QSPI_DIR1_EN)` 隔离；`Ball C1 (SPI_SS_B)` 接 `10 kΩ` 下拉；`Ball B2 (VCCPLL)` 接 `100 Ω + 4.7 μF + 100 nF`。
3. **光机 `AVDD` 五状态联锁与 `Rev D1` `D3` 极性约束**：
   - **严禁将 `Rev D1` `D3` 低脉冲逻辑直接接入 `94b50cf` 的 `D1` 正向峰值保持电路！** 必须等待 PR #21 核对后，决定统一采用 `94b50cf` 正脉冲或改用 `C_AC = 10 nF` 交流耦合负边沿电荷泵，并满足全部 6 项安全测试要求。
4. **JBD 原厂 NDA 阻断与 3D STEP 门禁**：
   - `BLK-JBD-01 ~ BLK-JBD-04`（光机 FPC 线序、初始化 LUT、QSPI 命令字、`AVDD` 电压及 `JBD013VGA_STEP.stp`）继续保持 **`BLOCKED`**，禁止虚构参数或提前投板光机转接 FPC。
