# STATE — evt0-r5-rework（2026-11-13 第二轮）
完成：S0–S4（PCB ec8419f1）+ S5 VBUS/VSYS；缺口51，PCB sha256前缀 dc5f98a7。原生ERC/DRC/重铺：NOT RUN。
下一步：1) 有KiCad时 bash tools/run_native_checks.sh evt0_core（SC_BEFORE=58 SC_AFTER=51），先看J3短线零余量、PGOOD/过孔与内层铜间距；2) USB DP/DM差分对（J1→U2→U1.13/14），需叠层确认、耦合布线、回流分析，不以1.0mm长度差代替阻抗分析；3) 余缺口：音频UART2、显示9、相机。
GitHub Draft PR：未创建（沙箱无网络/gh）。约束：R4/R5只读；R28/J3/J4/DNP不变；不降规则、不绕联锁。

## 第三轮
PCB仍 dc5f98a7，51缺口。原生检查 NOT RUN；USB差分阻断（需叠层/阻抗/工艺参数，且USB类0.25孔需改为≥0.30）；Draft PR 未建。
下一步需：KiCad环境运行 run_native_checks.sh；用户提供叠层与90Ω目标；GitHub 访问权限或让我输出 git bundle。

## 第四轮（S0–S6 r4）
PCB 现为 **c0f1ca5c**（SHA256 `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`）；SCH 不变 `81d599e6d107…`。新增 S6：删除R4既有GND悬空短线 40b55a19（D1.2处0.255mm冗余短线），缺口仍51、模型悬空0。原生ERC/DRC/重铺：**NOT RUN**（无KiCad），见 evidence/native_NOTRUN_S6。
下一步仍为：1) KiCad 10.0.7 内 `bash tools/run_native_checks.sh evt0_core`（先看 J3 短线零余量、PGOOD↔CHG_EN1 过孔0.035mm、VSYS约35mm DNP段）；2) USB 仍阻断（需叠层/90Ω/工艺，USB类过孔0.25→≥0.30）；3) 余缺口按原生重铺后重新统计。GitHub：未建PR。

## 第五轮（H02/H03，2026-11-13，Kimi 窗口）
PCB 现为 **c8aceeaf**（SHA256 `c8aceeafe8a31c9bb3e142cdf1e934a9f47b174c033d30f499b81488a596285d`）；SCH 不变 `81d599e6…`。zy_pcb 自检：缺口 **51→28**（逐网：USB_DP/DM 各4、CAM_DOVDD 5、CAM_2V8 3、CAM_DVDD 2、Y6–Y9 各1、VSYNC/XCLK/PCLK 各1、DISP_D1/D2/PWR_EN 各1）、违规0、悬空0；UUID 1694 无重复。原生 ERC/DRC/重铺：**NOT RUN**（无 KiCad，退出码2，evidence/native_NOTRUN_h02_20261113）。
优先项实测结论：J3 GND短线 0.200=规则（几何强制，保留待原生）；PGOOD 最小余量+0.035 合规；S5 VSYS/VBUS 最小余量+0.05、缺口0。
剩余28缺口：USB 8 阻断（叠层/90Ω/工艺，USB过孔0.25→≥0.30）；20 项拥堵（自动布线器三次失败+手动绕行干跑验证拥堵），需原生交互布线或通道重排，不得为降数量牺牲安全。
分支 hardware/evt0-r5-h02h03-kimi-20261113；Draft PR 见 GitHub。约束保持：R3/R4只读、R28/J3/J4/DNP不变、不降规则、不绕联锁。
