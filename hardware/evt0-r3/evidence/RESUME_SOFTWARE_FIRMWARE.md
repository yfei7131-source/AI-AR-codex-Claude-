# R3 恢复后的软件和固件复核

日期：2026-11-12（Asia/Shanghai）。保留恢复前的固件源码与构建证据；本次只新增测试输出、复核脚本及本报告。

| 检查 | 本次真实结果 | 证据 |
|---|---|---|
| `python -m unittest discover -s tests -v` | 102/102，退出码 0 | `resume-software-tests.txt` |
| `python firmware/tests/run_host.py --cc C:/codex-tools/glasses-host/ziglang/zig.exe` | 20 项核心 + 18 项媒体 + 9 项相机故障注入，合计 47/47，退出码 0 | `resume-firmware-host-tests.txt` |
| `python hardware/evt0-r3/tools/verify_firmware_evidence.py --output hardware/evt0-r3/evidence/resume-idf-revalidation.json` | 四个既有 ESP-IDF 5.4.3 构建的源文件集合和每件 SHA-256、现存 binary 字节数/SHA-256、日志完成标记均通过，退出码 0 | `resume-idf-revalidation.json` |

四个配置是 `unconfigured`、`eye-v22`、`evt0-r3`、`evt0-r3-ap`；各检查 27 件输入。二进制长度分别为 718480、727280、727280、1060288 B。该检查复核上一轮已完成的真实构建，**本轮没有重新编译 IDF，也没有烧录**。二进制仍位于构建清单中的本机 ASCII 工具目录，不纳入 Git。复核工具需要这些原始本地文件；换机后应按 `firmware/tools/build_idf.py` 重新构建，不能伪造相同二进制检查。

主机测试实际编译生产 C 源码，使用 `-std=c11 -Wall -Wextra -Werror -pedantic`。9 项相机测试使用 IDF API 桩和合成 JPEG，不是物理相机采集。软件测试使用本地合成输入及受控假服务，不验证真实云模型、iPhone、蓝牙无线或光学 HUD。

`camera_power.c` / `camera_adapter.c` 复核：全部板级 profile 的 `privacy_interlock_verified` 仍为 false；拒绝发生在相机初始化和上电之前。EVT-0 启动先尝试隔离 14 根 DVP/SCCB/XCLK 信号并保持 GPIO3 电源使能为低。将使能设高前须隔离成功；初始化失败、无帧、无效帧及正常结束均尝试停止相机并关断外部轨。已有测试覆盖未验证板、启动关轨、过期授权、无 PSRAM、有效帧、部分初始化失败、无帧、坏格式及隔离失败。

物理安全仍阻塞：GPIO/API 成功和 9 项注入测试不能证明真实电源已掉电、MOS 关断、LED 可见、开短路故障安全或信号线无反灌。当前相机 LED 单支路不提供灯开短故障自动断采集保证；T11/T12、复位绑带、供电时序、残压及撤销时的在途采集须台架测量。相机初始化/取帧仍是同步过程，不能宣称撤销会瞬时切断物理采集。未选传感器的 10 ms 上电等待仅是台架初值。相机、音频和显示未解锁，四份构建证据的 `hardware_verified=false`、`flashed=false` 保持不变。
