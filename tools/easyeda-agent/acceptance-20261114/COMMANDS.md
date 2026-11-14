# 实际执行命令（按序，工作目录 easyeda_setup/acceptance，E=easyeda.exe）

```
easyeda health                                            # 01_health.json
easyeda doc ls                                            # 05_doc_ls_example.txt
easyeda doc switch 1c4cc46f72ecf8cf                       # 切到原理图页 P1
easyeda sch block-apply block.ams1117_ldo_3v3             # 06_block_apply.json（放置 4 器件，reconcile 报 +3V3 漏接 C1.1/C3.1）
easyeda sch bridge-check                                  # 07_bridge_check.json：0 问题
easyeda sch connectivity                                  # 08_sch_connectivity.json：4 器件 3 网络 8 连接
easyeda sch geometry                                      # 09_sch_geometry.json：器件 bbox 与逐引脚坐标/朝向
easyeda sch autoconnect --pin C1:1 --kind power --net +3V3   # 失败：引脚朝向硬拒绝（如实保留）
easyeda sch autoconnect --pin C3:1 --kind power --net +3V3   # 失败：同上
easyeda sch connect --pin C1:1 --kind power --net +3V3 --direction up --offset 6     # 成功
easyeda sch connect --pin C3:1 --kind power --net +3V3 --direction down --offset 8   # 成功
easyeda sch connectivity                                  # 10_sch_connectivity_fixed.json：10 连接全部正确
easyeda doc switch dbf0342ee1b2d9a4                       # 切到 PCB1
easyeda pcb import-changes                                # 11_pcb_import.json：同步 4 器件
easyeda doc reload                                        # saved → closed → reopened
easyeda pcb list                                          # 12_pcb_list.json：4 元件坐标
easyeda pcb layers                                        # 13_pcb_layers.json：2 铜层 Top/Bottom
easyeda pcb outline-round --rect=-20,-785,742,-135        # 建 762×650 mil 圆角板框
easyeda pcb outline-get                                   # 14_pcb_outline.json
easyeda pcb nets                                          # 15_pcb_nets.json：GND/+3V3/+5V
easyeda pcb dump                                          # 16_pcb_dump.json：实时规则 clearance 5.98mil 等
easyeda pcb move --ids 253e5365d5ee4f4c --dx 50 --dy 50   # 17_move_c2.json：C2 (80.307,-684.878)→(130.307,-634.878)
easyeda pcb list                                          # 回读确认移动
easyeda doc reload                                        # 18_doc_reload.txt：保存→关闭→重开
easyeda pcb list                                          # 19_pcb_list_after_reload.json：坐标持久、uniqueId 稳定
easyeda pcb move --ids 253e5365d5ee4f4c --dx -50 --dy -50 # 恢复 C2 原位
easyeda doc reload                                        # 20_doc_reload_restore.txt
easyeda pcb list                                          # 回读确认恢复 (80.307,-684.878)
easyeda pcb drc                                           # 21_pcb_drc.json：passed=false，10 项 No Connection（未布线焊盘，如实保留）
easyeda doc switch 7960bd579a141949 → 发现空页 → easyeda doc switch 1c4cc46f72ecf8cf
easyeda sch drc                                           # 22_sch_drc.json：通过，0 违规
easyeda sch export-image --out 23_schematic_export.svg    # 原生 SVG 渲染（77,566 字节）
easyeda bom export --type csv                             # 24_bom.csv：4 行，含 LCSC 料号
easyeda pcb export-placement --window 63024054-… --project 0fb3d3be… --doc dbf0342ee1b2d9a4 --out 25_placement.csv  # 官方贴片坐标
```
