# KIMI 工程交接 — Rev D1 / NOT FOR FAB

输入顺序：Rev D1 NETLIST → 每针 PINMAP → CONNECTOR_PINOUT_REV_D1 → TRANSLATOR_BANKS_REV_D1 → BOM + BOM_COMPONENT_INSTANCES → ICD Rev D1。`00_Rev_D1_Change_Record` 的三份原厂审查说明解释修正与保留阻断；不要沿用 Rev D 聚合引脚或旧验证状态。

原理图逐针导入并展开所有外围实例，不得把 RN_* 文字簇当成已连接电路；所有电源、地、去耦回路、晶振、RF、调试、EN、反馈、NTC、NC 都需要原生图元回读。保护电池接口为采购约束，尚非选定 PCM 的裸电芯设计。电气表不是可投板原理图。

6层2+2+2 HDI 候选沿用；M-MAIN-L 保留46mm，41.6mm仅为紧凑化候选，未计减重。新外围全部需原生摆放，按实际封装庭院与焊盘重跑冲突、ERC、DRC及供应商DFM。nRF晶振与RF匹配贴近芯片；电源开关回路最小；FB远离SW；去耦就近连接地；RF天线禁铜区与匹配参考几何必须复核。铰链动态区禁元件、过孔及补强端应力集中，回流地不得跨分割。

质量：当前分析估算 41.198g；前框/铰链≤9.55g、每腿壳≤1.80g、FPC/补强≤0.35g、紧固/胶/网布≤0.40g 的集成方案，含0.50g余量后估算 39.380g。该数是有条件设计预算；没有减少双目光机、电池或既有右PCBA/配重账，未虚构减重或称重。候选必须由带材料的装配CAD与实物质量闭环。

固件：更新 nRF PSEL 到逐针表，使用32MHz HFXO、按晶体CL配置电容、LFRC校准、原厂CMAA Config3电感供电配置（仅装配LC后启用VREGMAIN/VREGRADIO DC/DC）；校验该I2S外设对所选GPIO的限制。ESP32 CHIP_PU 10k/1µF，GPIO0提供下载夹具；启动时相机I/O隔离状态要实测。BQ25180 上电必须读取/配置/回读目标电流、4.2V、电源路径与watchdog；不能把复位默认当50mA配置。FPGA下载及CDONE后≥49个SCK、OPT_CTRL/RAW流程均保持Rev D。

验收：运行Python电气检查和重复生成检查；GitHub CI运行原FPGA真实仿真/综合/PnR/STA及D1电气检查。通过仅覆盖源文件结构、计算和FPGA工具，不能代表原生CAD、RF、充电、热、声学、AR光学或实物通过。剩余工作见 BLOCKED_ITEMS_CHECKLIST.csv。
