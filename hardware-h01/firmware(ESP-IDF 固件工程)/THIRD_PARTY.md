# 固定第三方依赖与许可证

本项目原创设备适配层使用API调用官方组件，未复制未知许可证项目的固件或PCB。依赖源码由官方registry/SDK下载到项目外ASCII构建目录，保留上游LICENSE；仓库记录manifest和lock。

| 依赖 | 固定版本 / 来源 | 许可与核验 |
|---|---|---|
| ESP-IDF | v5.4.3；[官方release](https://github.com/espressif/esp-idf/releases/tag/v5.4.3) | SDK总体Apache-2.0，各子组件另带许可；发行时应保留相应声明 |
| esp32-camera | 2.0.16；[官方registry](https://components.espressif.com/components/espressif/esp32-camera/versions/2.0.16) | 实际下载组件根目录LICENSE为Apache-2.0；lock记录组件hash |
| esp_jpeg | 1.3.2；camera的传递依赖 | 实际组件根目录LICENSE为Apache-2.0；具体子目录的独立许可证亦须保留；lock记录hash |
| NimBLE | 固定为ESP-IDF v5.4.3内置子模块版本 | 原生Apache NimBLE/ESP port随SDK提供许可；未另取浮动master |
| Zig host编译器 | 0.13.0；PyPI ziglang固定版本，安装于项目外 | 仅开发工具，使用所带Clang编译C11核心；不纳入设备bin |

本次实际工具下载SHA256：

```text
esp-idf-v5.4.3.zip
743c97187d3679970af1d373db669c2bfc1e60c35e5660fdb317b9557c5fba59
xtensa-esp-elf-14.2.0_20250730-x86_64-w64-mingw32.zip
9ce39218884cfbf428f9f6b1cb6afd9341e327f5e1a8d1d0369c21ae6e3b0828
cmake-3.30.2-windows-x86_64.zip
48bf4b3dc2d668c578e0884cac7878e146b036ca6b5ce4f8b5572f861b004c25
ninja-win.zip (1.12.1)
f550fec705b6d6ff58f2db3c374c2277a37691678d6aba463adcbb129108467a
esp32ulp-elf-2.38_20240113-win64.zip
3a7627008ac92d1580542b95c696449e56aaa1d0881dc3ef5fd5c60afc77a49d
```

工具二进制hash与官方v5.4.3 `tools/tools.json` 核对；IDF完整zip取自官方 `dl.espressif.com/github_assets/espressif/esp-idf/releases/download/v5.4.3/esp-idf-v5.4.3.zip`，上列为实际下载校验值。未来产品分发仍需按实际使用组件整理许可，不以本表替代最终合规审查。
