# Round-3 原生 3D 交付边界

## 最终文件

以下 `-retry-02` 目录对应最终 Round-3／refinement-5 原生候选回读；同名无后缀目录为早期历史导出，不能替代最终版本。

| 板 | 最终 OBJ | 最终 STEP |
|---|---|---|
| M-MAIN-L | `M-MAIN-L-obj-retry-02/board.obj.zip`，2,106,251 bytes | **不存在／BLOCKED** |
| M-OPT-BRIDGE | `M-OPT-BRIDGE-obj-retry-02/board.obj.zip`，985,661 bytes | `M-OPT-BRIDGE-step-retry-02/board.step`，10,696,883 bytes |
| M-AUD-R | `M-AUD-R-obj-retry-02/board.obj.zip`，362,342 bytes | `M-AUD-R-step-retry-02/board.step`，4,948,327 bytes |

主板 STEP 真实错误：官方导出内容 22,150,672 bytes，超过 20 MiB 传输上限。原始错误保留于 `../layout/review-3/M-MAIN-L/13-export-3d-step.log`。未删减模型、未伪造文件扩展名。

## 检查范围

- 35／35 个当前已放置候选有模型绑定：主板 21／21、桥板 10／10、右板 4／4。
- `autoGenerateModels:false`，`modelCoverage:binding-only`。
- 文件存在性、大小、SHA256 和 OBJ ZIP CRC 已由 `../tools/finalize_return.py` 复核。
- 机器可读模型变换、绑定及文件结果见 `3D_AND_BINDINGS.json`。
- 不是完整 PCBA／整机：未放器件、JBD 光机、FPC、连接器、电池、壳体、铰链、鼻托和镜片未包含。
- `previewVerified:false`；没有结构装配、碰撞、热、重心、40 g 或双目光学可行性 PASS。
- `actual-both.svg` 是原生回读的辅助渲染；官方画布截图因隐藏标签页未取得可靠结果，不将 SVG 冒充官方截图。
