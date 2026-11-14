# 来源记录

## 输入文件

| 项目 | 值 |
| --- | --- |
| 原始 ZIP | `gemini-export-请连接并检查我的AI_AR智能眼镜研发GitHub仓库：_https___github.com_yfei7131-source_AI-AR-codex-Claude-_本轮仅做GitHub连接验证，禁_2026-11-14 18_57_42.zip` |
| ZIP SHA-256 | `9d1f2e8ce6158d5e63dd7e9595f7d2ab12ec6381264e85cdccc6aaf2a10b92a3` |
| ZIP 字节数 | 26,964 |
| 导出正文 | `gemini-export-请连接并检查我的AI_AR智能眼镜研发GitHub仓库：_https___github.com_yfei7131-source_AI-AR-codex-Claude-_本轮仅做GitHub连接验证，禁_2026-11-14 18_57_42.md` |
| 导出正文 SHA-256 | `658531733007d7685a3b323f0b6514f69948c44fa7a679b8ae67a3cfed0b700c` |
| 导出正文字节数 | 68,939 |
| 提取时间 | 2026-11-14 |

ZIP CRC 检查通过，仅包含一份 Markdown 导出正文，无附件、测量数据、供应商 PDF、CAD、原理图或测试报告。

## 仓库基线

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/yfei7131-source/AI-AR-codex-Claude-` |
| 研究分支 | `research/evt1-dual-ar-40g-20261114` |
| 分支基线 | `main` @ `e4e85b0a794e599f413b4987534e7999942e5373` |
| R8 现状 | PR #11 为 Draft；源分支 `hardware/evt0-r8-jlceda-20261114`，头提交 `1c62315b3f6d1f7f67198cd6675c008930820afd` |
| 本次写入范围 | 仅新增 `hardware/evt1-id/research/2026-11-14-dual-ar-40g/` |

R8 分支和 PR #11 仅用于确认隔离边界，本次没有检出、修改或合并 R8 任何文件。

## 来源性质与可信边界

1. 输入是 Gemini 对话导出，不是供应商文件、工程数据包或测试报告。
2. 导出正文引用了 JBD、NOP、Lattice、Espressif、TI、Qualcomm、TDK、Infineon 等页面 URL，但导出包没有附带页面快照或受控规格书。
3. 本轮只做同步与文档编排，没有重新联系供应商、没有获取报价、没有执行光学/热/射频/电池/结构测试。
4. 因此，BOM 中的型号、尺寸、重量、功耗、光学参数、成本与封装全部标记为 `UNVERIFIED`；需要设计、打样或环境验证的项目标记为 `BLOCKED`。
5. 导出正文中关于 R7 的 `e6a8363d2e6c3b1a462136cabc3f750f5dfb09d7`、49 项未连接和原生检查 `NOT RUN` 仅作为被审查的历史陈述保留，不作为本轮新增验证结论。
6. 本次没有修改 `hardware/evt0-r6-h02h03/`、`hardware/evt0-r7-usb-20261114`、R8 工程或任何 KiCad 文件。

## 从导出正文采纳的研究输入

- 40.0 g 整机挑战目标，39.5 g 工程分配目标，0.5 g 名义余量。
- 左镜腿主控、鼻梁光学/相机中枢、右镜腿音频/IMU、左右后段双电池的分区思想。
- JBD Mini II 单绿双目 + 超薄衍射波导 + Lattice FPGA 显示桥的候选路线。
- 独立双模蓝牙音频 SoC、IMU、触控、相机隐私互锁、USB-C 尾端入口的缺口清单。
- 光学、结构、电源、热、RF、固件、合规和 DFM 的验证门禁框架。

## 本轮修正

详细修正见 `CORRECTIONS_AND_RISKS.md`。其中以下错误已明确纠正：

- 1.1 Mbit 片内存储与 1.2288 Mbit 单帧容量的矛盾；
- 40 MHz 4-bit QSPI 对双目 60 Hz 带宽余量的错误估计；
- 0.1° 与 3 arcmin 的换算错误；
- 单颗 BQ24072 + LM66200 双电芯充电的拓扑错误；
- AZ91D 被误称为镁锂合金；
- ESP32-S3R8 被误称为裸片；
- 43°C 被误写成 IEC 62368-1 的通用皮肤限值。

## 供应商与外部链接（转录自导出正文，未在本轮独立复核）

- JBD Hummingbird Mini II: https://www.jb-display.com/product_des/5.html
- JBD 0.13 inch panel: https://www.jb-display.com/product_des/3.html
- JBD full-color variant: https://www.jb-display.com/product_des/12.html
- NOP waveguide reference: https://en.nophotonics.com/index.php?m=content&c=index&a=show&catid=60&id=127
- Lattice iCE40 UltraPlus: https://www.latticesemi.com/en/products/fpgaandcpld/ice40ultraplus
- Espressif ESP32-S3 datasheet: https://documentation.espressif.com/esp32-s3_datasheet_en.pdf
- TI BQ24072 family: https://www.ti.com/lit/ds/symlink/bq24074.pdf
- TI TPS63020: https://www.ti.com/product/TPS63020
- TDK ICM-42688-P: https://www.invensense.tdk.com/products/motion-tracking/6-axis/icm-42688-p/
- Infineon IM69D130: https://www.infineon.com/part/IM69D130

上述链接存在不等于参数已核实。任何采购、认证或设计冻结前必须取得现行受控文档和样品证据。
