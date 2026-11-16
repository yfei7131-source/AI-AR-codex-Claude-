# [Draft PR #19] 智元跃动 AI/AR 智能眼镜 V1.0 (EVT-1 Rev C) — Codex GitHub 同步与 CI 执行指南

- **目标仓库**：`https://github.com/yfei7131-source/AI-AR-codex-Claude-`
- **目标 PR**：[Draft PR #19](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/19)
- **独立分支**：`handoff/evt1-rev-c-feasibility-20261115`（严格基于 `d15cc6f` 演进，严禁覆盖 `main`、`PR #16`、`PR #17`、`PR #18`）
- **协作分工**：**Codex** 负责执行本指南将 Git bundle 同步至远端并运行 GitHub Actions CI；**KIMI** 负责依据 `hardware/evt1-v1-kimi-handoff/` 下的冻结设计表在嘉立创 EDA 中完成原理图与 6 层 HDI PCB。

---

## 1. 本次提交核心交付物清单 (`hardware/evt1-v1-kimi-handoff/`)

| 文件路径 | 用途与面向对象 | 当前状态 |
| :--- | :--- | :--- |
| `rtl/evt1_ar_display_fpga_bridge_rev_c.v` | 48MHz 关键路径深度流水线优化版 FPGA RTL（256字 `3x SB_RAM40_4K` FIFO + `4x SB_SPRAM256KA` + `2x SB_RAM40_4K` 行缓存 + `tear_row_holdoff` 防撕裂） | 1ps 事件驱动仿真 PASS；待 CI 原生综合/STA |
| `rtl/tb_evt1_ar_display_fpga_bridge_rev_c.v` | 修复 `row=0, addr=0x0000` (`0xA53C==0xA53C`) 碰撞并加入 `1.0ns` 相位保护与 `Row 10->11` 活跃行防撕裂自检测试台 | 38,400 对像素 `mismatches=0` |
| `rtl/ice40_spram_ebr_sim.v` & `rtl/ice40up5k_uwg30_rev_c.pcf` & `rtl/Makefile` | Lattice 原语行为模型、18-PIO UWG30 约束文件与带 `pipefail` 校验的 Makefile | 已验证语法与引脚合法性 |
| `.github/workflows/fpga_eda_ci.yml` | Codex / GitHub Actions 自动运行 `iverilog`、`vvp`、`yosys`、`nextpnr-ice40`、`icetime` 与 `verify_v1_0_engineering.py` 的工作流 | 已配置完成 |
| `ICD_FPGA_HOST_OPTICS_SPEC_REV_C.md` & `ICD_INTERFACE_CONTROL_TABLE.csv` | 主控 $\leftrightarrow$ FPGA $\leftrightarrow$ 双目光机完整接口控制定义及 JBD 4 项阻断 (`BLK-JBD-01..04`) 规范 | 已冻结可编辑版 |
| `CHANGELOG_EVT1_REV_C.md` | 从 `6eaebe0` 至最新提交的完整工程变更记录 | 已生成 |
| `BOM_V1_0_FROZEN.csv` & `PINMAP_V1_0_FROZEN.csv` & `BLOCKED_ITEMS_CHECKLIST.csv` | KIMI 嘉立创 EDA 44 位号 BOM、逐针映射表（含 `J_DISP_L/R` 1..10 脚）与诚实阻断清单 | 已冻结 |

---

## 2. Codex 一键同步至 GitHub PR #19 并触发真实 CI 命令

```bash
# 1. 从本工程包中的 handoff_evt1_rev_c.bundle 拉取完整提交历史至本地分支
git fetch ./handoff_evt1_rev_c.bundle handoff/evt1-rev-c-feasibility-20261115:handoff/evt1-rev-c-feasibility-20261115

# 2. 推送至 GitHub origin 更新 Draft PR #19（不触碰 main 与其他分支）
git push origin handoff/evt1-rev-c-feasibility-20261115

# 3. 观察并下载 GitHub Actions 原生 EDA CI 运行日志
gh run watch
```
