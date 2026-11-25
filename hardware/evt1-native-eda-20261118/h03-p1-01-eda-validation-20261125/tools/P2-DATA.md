# P2 三板原生数据输入

本目录从 PR #64 的 R11-MASTER EPRO2 和同源嘉立创 EDA 专业版读回生成。P2 优先使用 `manifest.json` 定位三板 JSON 与 Protel2网表。先复核 EPRO2、各文件 SHA-256 和采集阶段，再运行可布线性评估。状态保持 **NOT FOR FAB**。

| 对象 | PCB1 | PCB2 | PCB3 |
| --- | ---: | ---: | ---: |
| 器件 | 118 | 86 | 53 |
| 物理焊盘实体 | 507 | 328 | 239 |
| 已分配网名的器件/焊盘编号对 | 477 | 303 | 191 |
| 命名网络 | 112 | 58 | 37 |
| 原生线段 | 851 | 434 | 409 |
| 过孔（其中盲孔） | 98（62） | 49（42） | 54（42） |
| 原生 GND 内层铜面 | 2 | 2 | 2 |
| 板级原生禁布区 | 6 | 0 | 6 |
| 封装机械切割 | 1 | 1 | 1 |
| 原生连接错误 | 322 | 227 | 127 |

## 再生成

以下输入来自同一个原生工程 UUID，且同 R11 归档内容一致。采集目录使用 `PCB1`、`PCB2`、`PCB3` 前缀，各含 `-copper.json`、`-drc.json`、`-erc.json`、`-netlist.json` 和 `.net`。使用 `fresh-native-import` 标记本轮从 R11 文件建立的未编辑隔离工程采集。使用 `r11-milestone-native` 标记 R11 发布时的原始采集。

~~~powershell
python extract_p2.py --archive <R11.epro2> `
  --archive-sha256 758618cb4bbb12a5ed34200cbf7c51f2e476c80ed9eee96643efed4764791074 `
  --source-commit 79ce0553f6aaa90ebfee773dceefaf5505d11f30 `
  --capture-dir <capture-directory> --readback-dir <capability-read-directory> `
  --out <new-output-directory> --capture-class fresh-native-import
~~~

本轮隔离回读使用 CLI、daemon 和 connector v1.20.0，以及嘉立创 EDA 4.1.97。可选 `--readback-dir` 接受同一工程的 `PCB*-rules.json` 和 `PCB*-stackup.json`，按板 UUID 对账每网规则指派及逻辑铜层。

## 坐标与验证边界

- 坐标采用 mil、Y 向上，三板原点均为 `[0,0]`。物理铜层顺序使用嘉立创原生 ID `[1,15,16,17,18,2]`，15 和 18 为参考地平面。保留实际平面外边和全部内孔。持久原档提供 3 个在线 dump 省略的超短线段。
- 焊盘用封装本地几何、工件位置与在线逐焊盘回读交叉验证。圆与椭圆按精确尺寸提供。矩形/椭圆中心使用原生变换的锚点，附上 `nativePadOffsetBoundMil` 及原始字段，计算间距时使用该偏移包络。POLYGON 提供真实投影顶点。44 个多边形焊盘的编辑器孔字段缺少原生 PAD 钻孔记录，保留两边证据并使用独立的机械声孔记录。
- 过孔提供实际孔径、环外径、所跨层、有效铜层、规则名和原始参数。J2/J3、板外 BAT1/SPK1 的意图由原生 Protel2 网表和 R11 审计提供。重复物理焊盘保留独立图元 ID，声明网名与实例网名的大小写差异保留两列，歧义输入会停止生成。
- 原生规则包括 `RULE`、`RULE_TEMPLATE`、盲孔定义及在线规则摘要。保留原始 `unit` 标签及数值。R11 项目级准入仍包括兼容的 6 mil 共享层铜距、3 mil 盲孔径向环宽、0.075 至 0.150 mm 激光孔范围、0.350 mm 板边保护以及对应电气/孔壁规则。P2 网类约束按 R11 已核验适用场景选用。
- 六个逻辑铜层已有原生证据，物理叠层记录缺少四个内层和匹配介质构造。0.80 mm HDI 目标、壳体净空、镜片及光机包络、板厂确认仍需工程证据。继续沿用 40 g、真实双目透明 AR 和制造门禁。 [R11 STATE](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/79ce0553f6aaa90ebfee773dceefaf5505d11f30/hardware/evt1-native-eda-20261118/h03-codex-r11-master-20261125/STATE.md) · [继承的 V4 DFM 约束](https://github.com/yfei7131-source/AI-AR-codex-Claude-/blob/79ce0553f6aaa90ebfee773dceefaf5505d11f30/hardware/evt1-native-eda-20261118/h03-v4-dfm-u11-2n2-route/DFM_V4.md)
