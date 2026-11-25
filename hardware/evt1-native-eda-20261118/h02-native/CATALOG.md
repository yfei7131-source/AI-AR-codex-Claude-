# H02 目录字段与封装归一化

[catalog-plan.json](catalog-plan.json) 把 PR #32 的有效 BOM、原理图器件清单与 PR #33 的逐页原生回读按板和位号对账。PR #33 的回读来自各页最新可用记录，原生工程恢复和本轮装配验收仍需在当前副本复查。

| 范围 | 离线结果 |
| --- | --- |
| 板内原理图对象 | 253 个。49 个独立原厂标识，3 个已确定厂家及封装的型号，175 个无源件描述，14 个铜焊盘或探针对象，4 个外置对象，4 个订货号阻塞，4 个器件待选。 |
| 当前受控原厂标识及封装型号 | 52 个对象。历史原生值与当前受控值一致 41 个，需回读核对 11 个。 |
| PR #33 的 173 个历史字符串匹配 | 131 个是目录字段中的无源件值、成组描述、铜焊盘、候选和订货未决文本，涉及 35 种字面值。其历史字段核对沿用了“非空且无 TBD”的筛法。 |
| KiCad 封装 | 115 个铜焊盘编号集合对照重新运行通过。左板 52、桥板 49、右板 14 个。另有 138 个板内未分配与 1 个外部相机对象。本结果核对的原生 EasyEDA 封装关联数量为 0。 |

## 原生写入前的核对

1. 用当前工程 UUID、板、页、位号、器件唯一 ID 和明确的器件原厂资料查证每个待处理对象。历史 primitive ID 仅供定位。保留同名位号在不同板之间的隔离。
2. `RECONCILE_CONTROLLED_ID` 列出诊断后的目标字段。原厂型号（如 Nexperia 74LVC2G07GS）与订货包装编号保留各自含义。`CLEAR_LEGACY_DESCRIPTOR_IF_LIVE_MATCHES` 仅在当前原生 Manufacturer Part 仍精确等于计划给出的旧描述时适用。保留 Value、备注和设计规格。若原生字段的值已变更，先独立核对来由及当前品类。
3. 115 个 KiCad 封装的名称用于检索和焊盘编号核查。原生封装须有真实资源关联，保存重读后逐脚核对其物理铜焊盘、网络和方向。通用无源件封装的 pad 编号通过与原厂料号未定可以同时成立。维持双眼连接器及 AVDD 稳压器的 DNP，等待受控 JBD 引脚和封装资料。

## 阻断的目录条目

- `R_SENSE` 需要 2.20 Ω、0.1% 并满足 Kelvin 采样和温漂。继承的 `ERA-2AEB2R2X` 出现在成组值中。Panasonic ERA2AEB 的原厂订货范围为 47 Ω 至 100 kΩ，未支持该 token。保持设计阻值，确切采购器件留待确认。 [Panasonic ERA 系列目录](https://industrial.panasonic.com/cdbs/www-data/pdf/RDN0000/ast-ind-171281.pdf)
- `D_XREQ` 的继承文本为 ROHM RB521S-30 系列。ROHM 将具体订货项 RB521S-30TE61 列为 Last Time Buy。保留 A/K 设计关系和待选状态，替换器件须独立复核漏电、正向压降和实际 pad。 [ROHM 产品对照](https://www.rohm.com/products/diodes/schottky-barrier-diodes/standard/rb521s-30-product)
- `Q_CHG_MUTE_R` 的 2N7002 仍缺少选定厂家。Nexperia `PMV65XP` 和 `74LVC2G07GS` 作为原厂给出的具体封装型号可用于目录对账，包装后缀留作采购字段。 `Y2_BLE` 的 FA-128 候选需要受控订货号及负载、ESR 和频率公差。 [Nexperia PMV65XP 封装/订货](https://www.nexperia.com/chemical-content/PMV65XP.html) [Nexperia 74LVC2G07GS 封装/订货](https://www.nexperia.com/products/analog-logic-ics/logic/buffers-inverters-transceivers/buffers/serie/74lvc2g07/)

从 EVT-1 工程目录执行 `python h02-native/build_catalog_plan.py --check` 复查版本库计划。采集当前副本的 board-scoped pins 和 board_pages 后，可使用 `--capture <capture-directory> --output <new-plan.json>` 生成新计划。使用 `python tools/build_footprint_map.py --libraries <KiCad-footprints-directory> --check` 复验 KiCad 焊盘编号。
