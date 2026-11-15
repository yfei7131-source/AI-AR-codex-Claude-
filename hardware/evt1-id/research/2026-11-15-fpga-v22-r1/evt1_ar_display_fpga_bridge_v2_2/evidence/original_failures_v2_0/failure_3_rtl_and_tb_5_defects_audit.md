# V2.0 原始源码 (`27963cf` / `2ff56de`) 五大缺陷复盘与修复证据

1. **缺陷 1：C 仿真断言失败与 Git Bundle 打包顺序缺陷**
   - 现象：初始提交 `27963cf` 中 `dual_clock_rtl_event_sim.c` 在第 520 行和第 568 行触发 `assert` 中止，导致 `evidence/rtl_dual_clock_test_log.txt` 为 0 字节空文件；且 `git bundle` 在 `git commit --amend` 前被暂存，导致仓库内嵌 bundle 仍指向旧提交。
2. **缺陷 2：Verilog Testbench (`tb/tb_jbd_dual_bridge.v`) Test 2 CRC-16 校验值错误**
   - 现象：`tb_jbd_dual_bridge.v` 第 85–86 行发送的 RLE4 测试包 `[0x11, 0x00, 0x00, 0x00, 0x05, 0xFF, 158, 0x33, 0xFA, 0xCE]` 手写了错误 CRC `16'h9A0B`，而真实 CRC-16-CCITT (`poly=0x1021, init=0xFFFF`) 为 **`16'h3FFC`**，导致仿真时 `bridge_crc_err = 1`、`bad_packet_cnt = 1`，测试包被丢弃。
3. **缺陷 3：2-bit 帧存寻址越界与像素未解包 (`rtl/binocular_scanline_engine.v`)**
   - 现象：`binocular_scanline_engine.v` 虽定义了 `expand_2bpp()` 函数却从未调用；在 `MODE_640x480_2BPP` 与 `MODE_640x400_2BPP_PP` 下，每个 16-bit SPRAM 字存储 **8 个 2-bit 像素**（每行 640 像素仅需 **80 字 = 160 字节**），但原代码仍按 `spram_y * 16'd160` 寻址 160 字，导致 `y >= 410` 时 `410 * 160 = 65,600 > 65,535` 发生 **16 位地址溢出回绕**，且每字只解包了 4 个像素。
4. **缺陷 4：CDC 异步 FIFO (16B) 与 Stage RAM (1024W) 缓存溢出隐患**
   - 现象：`qspi_cdc_async_fifo.v` 深度仅 16 字节，当 `s3_qspi_slave_rx.v` 进入 `ST_RLE_EXPAND` 展开长游程（如 250 字节需暂停 `fifo_rd_en` 达 5.2 μs）时，40 MHz QSPI（50 ns/字节）持续输入的后续字节在 800 ns（16 字节）后即撑爆 FIFO（`overflow_latched = 1`）；同时当单包解压数据超过 `stage_ram[0:1023]`（1024 字）时未置位错误标志，仍会截断提交。
5. **缺陷 5：双缓冲 (`MODE_640x400_2BPP_PP`) 前后台读写未隔离**
   - 现象：`jbd_dual_bridge_top.v` 未将 `active_front_bank` 传回 `s3_qspi_slave_rx.v`，导致主机写入始终固定落在 `0x0000`（Bank 0/1），无法自动写入后台缓冲区（Back Buffer: `~active_front_bank ? 16'h8000 : 16'h0000`），且非双缓冲模式下 `active_front_bank` 也会错误翻转。
