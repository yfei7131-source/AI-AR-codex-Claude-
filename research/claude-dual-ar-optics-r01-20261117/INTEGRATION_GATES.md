# 研究结果集成门禁（供 Gemini / KIMI / Codex）

1. **架构一致性**：读取 Rev D1 的 `BOM_COMPONENT_INSTANCES_REV_D1.csv`、`NETLIST_ELECTRICAL_CONNECTION_REV_D1.csv`、`ICD_FPGA_HOST_OPTICS_SPEC_REV_D1.md`、FPGA RTL/PCF 后复核研究假设 H-01~H-08；现有 ESP32-S3 无双 DSI，删除 FPGA 的 ECR-01 暂不接受。
2. **原厂验证**：向 JBD 确认选定准确料号、FPC/连接器、QVGA/VGA 模式、QSPI 初始化、AVDD 电压、时序、3D STEP、功耗/亮度曲线及模块重量。未经确认不得直接接电投板。
3. **光学/结构**：从真实波导厂取得外形/质量/耦入位置与装配基准，用完整 CAD 验证 40g、FPC 过铰链、眼盒、视轴公差。报告中 37g 仅为独立模型，不作为闭环依据。
4. **软件/验证**：可优先实现不依赖 NDA 的双目十字线/网格测试图、双眼校准算法与误差统计；供应商协议部分维持 `TODO(NDA)`。
5. **实现变更**：只经独立 ECR 审核批准后，由负责工程实施的 Codex/KIMI 修改 Rev D1 后继分支；原生 ERC/DRC、FPGA CI 和物理点亮各自提供独立证据。

所有方案状态：**research-only / unverified / NOT FOR FAB**。
