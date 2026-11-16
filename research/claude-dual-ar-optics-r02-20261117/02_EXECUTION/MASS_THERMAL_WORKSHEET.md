# 质量/功耗/热预算 — 需重建的模板
## 为什么重建
R0.1 报 37g、Rev D 报 41.0g、Rev D1 报 41.2g，存在版本/计量边界差异。三者不是同一张可直接比较的完整实测账本。按当前 Rev D1 实际BOM+结构档建 `component_id, quantity, nominal_g, min_g, max_g, source, proof` 列，不可默认新增项质量为0。

## 强制整机项目
双波导/镜片、双光机及散热箔、左右镜框/镜腿壳、鼻梁副框、铰链/螺丝、鼻托、左右电芯和保护、主副板、所有 FPC/连接器/排线、处理器/FPGA/射频器件、摄像头、麦克风/扬声器、胶/灌封/镀层、充电触点、装配预留。

## 强制输出
- `MASS_BUDGET_RECONCILED.csv`：按件明细与质量范围；公式 `assembled_g = Σ(quantity × measured_part_g) + glue + assembly_delta`，质量可来自样品称重/3D CAD/暂估，需逐条标记。
- `MASS_MARGIN.md`：相对40.0g与建议39.5g内控目标的差值；区分项目目标和 EVT 41–43g阶段性基线。
- `POWER_BUDGET_MODE.csv`：sleep/standby/HUD高亮/camera+audio峰值，列每路电压、电流、效率、持续/脉冲、测量来源。
- `THERMAL_SCENARIOS.csv`：环境温度、视场、APL、接触位置、时长、平均/峰值功耗、接触表温，注明是否为 FEA/热阻模型或真实试验。

## 报告中只有理论估计的量级
- S2 `266mW ×24.5°C/W ≈6.5°C`；S3 `845mW ×24.5°C/W ≈20.7°C` 温升。这假设一个等效热阻，未证明实际接触温度。
- Mini II 官网典型功耗约60mW/只，与二手初版手册高亮工况最大550mW/只不可直接互相替代。必须量测亮度/APL-功耗曲线。
- 将整机结构改为0.45mm PA12 仅为高风险提案，未取得可注塑性证据；前期用0.6mm做保守核算并寻求厂商 DFM。
