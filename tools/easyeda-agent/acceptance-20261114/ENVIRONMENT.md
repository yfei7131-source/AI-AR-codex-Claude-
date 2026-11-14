# 验收环境（2026-11-14，Windows）

| 组件 | 版本 | 证据 |
|---|---|---|
| easyeda-agent CLI | v1.17.0（`C:\Users\Admin（无密码）\.local\bin\easyeda.exe`，SHA256 `53b2b7bf2cec8c9606b209594e141cbc08e23cd777da4368bcee46d28eabc2e9`，与 GitHub API digest 一致） | `easyeda --version` |
| daemon | v1.17.0 @ 127.0.0.1:60832 | 01_health.json |
| EDA Agent Connector | 1.17.0（侧载 .eext，SHA256 `3c281f8176867baed4430c9d8bcbf7a5330c73654d4c852589d991e21b14c8ff`） | 01_health.json versionGate |
| 嘉立创EDA专业版 | 4.1.97（D:\lceda-pro，electron，满足 V4 主线基线 ≥4.0.0，推荐 ≥4.1.60） | 01_health.json hostCompatibility |
| Skill | 1.17.0（SKILL.md SHA256 `ae5f402bce6b08ebf3caa5c211c3d9e35cd515af7434d794e28bfb820a93af95`） | easyeda skill read |
| OS | Windows 10/11 x64，Git Bash + PowerShell 5.1 | install.ps1 要求 |

测试工程：`New Project_2026-11-14_14-30-17`（projectUuid `0fb3d3be968de9d900a1e973182026b4e3234bbb6604aacacee001af222755b0`）——独立新建工程，非 ZY AI/AR 智能眼镜正式 PCB，仅作 easyeda-agent 链路验收。受试电路：标准电路块 block.ams1117_ldo_3v3（U1 AMS1117-3.3 C6186 + C1 100nF C1525 + C2 10µF C440198 + C3 22µF C45783）。
