# [Draft PR] 智元跃动 AI/AR 智能眼镜 V1.0 首席架构师工程修正与 Kimi 工程交接包

- **Target Repository**: `https://github.com/yfei7131-source/AI-AR-codex-Claude-`
- **Base Branch**: `main` (严格不直接修改 `main`，零覆盖 Kimi `hardware/evt0-r9-pcb-20261115` 及 `hardware/evt0-r8-jlceda-20261114`)
- **Head Branch**: `handoff/evt1-v1-arch-kimi-handoff-20261115`
- **PR Status**: **Draft PR** (`DESIGN_RULES_VERIFIED__HARDWARE_RELEASE_BLOCKED_BY_6_EXTERNAL_ITEMS`)

## 1. 本次提交包含的工程交付物 (`hardware/evt1-v1-kimi-handoff/`)

| 文件路径 | 说明 | 验证状态 |
| :--- | :--- | :--- |
| `hardware/evt1-v1-kimi-handoff/KIMI_ENGINEERING_HANDOFF_V1_0.md` | 首席硬件架构师工程修正与 Kimi 交接总册（含框图、电源树、HDI 规则、电路计算） | `VERIFIED_DOC` |
| `hardware/evt1-v1-kimi-handoff/PINMAP_V1_0_FROZEN.csv` | 31 路冻结引脚表（修复 `ESP32-S3-PICO-1` LGA56 内部 Octal PSRAM 引脚冲突与 `iCE40UP5K-UWG30` 电平转换） | `VERIFIED_DATASHEET` |
| `hardware/evt1-v1-kimi-handoff/BOM_V1_0_FROZEN.csv` | 冻结关键器件 BOM（含精确封装尺寸、功耗、质量及官方数据手册 URL） | `VERIFIED_DATASHEET` |
| `hardware/evt1-v1-kimi-handoff/SOC_ARCHITECTURE_COMPARISON.csv` | 高通 AR1、恒玄 BES2800BP、乐鑫 ESP32-S3-PICO-1 / P4、炬芯 ATS3085S 架构对比表 | `VERIFIED_DATASHEET` |
| `hardware/evt1-v1-kimi-handoff/ICD_INTERFACE_CONTROL_TABLE.csv` | 跨板接口控制表（QSPI、双目光学、DVP+隐私互锁、跨框 USB/电源/UART、PDM 麦克风、双电池） | `VERIFIED_DESIGN_CALC` |
| `hardware/evt1-v1-kimi-handoff/SYSTEM_BUDGETS_V1_0.json` | 38.85g 质量与重心模型、1:1 HDI PCB 空间预算、全工况功耗与热保护预算 | `VERIFIED_CALC` |
| `hardware/evt1-v1-kimi-handoff/BLOCKED_ITEMS_CHECKLIST.csv` | 6 项未获供应商 STEP/NDA/实测数据的诚实阻断清单（`BLK-01` ~ `BLK-06`） | `STRICT_BLOCKED_TRACKING` |
| `hardware/evt1-v1-kimi-handoff/verify_v1_0_engineering.py` | 零虚假 PASS 自动化工程校验脚本（含正向数据手册核查 + 3 项反向故障注入自检） | `PASS_SELF_TEST` |
| `hardware/evt1-v1-kimi-handoff/evidence/v1_0_verification_report.txt` | 真实脚本执行日志与阻断项输出 | `REAL_EXECUTION_LOG` |

## 2. 一键推送至 GitHub 独立分支并创建 Draft PR 指令

由于当前沙箱容器禁用了外网访问（No Outbound Internet Access in VM Sandbox），本地已完成完整的 Git 独立分支 `handoff/evt1-v1-arch-kimi-handoff-20261115` 提交、Git Bundle 打包 (`evt1-v1-arch-kimi-handoff-20261115.bundle`) 及 Patch 导出。在联网开发机上只需运行以下 3 条命令即可直接推送到远端仓库并创建 Draft PR：

```bash
# 1. 在本地克隆的 AI-AR-codex-Claude- 仓库中导入本分支 bundle
git fetch evt1-v1-arch-kimi-handoff-20261115.bundle handoff/evt1-v1-arch-kimi-handoff-20261115:handoff/evt1-v1-arch-kimi-handoff-20261115

# 2. 推送独立分支至 GitHub 远端（不触碰 main 与 Kimi R9）
git push -u origin handoff/evt1-v1-arch-kimi-handoff-20261115

# 3. 使用 GitHub CLI 创建 Draft PR
gh pr create --draft \
  --base main \
  --head handoff/evt1-v1-arch-kimi-handoff-20261115 \
  --title "[Draft] EVT-1 V1.0 Architecture & Kimi Handoff Package (PICO-1 Pin Fix, Dual-Cell Charger, Privacy Window Interlock, 6L HDI Rules)" \
  --body-file hardware/evt1-v1-kimi-handoff/KIMI_ENGINEERING_HANDOFF_V1_0.md
```
