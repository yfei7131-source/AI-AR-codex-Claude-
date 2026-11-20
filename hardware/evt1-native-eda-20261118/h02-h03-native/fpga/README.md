# EVT-1 FPGA 回归与 CI

以 PR #35 的 `ccc535842fca777bf1b84611556983db03af40d7` 为测试输入。仓库逐项比较确认 `03_FPGA_RTL` 和主机数据包源与 PR #32 相同。用 Icarus Verilog 13.0 在 Windows 上编译并执行现有测试台。原始输出用 `<SCRATCH>` 代替机器路径。[执行清单及源文件摘要](local-regressions.json) · [Icarus 版本输出](icarus-version.log.txt) · [MSYS2 原版工具包](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-iverilog)

| 回归 | 实际结果 |
| --- | --- |
| 双眼显示和 RAW | 38,400/38,400 帧字正确，零丢失、溢出或撕裂，800,000 时钟计数对应 60.000 Hz。[日志](display-raw.log.txt) |
| AVDD 关断逻辑 | 11 个用户态 RTL 用例通过，涵盖停钟、心跳锁存、OFF 禁用扫描/RAW 和避免误重启。Rev D1 对照测试复现已知 D3 停钟高电平缺陷。[日志](shutdown-safety.log.txt) |
| 帧格式、残包恢复 | 8 个定向组通过。PR #25 对照测试复现旧版保留位解析问题。[日志](host-framing.log.txt) |
| 主机编码对 RTL | 3 个像素字、两眼 RAW、一次性窗口关闭和编码 OFF 通过。[日志](host-wire.log.txt) |
| 模拟安全模型 | 条件式 RC 及事件断言通过。本机两种 ngspice 构建分别因临时文件和动态库问题停在启动阶段。硬件、监督器 PVT 和光机 AVDD 实测仍为 BLOCKED。[模型日志](avdd-models.log.txt) · [原生 ngspice 回执](ngspice-local-blocker.log.txt) |

在支持 Icarus、Yosys、nextpnr 与 icetime 的环境中，从仓库根目录运行 `python hardware/evt1-native-eda-20261118/host/check_bridge.py` 与 `make -C hardware/evt1-rev-d1-1-20261117/03_FPGA_RTL all`。基准缺陷见证需要完整 Git 历史。条件式 AVDD 模型使用 Rev D1.1 的 `05_Verification_Scripts/test_rev_d1_1_avdd_safety.py`。

原验证工作流已增加当前独立实现分支的推送触发，保留现有工具、输入与 48 MHz 门槛。PR #32 的可核查归档记录 `seed=0` 最终布线为系统时钟 52.21 MHz、主机数据时钟 54.79 MHz、主机片选时钟 232.23 MHz，独立 icetime 为 49.65 MHz。其提交身份与时间证据分别保留。当前分支的 Linux 综合、布局布线与 STA 以本分支工作流为准。[祖先 CI 原始路由摘要](pr32-route-search.json) · [PR #32 Actions](https://github.com/yfei7131-source/AI-AR-codex-Claude-/actions/runs/44526978167)

本轮检索时 PR #35 为最新，公开远端无 Neon 开发分支。最近的 Gemini R1.3 远端提交仅增加研究资料来源清单，无 RTL、PCF 或可实施的光机接口变更。本轮没有从 Gemini 分支合并设计。[Gemini 审查提交](https://github.com/yfei7131-source/AI-AR-codex-Claude-/commit/74ada7424bf3bd851a667c6d8f0dac3431ab724c)
