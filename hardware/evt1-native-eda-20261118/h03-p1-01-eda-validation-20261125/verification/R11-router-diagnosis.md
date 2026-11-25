# R11 历史自动布线与扇出复盘

- **线宽**。R11 三板原生默认 copperThickness1oz 的最小及默认线宽字段为 1.9685 mil。旧 PCB2 归档实际新增两条 AVDD_QUAL_CLR_N 走线，均为 1.96 mil。旧 PCB3 引擎中间结果的 143 段线同为 0.05 mm。上游 CLI 的自动布线接口依赖原生设计规则。隔离试验适合新建并绑定单网 4 mil 规则，审核原生实际铜宽、网和层。 [嘉立创 EDA 自动布线](https://prodocs.easyeda.com/en/pcb/route-auto-routing/) · [嘉立创 EDA 线宽规则](https://prodocs.easyeda.com/en/pcb/design-design-rule/)
- **进度**。R11 PCB3 作业连续 50 次呈报 running:0。取消后的引擎中间结果有进度 0.0017316、可布率 0.051948，候选含所请求范围外的 26 个网络，作业终态为 canceled。前台状态、引擎候选和落盘铜各有独立回执。v1.20.0 的 pcb autoroute 可跟踪原生作业，显示主机状态及引擎可布率，并按终态确认取消。实际接受仍须核对新增与删除对象、分网、层、宽度、过孔和 DRC。 [v1.20.0 发布记录](https://github.com/zhoushoujianwork/easyeda-agent/releases/tag/v1.20.0)
- **扇出**。旧三板分别对实际 BGA 运行 6 mil 走线与 6.2 mil 通道间隔的统一参数。球间铜缝约 7.85、7.85 和 6.08 mil，低于常规直穿所需的 18.4 mil。回执是 accepted:true 且无作业 ID，重新导出显示三板均无图元变化。几何数据能证明直穿通道不足，宿主没有提供逐球拒绝原因。新试验使用可控的外缘方向并记录原生图元及规则回读，HDI 工程路径使用既有孔跨、局部几何求解及 DRC。 [嘉立创 EDA 扇出](https://prodocs.easyeda.com/en/pcb/route-fanout-routing/)

原始回执见 PR #64 的 logs/fanout、logs/broad 和 logs/autoroute-PCB2。提取出的图元标识、规则、几何计算、统计和源归档指纹见 [R11-router-diagnosis.json](R11-router-diagnosis.json)。
