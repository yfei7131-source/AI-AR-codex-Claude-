# Claude 23:05 路由器恢复 — 使用边界

## 代码来源
- `r5_route_initial.py`：从原 Claude `create_file` 调用直接恢复的初版源码。
- `r5_route_restored_exact.py`：从 23:05 原始创建脚本应用两次 Claude 原始补丁后的**原样恢复源码**。
- `r5_route.py`：上述原样恢复版再由 ChatGPT 改了两处 NumPy 布尔量相减兼容错误（显式 `int(bool)`）；其余保持不变。
- `r5_run.py`：从 Claude 最后一次 `bash_tool` 的 heredoc **原样提取**。注：它的文档字符串提到输出 KiCad PCB，但实际程序仅执行内存布线并打印统计，**没有写磁盘**。

## 复现
在本包根目录：

```bash
PYTHONPATH=tools:tools/experimental_r5_2305 python tools/experimental_r5_2305/r5_run.py repo/hardware/evt0-r4-review/H02/evt0_core /CHG_PGOOD_N
```

本轮已执行：原样恢复版先出现 `numpy boolean subtract` 错误；改两处后，在 `/CHG_PGOOD_N` 上自定义连通性统计从 **58 降到 57**，生成 **9 个内存 segment、1 个 via**。该结果**不是 KiCad ERC/DRC**。

## PCB POC
- `experimental_R5_POC_NOT_FOR_FAB/evt0_core.kicad_pcb` 为 ChatGPT 独立生成的**实验性候选板**：将上述 10 个铜对象插入到 R4 原 PCB 的**副本**，R4 原件未改。
- 已复查生成板可被项目 `sx.py` 解析，并使用 `zy_pcb.Board` 重新加载得到 57 项自定义连接缺口；`TEST_RESULT_R5_POC.json` 保留来源/哈希与新增铜项目。
- **没有 KiCad 原生 ERC/DRC、制造性与实际信号完整性验证**；严禁作为正式 R5、Gerber 或生产放行文件。

### 下一轮工程师必须执行
1. 在装有 KiCad 的环境打开实验 PCB，检查 `/CHG_PGOOD_N` 的真实连接/走线/过孔与装配，运行真实 ERC/DRC。
2. 仅当通过审查，才把增量合入新的正式工程；其他未连接项目和12孔径错误/3库警告未处理。
3. 需要时先补完整可靠的写回、回滚、UUID/格式校验及原生验证流水线；不能据自定义检查宣称 DRC 通过。
