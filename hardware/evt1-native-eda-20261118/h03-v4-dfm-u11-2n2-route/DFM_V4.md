# V4 盲孔几何对账

**NOT FOR FAB。** PR #46 的 141 个盲孔与本轮归档的 141 个盲孔分别逐孔复查。审计先按图元 ID、坐标、铜环及孔径、网络匹配编辑器铜回读与 EPRO2，再从各板原生规则表解析跨层范围。正反两面单阶盲孔的铜层不相交。同一铜层仍须检查不同跨层组合，例如盲孔对通孔。 [PR #46](https://github.com/yfei7131-source/AI-AR-codex-Claude-/pull/46) · [原生审计脚本](independent_hdi_dfm_auditor_v4.py)

## 测量基准

| 项目 | 测量方式 | 门槛 |
| --- | --- | --- |
| 激光孔壁至板边 | 孔中心至真实铣边最近距离 − 孔半径 | JLCPCB FAQ 图 D ≥ 0.350 mm |
| 钻孔之间的孔壁间隙 | 中心距 − 两孔半径之和 | 图 F 同网 ≥ 0.130 mm，异网 ≥ 0.240 mm |
| 孔对等效中心距 | 两孔半径之和 + 图 F 对应的孔壁间隙门槛 | 随孔径变化，例 Ø0.100／Ø0.150 mm 异网 ≥ 0.365 mm |
| 铜环外缘至板边 | 中心至真实铣边最近距离 − 铜环外半径 | 本轮沿用更保守的 0.350 mm 铜边布置值 |
| 两个孔铜环之间 | 中心距 − 两个铜环外半径之和 | EVT-1 6 mil 间隙检查，沿用继承规则的适用域 |
| 激光孔径和环宽 | 名义孔径；(铜环外径 − 孔径) ÷ 2 | 孔径 0.075–0.150 mm，制造能力表环宽 3 mil |

JLCPCB 工艺图的 D 尺标止于孔口边，F 尺标在孔壁之间，示意包括共用一层的错位盲孔。V4 对这类共层组合使用名义钻孔直径构成保守投影，对共轴同网叠孔单列工程审查。孔型锥度、分阶压合、叠孔接合、钻孔偏移与加工公差使用供应商工程评审确认。 [JLCPCB HDI FAQ](https://jlcpcb.com/help/article/hdi-pcb-capabilities-faq) · [工艺图](https://rs.jlcpcb.com/static/image/blog/pcb/jlcpcb-hdi-manufacturing-process.png) · [HDI 参数及环宽表](https://jlcpcb.com/pcb-fabrication/hdi-pcb)

## 逐板结果

| 工程 | PCB | 盲孔 | 最小孔壁至板边（mm） | 最小铜环外缘至板边（mm） | JLC 盲孔已测几何告警 | 项目 0.350 mm 铜边告警 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PR #46 | PCB1 | 62 | 0.393700 | 0.3175 | 0 | 4 |
| PR #46 | PCB2 | 40 | 0.453959 | 0.3778 | 0 | 0 |
| PR #46 | PCB3 | 39 | 0.419466 | 0.3433 | 0 | 2 |
| 本轮归档 | PCB1 | 61 | 0.442633 | 0.3664 | 0 | 0 |
| 本轮归档 | PCB2 | 40 | 0.453959 | 0.3778 | 0 | 0 |
| 本轮归档 | PCB3 | 40 | 0.444866 | 0.3687 | 0 | 0 |

同网、异网盲孔对的最小实测值、图元号、共用层、中心距及相应最小中心距在各板 `closest_blind_pairs` 中。两份报告的所有相关孔对间隙、铜环宽度和实际单阶跨层均符合本次筛查。PR #46 的六项告警来自额外的铜边布置值。本轮归档的对应告警为零。保留已归档的原始整改回执，其中已有的“JLC 铜边”措辞以本报告测量定义为准。 [PR #46 逐孔报告](evidence/baseline-pr46-v4-audit/independent-dfm-v4-summary.json) · [本轮逐孔报告](evidence/post-dfm-v4-audit/independent-dfm-v4-summary.json)

已用独立重导入的三板原生回读复跑。除原始文件摘要外，V4 几何报告逐字段一致。测试覆盖精确门槛、铜边和孔壁基准、不同孔径换算、不同跨层、共轴叠孔待审及 141 个 PR #46 盲孔的完整覆盖。 [单元测试](evidence/v4-dfm-unit-tests.txt)

```powershell
python -B -m unittest discover -s h03-v4-dfm-u11-2n2-route -p test_independent_hdi_dfm_auditor_v4.py -v
python -B h03-v4-dfm-u11-2n2-route/independent_hdi_dfm_auditor_v4.py --epro h03-u11-wlcsp-v3-dfm-route/native/ZY_AIAR_EVT1_H03_3BOARD_U11_V3_DFM_MECR01_NOT_FOR_FAB.epro2 --dump-dir h03-u11-wlcsp-v3-dfm-route/evidence/post-route --out-dir v4-pr46-recheck
python -B h03-v4-dfm-u11-2n2-route/independent_hdi_dfm_auditor_v4.py --epro h03-v4-dfm-u11-2n2-route/native/ZY_AIAR_EVT1_H03_3BOARD_V4_DFM_U11_2N2_MECR01_NOT_FOR_FAB.epro2 --dump-dir h03-v4-dfm-u11-2n2-route/evidence/reimport-verify --dump-suffix=-reimport.dump.json --out-dir v4-reimport-recheck
```

以上只覆盖已采集的名义盲孔与孔对几何。板边及铜层工艺签核、先后压合顺序和 PCB3 的 2+N+2 制造 EQ 保持 **BLOCKED**。
