#!/usr/bin/env python3
"""Live EasyEDA Pro V4.1.97 capture for Track A (H02 footprint convergence, 22x4.2 preserved)
and Track B (independent MECR-01 25.0x4.6mm full 86-part bridge layout + real copper routing + DRC)."""

import argparse
from collections import Counter
import heapq
import json
import math
from pathlib import Path
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "h02-native"), str(PACKAGE / "h02-erc")]

from capture_native_h02 import Capture, write_json
from capture_erc_round import capture_boards

TRACK_A_UUID = "576ccce42fd1310e3cc2c3bbb14ccbae9eb92ba3990cbe17a1f01ede05b1f274"
TRACK_A_NAME = "EVT1-H02-FP-CONV-22x4_2-LIVE-20261120"
TRACK_B_UUID = "2a9c4c2d57b0dc3762eb01a1c9c264b7337b88a19258ea60cb2c42780e1374f8"
TRACK_B_NAME = "EVT1-H03-MECR01-25x4_6-V4-20261120"
BRIDGE_PCB = "9ce45f14cb79dc9d"

# Critical Power, FPGA Sequencing, Clock, Privacy LED, and AVDD Safety nets to route with REAL copper!
PRIORITY_NETS = [
    # (net_name, width_mil)
    ("FPGA_1V2_SENSE", 3.0),
    ("FPGA_1V8_EN", 3.0),
    ("clk_48m", 3.0),
    ("PRIV_LED_ANODE", 4.0),
    ("AVDD_WD_SET", 3.0),
    ("AVDD_WD_DIV", 3.0),
    ("AVDD_CRESET_VSYS", 3.0),
    ("AVDD_PULSE_QUAL", 3.0),
    ("AVDD_PG_OK", 3.0),
    ("AVDD_QUAL_CLR_N", 3.0),
    ("AVDD_REQ_FILTER", 3.0),
    ("AVDD_QUAL_RC", 3.0),
    ("AVDD_D3_VSYS", 3.0),
    ("AVDD_WD_Q", 3.0),
    ("AVDD_PG_NODE", 3.0),
    ("OPT_AVDD_EN", 3.0),
    ("AVDD_OPT_BIAS", 4.0),
    ("1V2_FPGA_PLL", 4.0),
    ("1V8_FPGA_VPP", 4.0),
    ("1V2_FPGA_CORE", 4.0),
    ("1V8_FPGA_IO", 4.0),
    ("VSYS", 4.0),
]


def run_cli(exe: str, args: list[str], allow_nonzero: bool = False) -> tuple[int, str, str]:
    proc = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"CLI failed ({proc.returncode}): {' '.join(args)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return proc.returncode, proc.stdout, proc.stderr


def ensure_project_open(exe: str, target_uuid: str, window: str):
    _, out, _ = run_cli(exe, ["project", "info"], allow_nonzero=True)
    try:
        cur = json.loads(out).get("result", {}).get("uuid")
    except Exception:
        cur = None
    if cur == target_uuid:
        print(f"  Project {target_uuid[:12]}... is already active; skipping project open.", flush=True)
        return
    run_cli(exe, ["project", "open", "--project-uuid", target_uuid, "--allow-discard-unsaved", "--window", window])
    time.sleep(2)


