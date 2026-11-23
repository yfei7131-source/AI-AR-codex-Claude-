# H03-R6 PCB2 去耦与参考地 · NOT FOR FAB

对 PR #53 的原生 PCB2 输入重算。归档含 400 段线和 47 颗独立过孔，分析包括 API 回读中省略的两段微小铜线。下列几何为离线工程筛查，须以隔离工程原生写入、保存重载及严格 DRC 确认实际整改。

## 可执行增量

定位 21 段 Y≥750 mil 的原有 GND 走线，保持每段网名、层别和端点，从 3 mil 加宽至 4 mil。11 段在待整改的 C5/C10/C32、C9 现有地线铜域，10 段位于该区域其他 GND 铜域。保持焊盘进线、FPGA 时钟、复位及安全信号布线。最小异网铜间距门槛 6.2 mil，最小铜到板边门槛 12 mil。 [21 段清单](decap-ground-widths-r6.json)

## C11 与联合调位门槛

C11 的两端均缺实际铜接触。对既有底面 Y=104–378 mil 共 80 个通过 6 mil 原生器件包络间距及新焊盘避障的放置位置，测试 485 条短折线，并在每个位置加入 1 mil 八方向网格连通候选。目标为 U13.1/U13.4 的 VSYS 和 U13.2/原有 GND 盲孔。未获得任何 VSYS 连接，双端回路候选为 0。继续保留 C11 的原位和本轮布线约束。下一条可执行路径是在冻结机械/装配窗口后重排 U13 邻接的 VSYS 和 AVDD_REQ_FILTER 走廊，或同时增加通过电源内层的换层与返流。 [复跑结果](c11-dual-route-tree.json) · [嘉立创 SMT 指南](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)

## 恢复参考地连续性

PCB2 原生 L2、L5 均为有效 GND 平面。40 颗盲孔仅连各自外层和相邻平面，7 颗通孔均属于其他网络。已绑定足迹中的板内正尺寸电镀孔为 0。编辑器把少量多边形 SMT 焊盘导出为表观 ROUND 孔，原生足迹真实孔字段为 null 或零尺寸。两个外表面铜簇 C12.2 与 C33.2 分别经 d66a84af7c151bc9、3ee8ab886f357cc2 与同一 L2 连通，两个过孔铜盘离该连续平面边界分别为 7.168 和 6.574 mil。保持现有回路，避免重复加线。

对 6/12 和 8/16 mil GND 通孔新增位置筛查，外铜间距 6.2 mil、敏感信号铜间距 11.8 mil、原生孔壁间距 11.811 mil。检查全部已归档铜线、真实跨层过孔、铜到板边、两个平面铜覆盖及邻近同网 SMT 开口。通过这些平面和铜障碍门槛的位置收敛在 MK2 原生装配包络内。冻结麦克风声腔、通孔填盖和阻焊注册要求之前保留 BLOCKED。在既有 GND 盲孔原坐标换通孔的替代扫描也未通过，限制包括孔壁间距、另一面的异网焊盘及 SMT 开口。下一条可执行路径是与声学结构组共同释放非声腔桥区，并在该处重放若干非高速局部地支线以形成 8/16 mil 的空窗。 [6/12 mil 检查](ground-stitches-refined-6-12.json) · [8/16 mil 检查](ground-stitches-refined-8-16.json) · [替代孔检查](replace-blind-6-12.json) · [Infineon 麦克风焊盘及钢网规范](https://www.infineon.com/assets/row/public/documents/24/49/infineon-im69d130-datasheet-en.pdf?fileId=5546d462602a9dc801607a0e46511a2e)

## 复跑

从当前目录执行，将 package 指向仓库的 hardware/evt1-native-eda-20261118。需要 NumPy 与 Shapely 2。脚本使用此前在 PCB2 上验证的归档读取和间距算法。

    python -B c11_dual_route_screen.py package c11-dual-route-tree.json --route-tree
    python -B ground_stitch_refine.py package ground-stitches-refined-6-12.json --hole 6 --land 12
    python -B ground_stitch_refine.py package ground-stitches-refined-8-16.json --hole 8 --land 16
    python -B ground_via_replace.py package replace-blind-6-12.json
