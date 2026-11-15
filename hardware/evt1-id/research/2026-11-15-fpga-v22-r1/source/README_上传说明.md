# Gemini FPGA V2.2-r1 — GitHub同步交接包

目标仓库：https://github.com/yfei7131-source/AI-AR-codex-Claude-

**状态：本交接包已在本地准备，但尚未推送到GitHub。** 当前ChatGPT GitHub连接器尝试创建分支时返回403 Resource not accessible by integration；容器内Git网络也不能解析github.com。

## 已核实原始文件

- 来源：`gemini新输出.zip`
- source version：`V2.2-r1`
- 原始Git bundle HEAD：`77befa01d597d515d23368b5c89d4084e567ed73`
- 原始Git bundle parent：`14d0a4ba58543d054f00af02cb872453c3e2accd`
- 原始Manifest中27个文件的体积与SHA256均逐项匹配；ZIP无CRC错误。
- 本交接包包含原样源代码、Manifest、证据、constraints及原始bundle。未把来源声明的RTL native PASS冒充已通过。

## Windows用户操作

1. 解压本ZIP到本地文件夹；确认命令行Git可以访问GitHub且有写入权限；可用`gh auth status`检查登录。
2. 双击`双击运行_同步GitHub.cmd`，或PowerShell运行`./同步到GitHub.ps1`。
3. 脚本将从V2.1分支 `handoff/evt1-fpga-v21-20261114`（`65a9c32e`）新建 `handoff/evt1-fpga-v22-r1-20261115`，新增此V2.2-r1工程，推送并尝试通过gh创建Draft PR。
4. 若连接不上GitHub或无权限，脚本安全失败；**不会自动覆盖原分支，也不合并main**。

## 上传目录

`hardware/evt1-id/research/2026-11-15-fpga-v22-r1/evt1_ar_display_fpga_bridge_v2_2/`

## 注意

V2.2-r1原bundle是两提交的独立历史，不能直接强推覆盖已有分支。上传到V2.1基础上的归档提交SHA会不同于原始`77befa01`；原始提交会保留在`dist/evt1-ar-display-fpga-bridge-v2_2.bundle`中。

已知阻断：原生Icarus/Yosys/nextpnr/STA仍未获得有效结果；Makefile中的管道退出码问题，40g布局冲突及JBD NDA ICD/FPC未解决。`NOT FOR FAB`。