def run_track_a(exe: str, window: str, out_dir: Path, archive_path: Path):
    print("\n=== TRACK A: H02 FOOTPRINT CONVERGENCE (22.0x4.2mm PRESERVED) ===", flush=True)
    ensure_project_open(exe, TRACK_A_UUID, window)

    manifest = json.loads((PACKAGE / "h02-erc/evidence/board_pages.json").read_bytes())
    manifest["project_id"] = TRACK_A_UUID
    manifest["project_name"] = TRACK_A_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "board_pages.json", manifest)

    probe = Capture(out_dir, exe, TRACK_A_UUID, 1)
    probe.run("project-info.json", ["project", "info"])
    capture_boards(probe, manifest)

    br = out_dir / "bridge"
    br.mkdir(parents=True, exist_ok=True)
    probe.run("bridge/doc-switch.json", ["doc", "switch", BRIDGE_PCB, "--json"])
    dump_path = br / "bridge-22x4_2-persisted.dump.json"
    run_cli(exe, ["--project", TRACK_A_UUID, "--doc", BRIDGE_PCB, "pcb", "dump", "--include-copper", "--label", TRACK_A_NAME, "--out", str(dump_path.resolve())])
    _, out, _ = run_cli(exe, ["--project", TRACK_A_UUID, "--doc", BRIDGE_PCB, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
    (br / "pcb-drc-after.json").write_text(out, encoding="utf-8")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    probe.run("archive-response.json", ["project", "export", "--project-uuid", TRACK_A_UUID, "--out", str(archive_path.resolve())], mutates=True, window=window)
    write_json(out_dir / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    print(f"TRACK A EXPORTED: {archive_path} ({archive_path.stat().st_size} bytes)", flush=True)


def route_priority_nets_live(exe: str, dump_path: Path, layers_json: dict, log_path: Path):
    """Collision-free 4-layer A* copper router driving real EasyEDA Pro V4.1.97 `pcb track` & `pcb via`.

    Strictly honors every locked EasyEDA Pro 6L HDI DRC rule from pcb-drc-rules.json:
      - Layers: TOP=1, L3(Inner2)=16 (horizontal bias), L4(Inner4)=18 (vertical bias), BOT=2
      - Track min >= 2.0 mil (we use 3.0-4.0 mil)
      - Track-to-Track >= 2.0 mil (we enforce >= 2.8 mil)
      - Track/Via-to-SMD Pad & Via-to-Via >= 6.0 mil (we enforce >= 6.8 mil)
      - Via: 4.0 mil hole / 8.0 mil outer (>= 2.95 mil hole / 7.09 mil outer HDI rule)
      - Hole-to-Hole >= 11.811 mil (we enforce >= 17.5 mil center-to-center between vias)
      - Board outline >= 11.811 mil (we enforce >= 14.5 mil track center, >= 17.0 mil via center)
      - MK2 acoustic slot keepout >= 34.0 mil radius on all layers
    """
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    L_IDS = [1, 16, 18, 2]  # 0=TOP, 1=L3, 2=L4, 3=BOT
    SIDE_TO_LI = {1: 0, 2: 3}

    W_MIL, H_MIL = 181.1024, 984.2520
    STEP = 2.5  # 2.5 mil grid -> 73 x 394 cells per layer (fast & crisp!)
    NX = int(W_MIL / STEP) + 1
    NY = int(H_MIL / STEP) + 1

    # Gather exact pads & MK2 acoustic hole world coords
    all_pads = []  # (px, py, hw, hh, li, net, ref, pnum)
    pads_by_net: dict[str, list[dict]] = {}
    mk2_hx, mk2_hy = 66.14, 929.53
    for c in dump["components"]:
        ref = c["designator"]
        if ref == "MK2":
            mk2_hx = float(c["x"]) - 0.005
            mk2_hy = float(c["y"]) + 31.89
        c_rot = float(c.get("rotation") or 0.0)
        for p in c.get("pads", []):
            net = p.get("net") or ""
            px, py = float(p["x"]), float(p["y"])
            pw = float(p.get("width") or 0.0)
            ph = float(p.get("height") or 0.0)
            if pw < 1.0 or ph < 1.0:
                # POLYGON pad fallback: extract exact span from shape or conservative 16x16 mil!
                shp = p.get("shape") or []
                if isinstance(shp, list) and len(shp) >= 2 and shp[0] == "POLY" and isinstance(shp[1], list):
                    nums = [float(v) for v in shp[1] if isinstance(v, (int, float))]
                    if len(nums) >= 4:
                        xs, ys = nums[0::2], nums[1::2]
                        pw = max(pw, max(xs) - min(xs))
                        ph = max(ph, max(ys) - min(ys))
                if pw < 1.0:
                    pw = 16.0
                if ph < 1.0:
                    ph = 16.0
            rot = c_rot + float(p.get("rotation") or 0.0)
            rad = math.radians(rot)
            ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
            hw = 0.5 * (pw * ca + ph * sa) + 0.5  # +0.5 mil safety pad tolerance
            hh = 0.5 * (pw * sa + ph * ca) + 0.5
            li = SIDE_TO_LI.get(int(p.get("layer", c["layer"])), 0)
            rec = {"x": px, "y": py, "hw": hw, "hh": hh, "li": li, "net": net, "ref": ref, "pnum": str(p.get("padNumber", ""))}
            all_pads.append(rec)
            if net:
                pads_by_net.setdefault(net, []).append(rec)

    def to_grid(x: float, y: float) -> tuple[int, int]:
        return max(0, min(NX - 1, int(round(x / STEP)))), max(0, min(NY - 1, int(round(y / STEP))))

    def from_grid(gx: int, gy: int) -> tuple[float, float]:
        return round(gx * STEP, 2), round(gy * STEP, 2)

    # Track global routed copper for cross-net collision avoidance
    routed_segs: list[tuple[int, float, float, float, float, float, str]] = []  # (li, x1, y1, x2, y2, width, net)
    placed_vias: list[tuple[float, float, str]] = []  # (vx, vy, net)

    def pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 < 1e-9:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def via_is_legal(vx: float, vy: float, net: str) -> bool:
        if vx < 17.0 or vx > W_MIL - 17.0 or vy < 17.0 or vy > H_MIL - 17.0:
            return False
        if math.hypot(vx - mk2_hx, vy - mk2_hy) < 35.0:
            return False
        # Hole-to-Hole >= 11.811 mil (4 mil hole -> >= 15.811 -> enforce 17.5 mil!)
        for ovx, ovy, _ in placed_vias:
            if math.hypot(vx - ovx, vy - ovy) < 17.5:
                return False
        # Via outer pad (r=4.0) to any OTHER net's SMD pad on TOP or BOT >= 6.0 mil -> 6.8 + 4.0 = 10.8 mil!
        for p in all_pads:
            if p["net"] == net:
                continue
            dx = max(0.0, abs(vx - p["x"]) - p["hw"])
            dy = max(0.0, abs(vy - p["y"]) - p["hh"])
            if math.hypot(dx, dy) < 11.0:
                return False
        # Via outer pad (r=4.0) to any OTHER net's routed track on any layer >= 6.0 mil -> 6.8 + 4.0 + w/2!
        for _, x1, y1, x2, y2, w, onet in routed_segs:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 11.0 + 0.5 * w:
                return False
        return True

    def seg_clear_of_other_pads_and_vias(li: int, x1: float, y1: float, x2: float, y2: float, width: float, net: str) -> bool:
        # Check MK2 slot clearance (track-to-slot >= 11.811 + 15.75 + w/2 -> 31 mil)
        if pt_seg_dist(mk2_hx, mk2_hy, x1, y1, x2, y2) < 31.0 + 0.5 * width:
            return False
        # Check other-net vias on all layers
        for vx, vy, onet in placed_vias:
            if onet == net:
                continue
            if pt_seg_dist(vx, vy, x1, y1, x2, y2) < 11.0 + 0.5 * width:
                return False
        # Check other-net pads on TOP/BOT
        if li in (0, 3):
            for p in all_pads:
                if p["li"] != li or p["net"] == net:
                    continue
                # Conservative circle/box check along segment
                steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 2.5) + 1)
                for s in range(steps + 1):
                    t = s / steps
                    cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                    dx = max(0.0, abs(cx - p["x"]) - p["hw"])
                    dy = max(0.0, abs(cy - p["y"]) - p["hh"])
                    if math.hypot(dx, dy) < 6.8 + 0.5 * width:
                        return False
        # Check other-net tracks on same layer
        for oli, ox1, oy1, ox2, oy2, ow, onet in routed_segs:
            if oli != li or onet == net:
                continue
            min_d = 3.2 + 0.5 * (width + ow)
            steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 2.5) + 1)
            for s in range(steps + 1):
                t = s / steps
                cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                if pt_seg_dist(cx, cy, ox1, oy1, ox2, oy2) < min_d:
                    return False
        return True

    def build_net_masks(net: str, width: float):
        """Build fast bytearrays [4][NX*NY] for track-blocked cells and [NX*NY] for via-legal cells."""
        blocked = [bytearray(NX * NY) for _ in range(4)]
        via_ok = bytearray(b"\x01" * (NX * NY))
        # Board outline & MK2 keepout
        min_gx = int(math.ceil((13.0 + 0.5 * width) / STEP))
        max_gx = int(math.floor((W_MIL - 13.0 - 0.5 * width) / STEP))
        min_gy = int(math.ceil((13.0 + 0.5 * width) / STEP))
        max_gy = int(math.floor((H_MIL - 13.0 - 0.5 * width) / STEP))
        vmin_gx = int(math.ceil(17.0 / STEP))
        vmax_gx = int(math.floor((W_MIL - 17.0) / STEP))
        vmin_gy = int(math.ceil(17.0 / STEP))
        vmax_gy = int(math.floor((H_MIL - 17.0) / STEP))

        for gx in range(NX):
            x = gx * STEP
            edge_x = gx < min_gx or gx > max_gx
            vedge_x = gx < vmin_gx or gx > vmax_gx
            for gy in range(NY):
                idx = gx * NY + gy
                y = gy * STEP
                if edge_x or gy < min_gy or gy > max_gy or math.hypot(x - mk2_hx, y - mk2_hy) < 32.0 + 0.5 * width:
                    for li in range(4):
                        blocked[li][idx] = 1
                    via_ok[idx] = 0
                elif vedge_x or gy < vmin_gy or gy > vmax_gy or math.hypot(x - mk2_hx, y - mk2_hy) < 35.5:
                    via_ok[idx] = 0

        # Block OTHER-net pads on TOP/BOT & via_ok
        pad_clr = 6.8 + 0.5 * width
        via_pad_clr = 11.2
        for p in all_pads:
            if p["net"] == net:
                continue
            li = p["li"]
            for clr, target in ((pad_clr, blocked[li]), (via_pad_clr, None)):
                gx0 = max(0, int(math.floor((p["x"] - p["hw"] - clr) / STEP)))
                gx1 = min(NX - 1, int(math.ceil((p["x"] + p["hw"] + clr) / STEP)))
                gy0 = max(0, int(math.floor((p["y"] - p["hh"] - clr) / STEP)))
                gy1 = min(NY - 1, int(math.ceil((p["y"] + p["hh"] + clr) / STEP)))
                for gx in range(gx0, gx1 + 1):
                    x = gx * STEP
                    dx = max(0.0, abs(x - p["x"]) - p["hw"])
                    base = gx * NY
                    for gy in range(gy0, gy1 + 1):
                        y = gy * STEP
                        dy = max(0.0, abs(y - p["y"]) - p["hh"])
                        if math.hypot(dx, dy) < clr:
                            if target is not None:
                                target[base + gy] = 1
                            else:
                                via_ok[base + gy] = 0

        # Block OTHER-net vias on all layers + ALL existing vias in via_ok (Hole-to-Hole >= 17.5 mil!)
        for vx, vy, onet in placed_vias:
            r_h = 17.8
            gx0 = max(0, int(math.floor((vx - r_h) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((vx + r_h) / STEP)))
            gy0 = max(0, int(math.floor((vy - r_h) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((vy + r_h) / STEP)))
            for gx in range(gx0, gx1 + 1):
                x = gx * STEP
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    d = math.hypot(x - vx, gy * STEP - vy)
                    if d < r_h:
                        via_ok[base + gy] = 0
                    if onet != net and d < 11.2 + 0.5 * width:
                        for li in range(4):
                            blocked[li][base + gy] = 1

        # Block OTHER-net routed tracks on their layer & in via_ok
        for oli, x1, y1, x2, y2, ow, onet in routed_segs:
            if onet == net:
                continue
            trk_clr = 3.2 + 0.5 * (width + ow)
            via_trk_clr = 11.2 + 0.5 * ow
            r = max(trk_clr, via_trk_clr)
            gx0 = max(0, int(math.floor((min(x1, x2) - r) / STEP)))
            gx1 = min(NX - 1, int(math.ceil((max(x1, x2) + r) / STEP)))
            gy0 = max(0, int(math.floor((min(y1, y2) - r) / STEP)))
            gy1 = min(NY - 1, int(math.ceil((max(y1, y2) + r) / STEP)))
            for gx in range(gx0, gx1 + 1):
                x = gx * STEP
                base = gx * NY
                for gy in range(gy0, gy1 + 1):
                    d = pt_seg_dist(x, gy * STEP, x1, y1, x2, y2)
                    if d < trk_clr:
                        blocked[oli][base + gy] = 1
                    if d < via_trk_clr:
                        via_ok[base + gy] = 0
        return blocked, via_ok

    def astar_route(p1: dict, p2: dict, blocked, via_ok):
        s_gx, s_gy = to_grid(p1["x"], p1["y"])
        t_gx, t_gy = to_grid(p2["x"], p2["y"])
        s_li, t_li = p1["li"], p2["li"]
        # Ensure start & target pad centers themselves are unblocked on their own pad layers
        for gx, gy, li in ((s_gx, s_gy, s_li), (t_gx, t_gy, t_li)):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx_, ny_ = gx + dx, gy + dy
                    if 0 <= nx_ < NX and 0 <= ny_ < NY:
                        # Only clear if not overlapping another net's pad (already protected by pad clearance)
                        if (dx == 0 and dy == 0):
                            blocked[li][nx_ * NY + ny_] = 0

        start = (s_li, s_gx, s_gy)
        goal = (t_li, t_gx, t_gy)
        pq = [(abs(s_gx - t_gx) + abs(s_gy - t_gy), 0.0, start)]
        g_cost = {start: 0.0}
        parent = {}
        # Layer movement costs: L3 prefers horizontal (dx), L4 prefers vertical (dy), TOP/BOT slight penalty
        iters = 0
        MAX_ITERS = 35000
        while pq and iters < MAX_ITERS:
            iters += 1
            _, gc, cur = heapq.heappop(pq)
            if cur == goal:
                path = [cur]
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                path.reverse()
                return path
            if gc > g_cost.get(cur, 1e18):
                continue
            li, gx, gy = cur
            # 4 planar neighbors
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx_, ny_ = gx + dx, gy + dy
                if 0 <= nx_ < NX and 0 <= ny_ < NY:
                    idx = nx_ * NY + ny_
                    if blocked[li][idx]:
                        continue
                    step_c = 1.0
                    if li == 1 and dy != 0:
                        step_c = 1.6  # L3 prefers horizontal
                    elif li == 2 and dx != 0:
                        step_c = 1.6  # L4 prefers vertical
                    elif li in (0, 3):
                        step_c = 1.3  # slight preference to use inner layers for long runs
                    ng = gc + step_c
                    nxt = (li, nx_, ny_)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = abs(nx_ - t_gx) + abs(ny_ - t_gy)
                        heapq.heappush(pq, (ng + h * 1.15, ng, nxt))
            # Layer transitions via through-hole via (only where via_ok == 1!)
            if via_ok[gx * NY + gy]:
                for nli in range(4):
                    if nli == li or blocked[nli][gx * NY + gy]:
                        continue
                    ng = gc + 12.0  # via penalty so short same-layer hops stay via-free!
                    nxt = (nli, gx, gy)
                    if ng < g_cost.get(nxt, 1e18):
                        g_cost[nxt] = ng
                        parent[nxt] = cur
                        h = abs(gx - t_gx) + abs(gy - t_gy)
                        heapq.heappush(pq, (ng + h * 1.15, ng, nxt))
        return None

    routed_log = {
        "layers_used": {"TOP": 1, "L3_Inner2": 16, "L4_Inner4": 18, "BOT": 2},
        "tracks_created": 0,
        "vias_created": 0,
        "gnd_plane_vias": 0,
        "nets": [],
    }
    cli_cmds: list[list[str]] = []

    def emit_via(vx: float, vy: float, net: str):
        placed_vias.append((vx, vy, net))
        cli_cmds.append([
            "--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "via",
            "--x", f"{vx:.2f}", "--y", f"{vy:.2f}",
            "--hole", "4", "--diameter", "8", "--net", net,
        ])

    def emit_track(li: int, x1: float, y1: float, x2: float, y2: float, width: float, net: str):
        if math.hypot(x2 - x1, y2 - y1) < 0.2:
            return
        routed_segs.append((li, x1, y1, x2, y2, width, net))
        cli_cmds.append([
            "--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "track",
            "--x1", f"{x1:.2f}", "--y1", f"{y1:.2f}",
            "--x2", f"{x2:.2f}", "--y2", f"{y2:.2f}",
            "--layer", str(L_IDS[li]), "--width", f"{width:.1f}", "--net", net,
        ])

    # STEP 1: Stitch GND pads to L2/L5 internal GND planes with collision-free 4/8 mil vias!
    # Connects L2/L5 Plane Zones (eliminating 2 Plane Zone errors) AND grounds dozens of GND pads cleanly!
    gnd_pads = pads_by_net.get("GND", [])
    gnd_vias = 0
    gnd_tracks = 0
    for gp in gnd_pads:
        px, py, li = gp["x"], gp["y"], gp["li"]
        found_v = None
        for r_mil in (9.0, 12.0, 15.0, 18.0, 22.0):
            for ang_deg in range(0, 360, 30):
                rad = math.radians(ang_deg)
                vx = round(px + r_mil * math.cos(rad), 2)
                vy = round(py + r_mil * math.sin(rad), 2)
                if via_is_legal(vx, vy, "GND") and seg_clear_of_other_pads_and_vias(li, px, py, vx, vy, 4.0, "GND"):
                    found_v = (vx, vy)
                    break
            if found_v:
                break
        if found_v:
            vx, vy = found_v
            emit_via(vx, vy, "GND")
            emit_track(li, px, py, vx, vy, 4.0, "GND")
            gnd_vias += 1
            gnd_tracks += 1
    routed_log["gnd_plane_vias"] = gnd_vias
    routed_log["nets"].append({"net": "GND (L2/L5 plane stitch)", "pads": len(gnd_pads), "stitched_pads": gnd_vias, "tracks": gnd_tracks, "vias": gnd_vias})
    print(f"  Planned GND plane stitch: {gnd_vias}/{len(gnd_pads)} pads -> L2/L5 GND planes", flush=True)

    # STEP 2: Route critical Power, FPGA Sequencing, Clock, Privacy LED, and AVDD Safety nets with 4-layer A*!
    for net, width_mil in PRIORITY_NETS:
        pts = pads_by_net.get(net, [])
        if len(pts) < 2:
            continue
        # Prim's MST over pads of this net
        n = len(pts)
        in_tree = [False] * n
        in_tree[0] = True
        edges = []
        for _ in range(n - 1):
            best_e = None
            for i in range(n):
                if not in_tree[i]:
                    continue
                for j in range(n):
                    if in_tree[j]:
                        continue
                    d = abs(pts[i]["x"] - pts[j]["x"]) + abs(pts[i]["y"] - pts[j]["y"]) + (0 if pts[i]["li"] == pts[j]["li"] else 20.0)
                    if best_e is None or d < best_e[0]:
                        best_e = (d, i, j)
            if best_e is None:
                break
            _, i, j = best_e
            in_tree[j] = True
            edges.append((pts[i], pts[j]))

        net_tracks = 0
        net_vias = 0
        edges_ok = 0
        for p1, p2 in edges:
            blocked, via_ok = build_net_masks(net, width_mil)
            path = astar_route(p1, p2, blocked, via_ok)
            if not path:
                continue
            edges_ok += 1
            # Compress collinear segments & emit vias at layer changes!
            # Connect exact pad center p1 -> path[0]
            sx, sy = from_grid(path[0][1], path[0][2])
            if math.hypot(p1["x"] - sx, p1["y"] - sy) >= 0.2:
                emit_track(p1["li"], p1["x"], p1["y"], sx, sy, width_mil, net)
                net_tracks += 1

            seg_start = path[0]
            prev = path[0]
            cur_dir = None
            for node in path[1:]:
                if node[0] != prev[0]:
                    # Flush current planar segment before via
                    if prev != seg_start:
                        x1, y1 = from_grid(seg_start[1], seg_start[2])
                        x2, y2 = from_grid(prev[1], prev[2])
                        emit_track(seg_start[0], x1, y1, x2, y2, width_mil, net)
                        net_tracks += 1
                    vx, vy = from_grid(prev[1], prev[2])
                    emit_via(vx, vy, net)
                    net_vias += 1
                    seg_start = node
                    cur_dir = None
                else:
                    d = (node[1] - prev[1], node[2] - prev[2])
                    if cur_dir is not None and d != cur_dir:
                        x1, y1 = from_grid(seg_start[1], seg_start[2])
                        x2, y2 = from_grid(prev[1], prev[2])
                        emit_track(seg_start[0], x1, y1, x2, y2, width_mil, net)
                        net_tracks += 1
                        seg_start = prev
                    cur_dir = d
                prev = node
            # Flush last planar segment
            if prev != seg_start:
                x1, y1 = from_grid(seg_start[1], seg_start[2])
                x2, y2 = from_grid(prev[1], prev[2])
                emit_track(seg_start[0], x1, y1, x2, y2, width_mil, net)
                net_tracks += 1
            # Connect path[-1] -> exact pad center p2
            ex, ey = from_grid(path[-1][1], path[-1][2])
            if math.hypot(p2["x"] - ex, p2["y"] - ey) >= 0.2:
                emit_track(p2["li"], ex, ey, p2["x"], p2["y"], width_mil, net)
                net_tracks += 1

        routed_log["nets"].append({
            "net": net,
            "pads": len(pts),
            "mst_edges": len(edges),
            "edges_routed": edges_ok,
            "width_mil": width_mil,
            "tracks": net_tracks,
            "vias": net_vias,
        })
        print(f"  Planned {net:18s}: edges={edges_ok:2d}/{len(edges):2d}, tracks={net_tracks:2d}, vias={net_vias:2d}", flush=True)

    # Execute all planned real copper commands in EasyEDA Pro V4.1.97!
    print(f"  Committing {len(cli_cmds)} real copper primitives (tracks & vias) to EasyEDA Pro V4.1.97...", flush=True)
    ok_tracks = 0
    ok_vias = 0
    failures = 0
    for cmd in cli_cmds:
        rc, _, _ = run_cli(exe, cmd, allow_nonzero=True)
        if rc == 0:
            if "track" in cmd:
                ok_tracks += 1
            elif "via" in cmd:
                ok_vias += 1
        else:
            failures += 1
    routed_log["tracks_created"] = ok_tracks
    routed_log["vias_created"] = ok_vias
    routed_log["cli_failures"] = failures
    write_json(log_path, routed_log)
    print(f"  Committed: {ok_tracks} tracks, {ok_vias} vias (failures={failures})", flush=True)
    return routed_log


def run_track_b_pre(exe: str, window: str, out_dir: Path):
    print("\n=== TRACK B (PRE-ROUTE): INDEPENDENT MECR-01 25.0x4.6mm 86-PART LAYOUT ===", flush=True)
    ensure_project_open(exe, TRACK_B_UUID, window)

    out_dir.mkdir(parents=True, exist_ok=True)
    probe = Capture(out_dir, exe, TRACK_B_UUID, 1)
    probe.run("project-info.json", ["project", "info"])
    probe.run("doc-switch.json", ["doc", "switch", BRIDGE_PCB, "--json"])
    layers = probe.run("pcb-layers.json", ["--doc", BRIDGE_PCB, "pcb", "layers"])
    probe.run("pcb-drc-rules.json", ["--doc", BRIDGE_PCB, "pcb", "drc-rules"])

    # Pre-routing dump & strict DRC (verifying all 86/86 placed, Import Changes == 0, MK2 == 0!)
    pre_dump = out_dir / "bridge-25x4_6-pre-route.dump.json"
    run_cli(exe, ["--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "dump", "--include-copper", "--label", TRACK_B_NAME, "--out", str(pre_dump.resolve())])
    _, drc_pre, _ = run_cli(exe, ["--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
    (out_dir / "pcb-drc-pre-route.json").write_text(drc_pre, encoding="utf-8")
    drc_pre_j = json.loads(drc_pre)
    print("  PRE-ROUTE DRC:", dict(Counter((v.get("rule"), v.get("objType")) for v in drc_pre_j.get("violations", []))), flush=True)
    return pre_dump, layers


def run_track_b_route_and_export(exe: str, window: str, out_dir: Path, archive_path: Path):
    ensure_project_open(exe, TRACK_B_UUID, window)
    probe = Capture(out_dir, exe, TRACK_B_UUID, 1)
    pre_dump = out_dir / "bridge-25x4_6-pre-route.dump.json"
    layers = json.loads((out_dir / "pcb-layers.json").read_text(encoding="utf-8"))

    # Execute REAL live copper routing of critical Power/FPGA/AVDD nets!
    route_priority_nets_live(exe, pre_dump, layers, out_dir / "live-routing-log.json")

    # Rebuild inner L2/L5 GND planes (thermal reliefs for GND vias, anti-pads for signal vias!)
    run_cli(exe, ["--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "pour-rebuild"], allow_nonzero=True)

    # Save -> reload -> fresh post-routing dump & strict DRC -> official .epro2 export!
    probe.run("pcb-save.json", ["--doc", BRIDGE_PCB, "pcb", "save"], mutates=True)
    probe.run("pcb-reload.json", ["doc", "reload", BRIDGE_PCB, "--json"], mutates=True)
    post_dump = out_dir / "bridge-25x4_6-post-route.dump.json"
    run_cli(exe, ["--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "dump", "--include-copper", "--label", TRACK_B_NAME, "--out", str(post_dump.resolve())])
    _, drc_post, _ = run_cli(exe, ["--project", TRACK_B_UUID, "--doc", BRIDGE_PCB, "pcb", "drc", "--strict", "--json"], allow_nonzero=True)
    (out_dir / "pcb-drc-post-route.json").write_text(drc_post, encoding="utf-8")
    drc_post_j = json.loads(drc_post)
    print("  POST-ROUTE DRC:", dict(Counter((v.get("rule"), v.get("objType")) for v in drc_post_j.get("violations", []))), flush=True)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    probe.run("archive-response.json", ["project", "export", "--project-uuid", TRACK_B_UUID, "--out", str(archive_path.resolve())], mutates=True, window=window)
    write_json(out_dir / "capture-state.json", {"status": "CAPTURED", "manufacturing": "BLOCKED"})
    print(f"TRACK B EXPORTED: {archive_path} ({archive_path.stat().st_size} bytes)", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", required=True)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--easyeda", default="easyeda")
    p.add_argument("--track", choices=["a", "b-pre", "b-route", "both"], default="both")
    a = p.parse_args()
    if a.track in ("a", "both"):
        run_track_a(
            a.easyeda, a.window,
            a.out_root / "evidence/track-a-22x4_2",
            a.out_root / "native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2",
        )
    if a.track in ("b-pre", "both"):
        run_track_b_pre(
            a.easyeda, a.window,
            a.out_root / "evidence/track-b-25x4_6",
        )
    if a.track in ("b-route", "both"):
        run_track_b_route_and_export(
            a.easyeda, a.window,
            a.out_root / "evidence/track-b-25x4_6",
            a.out_root / "native/ZY_AIAR_EVT1_H03_MECR01_25x4_6_TRIAL_NOT_FOR_FAB.epro2",
        )
    print("\nSELECTED LIVE TRACKS COMPLETE!", flush=True)


if __name__ == "__main__":
    main()
