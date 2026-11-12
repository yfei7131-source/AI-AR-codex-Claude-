# R3 firmware GPIO cross-check

Profile: `CONFIG_GL_BOARD_AIAR_EVT0_R3`. Matched 22 active assignments.
board.h SHA256: `480ea6721a595cb1ef2206780be68e6f6a0a22a2ff0c7127553e0a17483b61c5`
board.c SHA256: `b1410fd2050e5ac8c41ac1dec14eebd8c318457bb0169a1ac94c6357ef499e8c`

See [per-pin results](pinmap_fw_crosscheck.csv). GPIO43/44 are the MCU side of the optional R33/R34 links.
Camera interlock remains false. Display pins have no reviewed sink. GPIO46 is a reset strap only.
Exit 2 = numerical match with explicit open hardware gates. No manufacturing release.
