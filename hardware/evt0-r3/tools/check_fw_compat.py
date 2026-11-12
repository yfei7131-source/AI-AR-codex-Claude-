"""Compare the R3 pin map with positional gl_board initializers (no firmware writes).
Exit 1: mismatched pin, incomplete input or unsupported source syntax.
Exit 2: declared pins agree, production freeze blocked by locked capture and optical selection.
"""
import argparse
import csv
import hashlib
import re
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
DEFAULT = "CONFIG_GL_BOARD_AIAR_EVT0_R3"
FIELD_NET = {
    "button_gpio": "KEY_BOOT", "xclk": "CAM_XCLK_R", "sda": "CAM_SIOD", "scl": "CAM_SIOC",
    "vsync": "CAM_VSYNC", "href": "CAM_HREF", "pclk": "CAM_PCLK_R", "cam_pwr_en": "CAM_PWR_EN",
    "vbat_adc": "VBAT_ADC", "mic_sck": "MIC_SCK", "mic_ws": "MIC_WS", "mic_sd": "MIC_SD",
    "audio_uart_tx": "U0TXD", "audio_uart_rx": "U0RXD", **{f"d[{i}]": f"CAM_Y{i+2}" for i in range(8)},
}
META = {"name", "configured", "privacy_interlock_verified"}


def source(path):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(encoding="utf-8"), flags=re.S)


def parse_profile(main, macro):
    struct = re.search(r"typedef\s+struct\s*\{([^{}]+)\}\s*gl_board\s*;", source(main / "board.h"))
    if not struct:
        raise ValueError("gl_board declaration not found")
    fields = []
    for decl in struct[1].strip().rstrip(";").split(";"):
        match = re.fullmatch(r"\s*(?:const\s+char\s*\*|int\s+|bool\s+)(.+?)\s*", decl, re.S)
        if not match:
            raise ValueError(f"unsupported gl_board declaration: {decl}")
        for field in match[1].split(","):
            ident = re.fullmatch(r"\s*(\w+)(?:\[(\d+)\])?\s*", field)
            if not ident:
                raise ValueError(f"unsupported field: {field}")
            if ident[2]:
                fields.extend(f"{ident[1]}[{i}]" for i in range(int(ident[2])))
            else:
                fields.append(ident[1])
    if set(fields) != META | set(FIELD_NET) or len(fields) != len(set(fields)):
        raise ValueError("gl_board fields changed: review FIELD_NET")
    branches = re.findall(r"^#(?:if|elif)\s+" + re.escape(macro) + r"\s*$([^#]*)", source(main / "board.c"), re.M)
    if len(branches) != 1:
        raise ValueError(f"expected exactly one branch for {macro}")
    init = re.search(r"static\s+const\s+gl_board\s+\w+\s*=\s*\{([^;]+)\}\s*;", branches[0])
    if not init:
        raise ValueError("selected positional initializer not found")
    # Require simple integer literals for GPIO and literal booleans for policy.
    values = [v.strip() for v in init[1].replace("{", "").replace("}", "").split(",")]
    if len(fields) != len(values):
        raise ValueError("initializer/struct length differs")
    profile = dict(zip(fields, values))
    if profile["configured"] != "true" or profile["privacy_interlock_verified"] != "false":
        raise ValueError("expected configured and locked bench profile")
    return {name: int(val) for name, val in profile.items() if name not in META}


def check(repo, pinmap, macro):
    main = repo / "firmware/main"
    pins = parse_profile(main, macro)
    with pinmap.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by_gpio = {int(row["gpio"]): row for row in rows}
    if len(rows) != len(by_gpio):
        raise ValueError("duplicate hardware GPIO")
    used = {gpio: field for field, gpio in pins.items() if gpio >= 0}
    if len(used) != sum(gpio >= 0 for gpio in pins.values()):
        raise ValueError("duplicate active profile GPIO")
    matches = 0
    results = []
    for gpio, row in sorted(by_gpio.items()):
        net = row["hw_net"]
        field = used.get(gpio, "")
        if field:
            if FIELD_NET[field] != net:
                raise ValueError(f"GPIO{gpio}: {field} needs {FIELD_NET[field]}, found {net}")
            verdict = "match"
            matches += 1
        elif net.startswith("DISP_"):
            verdict = "reserved: optical interface unreviewed"
        elif net == "STRAP46":
            verdict = "strap only: never enable audio"
        elif net in {"NC", "USB_DP", "USB_DM"}:
            verdict = "hardware reserved"
        elif macro != DEFAULT:
            verdict = "not allocated in selected reference profile"
        else:
            raise ValueError(f"unclassified R3 net {net} on GPIO{gpio}")
        results.append([gpio, row["module_pin"], net, row["constraint"], field, macro, verdict])
    if set(used) - set(by_gpio) or (macro == DEFAULT and matches != 22):
        raise ValueError("missing bonded GPIO or R3 allocation (expected 22)")
    with pinmap.with_name("pinmap_fw_crosscheck.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["gpio","module_pin","hw_net","constraint","fw_field","fw_profile","verdict"])
        w.writerows(results)
    report = [
        "# R3 firmware GPIO cross-check", "", f"Profile: `{macro}`. Matched {matches} active assignments.",
        f"board.h SHA256: `{hashlib.sha256((main/'board.h').read_bytes()).hexdigest()}`",
        f"board.c SHA256: `{hashlib.sha256((main/'board.c').read_bytes()).hexdigest()}`",
        "", "See [per-pin results](pinmap_fw_crosscheck.csv). GPIO43/44 are the MCU side of the optional R33/R34 links.",
        "Camera interlock remains false. Display pins have no reviewed sink. GPIO46 is a reset strap only.",
        "Exit 2 = numerical match with explicit open hardware gates. No manufacturing release.", "",
    ]
    pinmap.with_name("fw_compat_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"{macro}: {matches} GPIO matches; optical and camera gates open; exit=2")
    return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("repo_root", type=Path)
    p.add_argument("pinmap", type=Path, nargs="?", default=DESIGN/"H02/evt0_core/pinmap_hw.csv")
    p.add_argument("--profile", default=DEFAULT)
    args = p.parse_args()
    try:
        result = check(args.repo_root, args.pinmap, args.profile)
    except (ValueError, OSError, KeyError) as error:
        p.exit(1, f"FAIL: {error}\n")
    raise SystemExit(result)

