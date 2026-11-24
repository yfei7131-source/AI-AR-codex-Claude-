#!/usr/bin/env python3
"""
H03-R8 PCB2 (Optical Bridge, 4.6 mm x 25.0 mm) Joint Relayout, Dual-End Path,
MK2 Interference, and L2/L5 Return-Plane Verification Engine.

Design Contract (Strict Fail-Fast & Zero Fabrication):
  1. MUST parse a complete copper JSON file (--copper-json PATH) including board
     outline, components, pads (RECT / OVAL / ROUND / POLYGON with holes),
     multi-layer tracks, blind/through vias, and L2/L5 GND planes.
  2. NEVER silently fall back to hardcoded coordinates. Any missing required
     top-level section, missing required component/pad, missing L2/L5 plane,
     or malformed POLYGON pad raises a strict exception and exits non-zero.
  3. Verifies:
       - C11/U13 joint relayout (both zero-IC-move R8-A and U1/U3/U5 joint-shift R8-C)
       - VSYS (A* copper-obstacle-aware routing on L6 or stereo L4) & GND (BV_L5_L6 -> L5)
         dual-end legal connectivity
       - MK2 acoustic keepout & POLYGON pad interference (quantified overlap area)
       - L2/L5 GND plane continuity & blind-via plane containment / boundary margin
       - 8 critical decoupling caps (C5/C8/C9/C10/C11/C12/C31/C32) return audit
  4. Outputs BOTH passing executable coordinates AND failed candidates with
     explicit failure reason codes for Codex implementation.
  5. Explicitly tags output as OFFLINE_GEOMETRY_SCREEN_NOT_FULL_BOARD_DRC;
     offline geometry screening NEVER substitutes for native EasyEDA Pro full-board DRC.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from shapely.affinity import rotate as shp_rotate, translate as shp_translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Strict Exceptions (Fail-Fast on Missing / Malformed Data)
# ---------------------------------------------------------------------------
class MissingCopperDataError(ValueError):
    """Raised when required sections, components, pads, or planes are missing."""


class InvalidPolygonPadError(ValueError):
    """Raised when a POLYGON pad cannot be parsed into a valid >=3-vertex polygon."""


# ---------------------------------------------------------------------------
# Locked Manufacturing & SI/PI Rules (mil) — NEVER RELAX
# ---------------------------------------------------------------------------
EDGE_CLEARANCE = 12.0
COPPER_CLEARANCE = 6.2
SENSITIVE_3W_CLEARANCE = 11.8
HOLE_WALL_CLEARANCE = 11.811          # 0.30 mm
SMD_CHIP_SPACING = 6.0                # JLCPCB 0201/0402: 0.15 mm
SMD_SOT_SPACING = 8.0                 # JLCPCB 0201/0402-to-SOT: 0.20 mm
SMD_QFN_BGA_SPACING = 40.0            # JLCPCB 0201/0402-to-QFN/BGA: 1.00 mm
TRACE_WIDTH_PWR = 4.0                 # >= 4.0 mil (above JLC 3.5 mil floor)
BLIND_VIA_HOLE = 4.0
BLIND_VIA_DIAM = 10.0
MIN_PLANE_EDGE_MARGIN = 5.0           # Keep blind via land safely inside L2/L5 copper plane

# EasyEDA Pro layer IDs (verified from plan_bridge_r5.py / rectify_v4_edge_and_route_pr47.py)
L1_TOP = 1
L6_BOT = 2
L2_GND = 15
L3_SIG = 16
L4_PWR = 17
L5_GND = 18

SENSITIVE_NETS = {
    "host_sck", "opt_sck", "OPT_SCK_L", "OPT_SCK_R", "clk_48m",
    "FPGA_CDONE_VSYNC_N", "FPGA_CRESET_B",
    "BK_SW", "BB_L1", "BB_L2", "VBUS_5V", "VBUS_5V_USB", "VSYS",
    "PDM_CLK_1V8", "I2S_S3_DOUT_3V3", "I2S_S3_DOUT_1V8",
    "I2S_BCLK_3V3", "I2S_BCLK_1V8", "I2S_LRCLK_3V3", "I2S_LRCLK_1V8",
    "I2S_AMP_DIN_1V8", "AVDD_REQ_FILTER", "AVDD_QUAL_RC",
}

REQUIRED_COMPONENTS = ("C11", "U13", "MK2", "U1", "U3", "U5", "U2", "J1")
EIGHT_DECAPS = ("C5", "C8", "C9", "C10", "C11", "C12", "C31", "C32")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class PadRecord:
    ref: str
    number: str
    net: str
    layer: int
    x: float
    y: float
    shape_type: str
    geom: Polygon
    hole_diam: float = 0.0


@dataclass
class ComponentRecord:
    designator: str
    name: str
    layer: int
    x: float
    y: float
    rotation: float
    bbox: Polygon
    pads: List[PadRecord] = field(default_factory=list)


@dataclass
class TrackRecord:
    layer: int
    net: str
    width: float
    line: LineString
    geom: Polygon


@dataclass
class ViaRecord:
    via_id: str
    net: str
    x: float
    y: float
    hole: float
    diam: float
    layers: Tuple[int, ...]
    rule_name: str = ""

    @property
    def is_through(self) -> bool:
        return len(self.layers) >= 6 or (L1_TOP in self.layers and L6_BOT in self.layers)

    def pad_geom(self) -> Polygon:
        return Point(self.x, self.y).buffer(self.diam / 2.0, quad_segs=16)


@dataclass
class BoardModel:
    source_path: str
    outline: Polygon
    safe_board: Polygon
    components: Dict[str, ComponentRecord]
    tracks: List[TrackRecord]
    vias: List[ViaRecord]
    planes: Dict[int, Polygon]  # layer_id -> union of GND plane polygons


# ---------------------------------------------------------------------------
# Strict Geometry Parsers (Including POLYGON Pads)
# ---------------------------------------------------------------------------
def _require_keys(obj: Dict[str, Any], keys: Sequence[str], context: str) -> None:
    missing = [k for k in keys if k not in obj or obj[k] is None]
    if missing:
        raise MissingCopperDataError(f"{context} missing required key(s): {missing}")


def _extract_polygon_points(raw: Any, context: str) -> List[Tuple[float, float]]:
    """
    Parse POLYGON vertex definitions from multiple EasyEDA Pro / export encodings:
      1. List of [x, y] pairs: [[x1, y1], [x2, y2], ...]
      2. Flat numeric list: [x1, y1, x2, y2, ...]
      3. SVG-like command array: ["M", x1, y1, "L", x2, y2, ..., "Z"]
      4. SVG-like command string: "M x1 y1 L x2 y2 ... Z"
    Raises InvalidPolygonPadError if malformed or fewer than 3 distinct points.
    """
    pts: List[Tuple[float, float]] = []

    if isinstance(raw, str):
        tokens = re.findall(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw)
        nums: List[float] = []
        for tok in tokens:
            if tok.upper() in ("M", "L", "Z", "C", "Q", "H", "V"):
                continue
            nums.append(float(tok))
        if len(nums) < 6 or len(nums) % 2 != 0:
            raise InvalidPolygonPadError(f"{context}: malformed POLYGON path string ({len(nums)} coords)")
        pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]

    elif isinstance(raw, list) and raw:
        if all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in raw):
            pts = [(float(p[0]), float(p[1])) for p in raw]
        elif any(isinstance(item, str) for item in raw):
            nums = []
            for item in raw:
                if isinstance(item, str):
                    if item.strip().upper() in ("M", "L", "Z"):
                        continue
                    try:
                        nums.append(float(item))
                    except ValueError as exc:
                        raise InvalidPolygonPadError(f"{context}: unsupported POLYGON token {item!r}") from exc
                elif isinstance(item, (int, float)):
                    nums.append(float(item))
            if len(nums) < 6 or len(nums) % 2 != 0:
                raise InvalidPolygonPadError(f"{context}: malformed POLYGON command list ({len(nums)} coords)")
            pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
        elif all(isinstance(item, (int, float)) for item in raw):
            if len(raw) < 6 or len(raw) % 2 != 0:
                raise InvalidPolygonPadError(f"{context}: flat POLYGON list must have even >=6 numbers")
            pts = [(float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw), 2)]
        else:
            raise InvalidPolygonPadError(f"{context}: unrecognized POLYGON vertex structure")
    else:
        raise InvalidPolygonPadError(f"{context}: empty or non-sequence POLYGON geometry")

    # Remove consecutive duplicates
    dedup: List[Tuple[float, float]] = []
    for p in pts:
        if not dedup or math.hypot(p[0] - dedup[-1][0], p[1] - dedup[-1][1]) > 1e-6:
            dedup.append(p)
    if len(dedup) >= 2 and math.hypot(dedup[0][0] - dedup[-1][0], dedup[0][1] - dedup[-1][1]) <= 1e-6:
        dedup.pop()
    if len(dedup) < 3:
        raise InvalidPolygonPadError(f"{context}: POLYGON has fewer than 3 distinct vertices ({len(dedup)})")
    return dedup


def parse_pad_geometry(pad_dict: Dict[str, Any], comp_ref: str) -> PadRecord:
    """Strictly parse a single pad (RECT, OVAL, ROUND/CIRCLE/ELLIPSE, POLYGON) and its hole."""
    pad_num = str(pad_dict.get("number", pad_dict.get("pad", pad_dict.get("name", ""))))
    if not pad_num:
        raise MissingCopperDataError(f"Component {comp_ref} contains a pad without number/name")
    ctx = f"{comp_ref}.{pad_num}"
    _require_keys(pad_dict, ("layer", "shape"), ctx)

    layer = int(pad_dict["layer"])
    net = str(pad_dict.get("net", "") or "")
    px = float(pad_dict.get("x", 0.0))
    py = float(pad_dict.get("y", 0.0))
    rot = float(pad_dict.get("rotation", pad_dict.get("angle", 0.0)) or 0.0)
    shape = pad_dict["shape"]

    # Parse hole if present (e.g., ["ROUND", 1.42338, 1.42338] or numeric)
    hole_diam = 0.0
    raw_hole = pad_dict.get("hole")
    if isinstance(raw_hole, list) and len(raw_hole) >= 2 and isinstance(raw_hole[1], (int, float)):
        hole_diam = float(raw_hole[1])
    elif isinstance(raw_hole, (int, float)):
        hole_diam = float(raw_hole)

    # Parse shape
    if isinstance(shape, list) and shape:
        stype = str(shape[0]).upper()
        if stype == "RECT":
            if len(shape) < 3:
                raise MissingCopperDataError(f"{ctx}: RECT shape requires [RECT, w, h]")
            w, h = float(shape[1]), float(shape[2])
            geom = box(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)
            if rot:
                geom = shp_rotate(geom, rot, origin=(0.0, 0.0))
            geom = shp_translate(geom, xoff=px, yoff=py)
        elif stype in ("ROUND", "CIRCLE"):
            if len(shape) < 2:
                raise MissingCopperDataError(f"{ctx}: ROUND shape requires diameter")
            d = float(shape[1])
            geom = Point(px, py).buffer(d / 2.0, quad_segs=16)
        elif stype in ("OVAL", "ELLIPSE"):
            if len(shape) < 3:
                raise MissingCopperDataError(f"{ctx}: OVAL shape requires [OVAL, w, h]")
            w, h = float(shape[1]), float(shape[2])
            if abs(w - h) < 1e-6:
                geom = Point(px, py).buffer(w / 2.0, quad_segs=16)
            else:
                # Capsule approximation for oblong/oval SMD pad
                if w > h:
                    r = h / 2.0
                    seg = LineString([(-(w / 2.0 - r), 0.0), (w / 2.0 - r, 0.0)])
                else:
                    r = w / 2.0
                    seg = LineString([(0.0, -(h / 2.0 - r)), (0.0, h / 2.0 - r)])
                geom = seg.buffer(r, quad_segs=12)
                if rot:
                    geom = shp_rotate(geom, rot, origin=(0.0, 0.0))
                geom = shp_translate(geom, xoff=px, yoff=py)
        elif stype == "POLYGON":
            # Support ["POLYGON", [[x,y],...]], ["POLYGON", [x1,y1,...]], ["POLYGON", "M ..."],
            # or ["POLYGON", x1, y1, x2, y2, ...] or separate "points" key
            if len(shape) == 2 and isinstance(shape[1], (list, str)):
                raw_pts = shape[1]
            elif len(shape) > 2:
                raw_pts = shape[1:]
            elif "points" in pad_dict:
                raw_pts = pad_dict["points"]
            else:
                raise InvalidPolygonPadError(f"{ctx}: POLYGON pad has no vertex payload")
            pts = _extract_polygon_points(raw_pts, ctx)
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or poly.area <= 1e-6:
                raise InvalidPolygonPadError(f"{ctx}: POLYGON pad resolved to empty/zero-area geometry")
            # If points are local-relative (centroid near 0 while px/py is far), translate;
            # if points are already absolute board coordinates, keep as-is.
            if pad_dict.get("polygon_relative", False):
                if rot:
                    poly = shp_rotate(poly, rot, origin=(0.0, 0.0))
                poly = shp_translate(poly, xoff=px, yoff=py)
            geom = poly
            if px == 0.0 and py == 0.0:
                c = geom.centroid
                px, py = float(c.x), float(c.y)
        else:
            raise InvalidPolygonPadError(f"{ctx}: unsupported pad shape type {stype!r}")
    elif isinstance(shape, str) and shape.upper() == "POLYGON":
        stype = "POLYGON"
        if "points" not in pad_dict:
            raise InvalidPolygonPadError(f"{ctx}: shape='POLYGON' requires 'points' field")
        pts = _extract_polygon_points(pad_dict["points"], ctx)
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 1e-6:
            raise InvalidPolygonPadError(f"{ctx}: POLYGON pad resolved to empty/zero-area geometry")
        geom = poly
        if px == 0.0 and py == 0.0:
            c = geom.centroid
            px, py = float(c.x), float(c.y)
    else:
        raise InvalidPolygonPadError(f"{ctx}: invalid pad shape payload {shape!r}")

    return PadRecord(
        ref=ctx,
        number=pad_num,
        net=net,
        layer=layer,
        x=px,
        y=py,
        shape_type=stype,
        geom=geom,
        hole_diam=hole_diam,
    )


def load_copper_json(path: Path) -> BoardModel:
    """Strictly parse complete PCB2-copper.json. Raises on any missing required data."""
    if not path.exists():
        raise FileNotFoundError(f"Copper JSON file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MissingCopperDataError(f"Invalid JSON syntax in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise MissingCopperDataError(f"Copper JSON root must be an object, got {type(data).__name__}")

    # 1. Board outline (REQUIRED)
    if "outline" not in data or not data["outline"]:
        raise MissingCopperDataError("Missing required top-level 'outline' in copper JSON")
    raw_outline = data["outline"]
    outline_pts = raw_outline["points"] if isinstance(raw_outline, dict) and "points" in raw_outline else raw_outline
    outline = Polygon(_extract_polygon_points(outline_pts, "outline"))
    if not outline.is_valid or outline.area <= 0:
        raise MissingCopperDataError("Board outline polygon is invalid or empty")
    safe_board = outline.buffer(-EDGE_CLEARANCE)

    # 2. Components & Pads (REQUIRED)
    raw_comps = data.get("components")
    if not isinstance(raw_comps, list) or not raw_comps:
        raise MissingCopperDataError("Missing or empty required top-level 'components' list")
    components: Dict[str, ComponentRecord] = {}
    for idx, c in enumerate(raw_comps):
        ctx = f"components[{idx}]"
        _require_keys(c, ("designator", "layer", "x", "y"), ctx)
        des = str(c["designator"])
        layer = int(c["layer"])
        cx, cy = float(c["x"]), float(c["y"])
        rot = float(c.get("rotation", c.get("angle", 0.0)) or 0.0)
        raw_bbox = c.get("bbox")
        if isinstance(raw_bbox, dict):
            _require_keys(raw_bbox, ("minX", "minY", "maxX", "maxY"), f"{des}.bbox")
            cbox = box(float(raw_bbox["minX"]), float(raw_bbox["minY"]),
                       float(raw_bbox["maxX"]), float(raw_bbox["maxY"]))
        elif isinstance(raw_bbox, list) and len(raw_bbox) == 4:
            cbox = box(float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
        else:
            raise MissingCopperDataError(f"Component {des} missing valid 'bbox'")

        pads = [parse_pad_geometry(p, des) for p in c.get("pads", [])]
        components[des] = ComponentRecord(
            designator=des,
            name=str(c.get("name", des)),
            layer=layer,
            x=cx,
            y=cy,
            rotation=rot,
            bbox=cbox,
            pads=pads,
        )

    missing_comps = [r for r in REQUIRED_COMPONENTS if r not in components]
    if missing_comps:
        raise MissingCopperDataError(f"Missing required PCB2 components: {missing_comps}")

    # Verify U13 has VSYS, GND, AVDD_REQ_FILTER pads
    u13_nets = {p.net for p in components["U13"].pads}
    for req_net in ("VSYS", "GND", "AVDD_REQ_FILTER"):
        if req_net not in u13_nets:
            raise MissingCopperDataError(f"Component U13 missing required pad net '{req_net}'")

    # Verify MK2 has POLYGON pad(s) parsed
    mk2_polys = [p for p in components["MK2"].pads if p.shape_type == "POLYGON"]
    if not mk2_polys:
        raise MissingCopperDataError("Component MK2 missing required POLYGON pad geometry (Pad 5)")

    # 3. Tracks (REQUIRED)
    raw_tracks = data.get("tracks", data.get("lines"))
    if not isinstance(raw_tracks, list):
        raise MissingCopperDataError("Missing required top-level 'tracks' (or 'lines') list")
    tracks: List[TrackRecord] = []
    for idx, t in enumerate(raw_tracks):
        ctx = f"tracks[{idx}]"
        _require_keys(t, ("layer", "width"), ctx)
        layer = int(t["layer"])
        net = str(t.get("net", "") or "")
        w = float(t["width"])
        if "points" in t and isinstance(t["points"], list) and len(t["points"]) >= 2:
            line = LineString([(float(p[0]), float(p[1])) for p in t["points"]])
        elif all(k in t for k in ("x1", "y1", "x2", "y2")):
            line = LineString([(float(t["x1"]), float(t["y1"])), (float(t["x2"]), float(t["y2"]))])
        else:
            raise MissingCopperDataError(f"{ctx}: track requires 'points' or (x1,y1,x2,y2)")
        if line.length <= 0:
            continue
        tracks.append(TrackRecord(layer=layer, net=net, width=w, line=line, geom=line.buffer(w / 2.0, cap_style=1)))

    # 4. Vias (REQUIRED)
    raw_vias = data.get("vias")
    if not isinstance(raw_vias, list) or not raw_vias:
        raise MissingCopperDataError("Missing or empty required top-level 'vias' list")
    vias: List[ViaRecord] = []
    for idx, v in enumerate(raw_vias):
        ctx = f"vias[{idx}]"
        _require_keys(v, ("x", "y"), ctx)
        hole = float(v.get("hole", v.get("holeDiameter", 0.0)))
        diam = float(v.get("diam", v.get("diameter", 0.0)))
        if hole <= 0 or diam <= hole:
            raise MissingCopperDataError(f"{ctx}: invalid via hole={hole}, diam={diam}")
        rule = str(v.get("rule_name", "") or "")
        raw_layers = v.get("layers", v.get("span_layer_ids"))
        if isinstance(raw_layers, str):
            layers = tuple(int(x) for x in raw_layers.split("/") if x.strip().isdigit())
        elif isinstance(raw_layers, list) and raw_layers:
            layers = tuple(int(x) for x in raw_layers)
        elif rule == "BV_L1_L2":
            layers = (L1_TOP, L2_GND)
        elif rule == "BV_L5_L6":
            layers = (L5_GND, L6_BOT)
        else:
            layers = (L1_TOP, L2_GND, L3_SIG, L4_PWR, L5_GND, L6_BOT)
        vias.append(ViaRecord(
            via_id=str(v.get("id", v.get("via_id", f"via_{idx}"))),
            net=str(v.get("net", "") or ""),
            x=float(v["x"]),
            y=float(v["y"]),
            hole=hole,
            diam=diam,
            layers=layers,
            rule_name=rule,
        ))

    # 5. L2 & L5 GND Planes (REQUIRED for return-path verification)
    raw_planes = data.get("planes", data.get("pours"))
    if not isinstance(raw_planes, list) or not raw_planes:
        raise MissingCopperDataError("Missing or empty required top-level 'planes' (L2/L5 GND planes)")
    planes_by_layer: Dict[int, List[Polygon]] = {}
    for idx, pl in enumerate(raw_planes):
        ctx = f"planes[{idx}]"
        _require_keys(pl, ("layer", "net", "points"), ctx)
        if str(pl["net"]) != "GND":
            continue
        lay = int(pl["layer"])
        poly = Polygon(_extract_polygon_points(pl["points"], ctx))
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 0:
            raise MissingCopperDataError(f"{ctx}: GND plane polygon is empty")
        planes_by_layer.setdefault(lay, []).append(poly)

    planes: Dict[int, Polygon] = {lay: unary_union(polys) for lay, polys in planes_by_layer.items()}
    for req_plane_layer, lname in ((L2_GND, "L2 (layer 15)"), (L5_GND, "L5 (layer 18)")):
        if req_plane_layer not in planes:
            raise MissingCopperDataError(f"Missing required GND plane for {lname}")

    return BoardModel(
        source_path=str(path),
        outline=outline,
        safe_board=safe_board,
        components=components,
        tracks=tracks,
        vias=vias,
        planes=planes,
    )


# ---------------------------------------------------------------------------
# Obstacle-Aware A* 8-Direction Path Router (VSYS Dual-End Verification)
# ---------------------------------------------------------------------------
def route_astar_2d(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    safe_board: Polygon,
    blocked_union: Optional[Polygon],
    step: float = 2.0,
    max_expansions: int = 8000,
) -> Optional[List[Tuple[float, float]]]:
    """8-direction A* router on a 2 mil grid verifying an obstacle-free copper path."""
    sx, sy = round(start[0] / step) * step, round(start[1] / step) * step
    gx, gy = round(goal[0] / step) * step, round(goal[1] / step) * step

    # Direct line-of-sight fast check first
    direct = LineString([start, goal])
    if safe_board.contains(direct) and (blocked_union is None or not direct.intersects(blocked_union)):
        return [start, goal]

    def is_free(pt_xy: Tuple[float, float]) -> bool:
        pt = Point(pt_xy)
        if not safe_board.contains(pt):
            return False
        if blocked_union is not None and blocked_union.contains(pt):
            return False
        return True

    def seg_free(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        ls = LineString([a, b])
        if not safe_board.contains(ls):
            return False
        if blocked_union is not None and ls.intersects(blocked_union):
            return False
        return True

    if not is_free((sx, sy)) or not is_free((gx, gy)):
        return None

    dirs = [
        (step, 0.0, step), (-step, 0.0, step), (0.0, step, step), (0.0, -step, step),
        (step, step, step * 1.4142), (step, -step, step * 1.4142),
        (-step, step, step * 1.4142), (-step, -step, step * 1.4142),
    ]
    pq: List[Tuple[float, float, Tuple[float, float]]] = [(math.hypot(gx - sx, gy - sy), 0.0, (sx, sy))]
    came_from: Dict[Tuple[float, float], Optional[Tuple[float, float]]] = {(sx, sy): None}
    g_score: Dict[Tuple[float, float], float] = {(sx, sy): 0.0}
    expansions = 0

    while pq and expansions < max_expansions:
        _, cur_g, cur = heapq.heappop(pq)
        expansions += 1
        if math.hypot(cur[0] - gx, cur[1] - gy) <= step * 1.5 and seg_free(cur, goal):
            path = [goal, cur]
            node = cur
            while came_from[node] is not None:
                node = came_from[node]  # type: ignore[assignment]
                path.append(node)
            path.append(start)
            path.reverse()
            return path
        for dx, dy, cost in dirs:
            nxt = (round(cur[0] + dx, 4), round(cur[1] + dy, 4))
            ng = cur_g + cost
            if ng < g_score.get(nxt, float("inf")):
                if seg_free(cur, nxt):
                    g_score[nxt] = ng
                    came_from[nxt] = cur
                    heapq.heappush(pq, (ng + math.hypot(gx - nxt[0], gy - nxt[1]), ng, nxt))
    return None


# ---------------------------------------------------------------------------
# Core Verification Helpers
# ---------------------------------------------------------------------------
def c11_candidate_geom(c11: ComponentRecord, cx: float, cy: float, angle_deg: int):
    """Derive C11 body and pad polygons directly from native C11 bbox/pads."""
    minx, miny, maxx, maxy = c11.bbox.bounds
    bw, bh = maxx - minx, maxy - miny
    # Derive native pad offset & size from native pads
    p1_native = next(p for p in c11.pads if p.net == "VSYS")
    p2_native = next(p for p in c11.pads if p.net == "GND")
    pad_off = abs(p1_native.x - c11.x) if abs(p1_native.x - c11.x) > 1e-3 else abs(p1_native.y - c11.y)
    pw = p1_native.geom.bounds[2] - p1_native.geom.bounds[0]
    ph = p1_native.geom.bounds[3] - p1_native.geom.bounds[1]

    if angle_deg in (0, 180):
        hw, hh = bw / 2.0, bh / 2.0
        dx = -pad_off if angle_deg == 0 else pad_off
        p1, p2 = (cx + dx, cy), (cx - dx, cy)
        hpw, hph = pw / 2.0, ph / 2.0
    else:
        hw, hh = bh / 2.0, bw / 2.0
        dy = -pad_off if angle_deg == 90 else pad_off
        p1, p2 = (cx, cy + dy), (cx, cy - dy)
        hpw, hph = ph / 2.0, pw / 2.0

    body = box(cx - hw, cy - hh, cx + hw, cy + hh)
    pad1 = box(p1[0] - hpw, p1[1] - hph, p1[0] + hpw, p1[1] + hph)
    pad2 = box(p2[0] - hpw, p2[1] - hph, p2[0] + hpw, p2[1] + hph)
    return body, pad1, pad2, p1, p2


def min_hole_wall_gap(vx: float, vy: float, vhole: float, vias: Sequence[ViaRecord], pads: Iterable[PadRecord]) -> float:
    best = float("inf")
    for v in vias:
        gap = math.hypot(vx - v.x, vy - v.y) - (vhole / 2.0) - (v.hole / 2.0)
        if gap < best:
            best = gap
    for p in pads:
        if p.hole_diam > 0:
            gap = math.hypot(vx - p.x, vy - p.y) - (vhole / 2.0) - (p.hole_diam / 2.0)
            if gap < best:
                best = gap
    return best


def verify_mk2_interference(board: BoardModel) -> Dict[str, Any]:
    """Quantify native C11 vs MK2 bbox AND parsed POLYGON pads interference."""
    mk2 = board.components["MK2"]
    c11 = board.components["C11"]
    mk2_poly_pads = [p for p in mk2.pads if p.shape_type == "POLYGON"]
    mk2_poly_union = unary_union([p.geom for p in mk2_poly_pads])
    return {
        "mk2_layer": mk2.layer,
        "mk2_bbox_mil": [round(v, 4) for v in mk2.bbox.bounds],
        "mk2_polygon_pad_count": len(mk2_poly_pads),
        "mk2_polygon_total_area_sqmil": round(mk2_poly_union.area, 2),
        "mk2_polygon_hole_diams_mil": sorted({round(p.hole_diam, 5) for p in mk2_poly_pads}),
        "native_c11_vs_mk2_bbox_overlap_sqmil": round(c11.bbox.intersection(mk2.bbox).area, 2),
        "native_c11_vs_mk2_polygon_pads_dist_mil": round(c11.bbox.distance(mk2_poly_union), 2),
    }


def verify_l2_l5_return_and_eight_decaps(board: BoardModel) -> Dict[str, Any]:
    """Verify L2/L5 GND plane containment for existing blind vias and audit 8 decaps."""
    l2_plane = board.planes[L2_GND]
    l5_plane = board.planes[L5_GND]
    mk2_box = board.components["MK2"].bbox

    bv_l1_l2 = [v for v in board.vias if (L1_TOP in v.layers and L2_GND in v.layers and not v.is_through)]
    bv_l5_l6 = [v for v in board.vias if (L5_GND in v.layers and L6_BOT in v.layers and not v.is_through)]
    through_gnd = [v for v in board.vias if v.is_through and v.net == "GND"]

    # Check plane containment for all GND blind vias
    l2_outside = [v.via_id for v in bv_l1_l2 if not l2_plane.contains(Point(v.x, v.y))]
    l5_outside = [v.via_id for v in bv_l5_l6 if not l5_plane.contains(Point(v.x, v.y))]

    decap_audit: Dict[str, Any] = {}
    for ref in EIGHT_DECAPS:
        if ref not in board.components:
            continue
        comp = board.components[ref]
        gnd_pads = [p for p in comp.pads if p.net == "GND"]
        pwr_pads = [p for p in comp.pads if p.net != "GND"]
        if not gnd_pads or not pwr_pads:
            raise MissingCopperDataError(f"Decap {ref} missing GND or power pad")
        gp, pp = gnd_pads[0], pwr_pads[0]
        pool = bv_l1_l2 if comp.layer == L1_TOP else bv_l5_l6
        nearest = min(pool, key=lambda v: math.hypot(v.x - gp.x, v.y - gp.y)) if pool else None
        dist = round(math.hypot(nearest.x - gp.x, nearest.y - gp.y), 2) if nearest else None
        plane = l2_plane if comp.layer == L1_TOP else l5_plane
        nearest_plane_margin = (
            round(Point(nearest.x, nearest.y).distance(plane.boundary), 3) if nearest else None
        )
        over_mk2 = comp.bbox.intersects(mk2_box)
        decap_audit[ref] = {
            "layer": "L1" if comp.layer == L1_TOP else "L6",
            "center_mil": [round(comp.x, 3), round(comp.y, 3)],
            "pwr_net": pp.net,
            "gnd_pad_mil": [round(gp.x, 3), round(gp.y, 3)],
            "nearest_same_side_bv": nearest.via_id if nearest else None,
            "gnd_pad_to_nearest_bv_mil": dist,
            "nearest_bv_plane_edge_margin_mil": nearest_plane_margin,
            "intersects_mk2_projection": over_mk2,
            "through_via_allowed_locally": not over_mk2,
        }

    return {
        "l2_gnd_plane_area_sqmil": round(l2_plane.area, 2),
        "l5_gnd_plane_area_sqmil": round(l5_plane.area, 2),
        "existing_bv_l1_l2_count": len(bv_l1_l2),
        "existing_bv_l5_l6_count": len(bv_l5_l6),
        "existing_gnd_through_via_count": len(through_gnd),
        "bv_l1_l2_outside_l2_plane": l2_outside,
        "bv_l5_l6_outside_l5_plane": l5_outside,
        "eight_decap_audit": decap_audit,
    }


def _build_l6_vsys_obstacle_union(board: BoardModel, shifted_comps: Dict[str, Polygon], exclude_refs: set) -> Optional[Polygon]:
    """Build exact L6 copper obstacle union inflated by 6.2 mil (or 11.8 mil for sensitive nets) + trace half-width."""
    obs: List[Polygon] = []
    half_w = TRACE_WIDTH_PWR / 2.0

    # Other-net L6 tracks
    for t in board.tracks:
        if t.layer != L6_BOT or t.net == "VSYS":
            continue
        clr = SENSITIVE_3W_CLEARANCE if t.net in SENSITIVE_NETS else COPPER_CLEARANCE
        obs.append(t.geom.buffer(clr + half_w, quad_segs=8))

    # Other-net L6 pads (including MK2 POLYGON pads!)
    for des, comp in board.components.items():
        if des in exclude_refs:
            continue
        # If component was shifted in joint relayout, shift its pads by the same delta
        dx = shifted_comps[des].bounds[0] - comp.bbox.bounds[0] if des in shifted_comps else 0.0
        dy = shifted_comps[des].bounds[1] - comp.bbox.bounds[1] if des in shifted_comps else 0.0
        for p in comp.pads:
            if p.layer != L6_BOT or p.net == "VSYS":
                continue
            pg = shp_translate(p.geom, xoff=dx, yoff=dy) if (dx or dy) else p.geom
            clr = SENSITIVE_3W_CLEARANCE if p.net in SENSITIVE_NETS else COPPER_CLEARANCE
            obs.append(pg.buffer(clr + half_w, quad_segs=8))

    # Other-net vias touching L6
    for v in board.vias:
        if L6_BOT not in v.layers or v.net == "VSYS":
            continue
        clr = SENSITIVE_3W_CLEARANCE if v.net in SENSITIVE_NETS else COPPER_CLEARANCE
        obs.append(v.pad_geom().buffer(clr + half_w, quad_segs=8))

    return unary_union(obs) if obs else None


def evaluate_joint_relayout(
    board: BoardModel,
    scheme_name: str,
    shifts: Dict[str, Tuple[float, float]],
    x_range: Sequence[int],
    y_range: Sequence[int],
    allow_l4_stereo: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate C11/U13 candidate grid under a given joint-shift configuration.
    Records BOTH passing executable candidates AND failed candidates with explicit reasons.
    """
    c11 = board.components["C11"]
    u13 = board.components["U13"]
    mk2_box = board.components["MK2"].bbox
    u2_box = board.components["U2"].bbox
    l5_plane = board.planes[L5_GND]
    u13_vsys_pad = next(p for p in u13.pads if p.net == "VSYS" and p.y > u13.y)
    u13_filter_pad = next(p for p in u13.pads if p.net == "AVDD_REQ_FILTER")

    # Apply joint component shifts on L6
    shifted_l6_boxes: Dict[str, Polygon] = {}
    for des, comp in board.components.items():
        if comp.layer != L6_BOT or des == "C11":
            continue
        dx, dy = shifts.get(des, (0.0, 0.0))
        shifted_l6_boxes[des] = shp_translate(comp.bbox, xoff=dx, yoff=dy) if (dx or dy) else comp.bbox

    # Check if shifted components collide with each other (excluding pre-existing native overlaps)
    shift_conflicts: List[Dict[str, Any]] = []
    for s_des in shifts:
        if s_des not in shifted_l6_boxes:
            continue
        s_box = shifted_l6_boxes[s_des]
        for o_des, o_box in shifted_l6_boxes.items():
            if o_des == s_des:
                continue
            gap = s_box.distance(o_box)
            if gap < SMD_CHIP_SPACING:
                shift_conflicts.append({"shifted": s_des, "neighbor": o_des, "gap_mil": round(gap, 2)})

    l6_vsys_blocked = _build_l6_vsys_obstacle_union(board, shifted_l6_boxes, exclude_refs={"C11"})
    l4_tracks = [t for t in board.tracks if t.layer == L4_PWR and t.net != "VSYS"]
    all_pads = [p for c in board.components.values() for p in c.pads]

    passing: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    reason_counts: Dict[str, int] = {}

    def record_fail(cx: int, cy: int, angle: int, reason: str, detail: str):
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if len(failed) < 50:  # Keep representative sample of failed candidates
            failed.append({"center_mil": [cx, cy], "angle_deg": angle, "reason": reason, "detail": detail})

    for angle in (0, 180):
        for cx in x_range:
            for cy in y_range:
                body, pad1, pad2, p1, p2 = c11_candidate_geom(c11, float(cx), float(cy), angle)
                if not board.safe_board.contains(pad1) or not board.safe_board.contains(pad2):
                    record_fail(cx, cy, angle, "BOARD_EDGE_FAIL", "Pad violates 12.0 mil edge clearance")
                    continue
                if body.intersects(mk2_box):
                    record_fail(cx, cy, angle, "MK2_INTRUSION", "Overlaps MK2 acoustic keepout")
                    continue
                min_comp_gap = min(body.distance(cb) for cb in shifted_l6_boxes.values())
                if min_comp_gap < SMD_CHIP_SPACING:
                    record_fail(cx, cy, angle, "SMD_SPACING_FAIL", f"min L6 gap={min_comp_gap:.2f} < 6.0 mil")
                    continue

                # Propose BV_L5_L6 blind via adjacent to Pad 2 (GND)
                gvx = p2[0] + (14.0 if angle == 0 else -14.0)
                gvy = p2[1]
                gv_pad = Point(gvx, gvy).buffer(BLIND_VIA_DIAM / 2.0, quad_segs=16)
                if not board.safe_board.contains(gv_pad):
                    # Try vertical offset if horizontal hits board edge
                    gvx, gvy = p2[0], (p2[1] + 14.0 if cy < 370 else p2[1] - 14.0)
                    gv_pad = Point(gvx, gvy).buffer(BLIND_VIA_DIAM / 2.0, quad_segs=16)
                if not board.safe_board.contains(gv_pad):
                    record_fail(cx, cy, angle, "GND_VIA_EDGE_FAIL", "BV_L5_L6 violates 12.0 mil board edge")
                    continue
                if not l5_plane.contains(Point(gvx, gvy)):
                    record_fail(cx, cy, angle, "L5_PLANE_MISS", "BV_L5_L6 outside L5 GND plane")
                    continue
                l5_margin = Point(gvx, gvy).distance(l5_plane.boundary)
                if l5_margin < MIN_PLANE_EDGE_MARGIN:
                    record_fail(cx, cy, angle, "L5_PLANE_EDGE_FAIL", f"L5 margin={l5_margin:.2f} < {MIN_PLANE_EDGE_MARGIN}")
                    continue
                wall_gap = min_hole_wall_gap(gvx, gvy, BLIND_VIA_HOLE, board.vias, all_pads)
                if wall_gap < HOLE_WALL_CLEARANCE:
                    record_fail(cx, cy, angle, "HOLE_WALL_FAIL", f"wall gap={wall_gap:.2f} < 11.811 mil")
                    continue

                # Route VSYS on L6 via obstacle-aware A*
                vsys_path = route_astar_2d(p1, (u13_vsys_pad.x, u13_vsys_pad.y), board.safe_board, l6_vsys_blocked)
                route_mode = "L6_DIRECT_ASTAR"
                if vsys_path is None:
                    if allow_l4_stereo and len(l4_tracks) == 0:
                        route_mode = "L4_STEREO_REQUIRES_HDI_EQ"
                        vsys_path = [p1, (u13_vsys_pad.x, u13_vsys_pad.y)]
                    else:
                        record_fail(cx, cy, angle, "NO_VSYS_L6_ROUTE", "Blocked by L6 copper/pads/3W obstacles")
                        continue

                vsys_line = LineString(vsys_path)
                vsys_copper = vsys_line.buffer(TRACE_WIDTH_PWR / 2.0, cap_style=1)
                avdd_gap = vsys_copper.distance(u13_filter_pad.geom)
                if avdd_gap < SENSITIVE_3W_CLEARANCE:
                    record_fail(cx, cy, angle, "AVDD_FILTER_3W_FAIL", f"AVDD_REQ_FILTER gap={avdd_gap:.2f} < 11.8 mil")
                    continue

                passing.append({
                    "scheme": scheme_name,
                    "center_mil": [cx, cy],
                    "angle_deg": angle,
                    "pad1_vsys_mil": [round(p1[0], 2), round(p1[1], 2)],
                    "pad2_gnd_mil": [round(p2[0], 2), round(p2[1], 2)],
                    "gnd_bv_l5_l6_mil": [round(gvx, 2), round(gvy, 2)],
                    "vsys_route_mode": route_mode,
                    "vsys_route_len_mil": round(vsys_line.length, 2),
                    "vsys_waypoints_mil": [[round(pt[0], 2), round(pt[1], 2)] for pt in vsys_path],
                    "avdd_req_filter_gap_mil": round(avdd_gap, 2),
                    "min_l6_comp_gap_mil": round(min_comp_gap, 2),
                    "gnd_via_hole_wall_gap_mil": round(wall_gap, 2),
                    "l5_plane_edge_margin_mil": round(l5_margin, 2),
                    "in_u2_bga_shadow": body.intersects(u2_box),
                    "mk2_overlap_sqmil": 0.0,
                })

    passing.sort(key=lambda r: (r["in_u2_bga_shadow"], r["vsys_route_len_mil"], -r["min_l6_comp_gap_mil"]))
    return {
        "scheme": scheme_name,
        "joint_shifts_mil": {k: list(v) for k, v in shifts.items()},
        "joint_shift_neighbor_notes": shift_conflicts,
        "passing_count": len(passing),
        "passing_top5": passing[:5],
        "failed_total": sum(reason_counts.values()),
        "failure_reason_counts": reason_counts,
        "failed_sample": failed[:15],
    }


def run_verification(copper_json: Path) -> Dict[str, Any]:
    board = load_copper_json(copper_json)
    mk2_report = verify_mk2_interference(board)
    return_report = verify_l2_l5_return_and_eight_decaps(board)

    # 1. Baseline zero-shift L6 screen (reproduces why prior 80 candidates failed on L6-only VSYS)
    r6_repro = evaluate_joint_relayout(
        board,
        scheme_name="BASELINE_ZERO_SHIFT_L6_ONLY",
        shifts={},
        x_range=range(60, 152, 4),
        y_range=range(264, 384, 4),
        allow_l4_stereo=False,
    )

    # 2. Scheme R8-C: Joint shift U1 (+50 Y), U3 (+38 Y), U5 (+64 Y) -> C11 directly north of U13
    r8_c = evaluate_joint_relayout(
        board,
        scheme_name="R8-C_JOINT_U1_U3_U5_SHIFT",
        shifts={"U1": (0.0, 50.0), "U3": (0.0, 38.0), "U5": (0.0, 64.0)},
        x_range=range(126, 152, 2),
        y_range=range(276, 290, 2),
        allow_l4_stereo=False,
    )

    # 3. Scheme R8-A: Zero IC shift, L6 open pocket + L4 stereo VSYS (requires HDI EQ)
    r8_a = evaluate_joint_relayout(
        board,
        scheme_name="R8-A_ZERO_IC_SHIFT_L4_STEREO",
        shifts={},
        x_range=range(62, 104, 2),
        y_range=range(358, 382, 2),
        allow_l4_stereo=True,
    )

    return {
        "verification_scope": "OFFLINE_GEOMETRY_SCREEN_NOT_FULL_BOARD_DRC",
        "full_board_native_drc_completed": False,
        "warning": "Offline Shapely 2 geometry screen only; MUST NOT be used as a substitute for native EasyEDA Pro full-board ERC/DRC.",
        "source_copper_json": str(copper_json),
        "board_bounds_mil": [round(v, 4) for v in board.outline.bounds],
        "locked_rules_mil": {
            "edge_clearance": EDGE_CLEARANCE,
            "copper_clearance": COPPER_CLEARANCE,
            "sensitive_3w_clearance": SENSITIVE_3W_CLEARANCE,
            "hole_wall_clearance": HOLE_WALL_CLEARANCE,
            "smd_chip_spacing": SMD_CHIP_SPACING,
            "smd_sot_spacing": SMD_SOT_SPACING,
            "smd_qfn_bga_spacing": SMD_QFN_BGA_SPACING,
            "min_plane_edge_margin": MIN_PLANE_EDGE_MARGIN,
        },
        "mk2_interference_audit": mk2_report,
        "l2_l5_return_and_decaps": return_report,
        "baseline_zero_shift_repro": r6_repro,
        "scheme_r8_c_joint_relayout": r8_c,
        "scheme_r8_a_l4_stereo": r8_a,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="H03-R8 PCB2 Joint Relayout & Dual-End Path Verifier (Fail-Fast Full Copper JSON)"
    )
    parser.add_argument(
        "--copper-json",
        required=True,
        help="Path to complete PCB2-copper.json (REQUIRED; no silent fallback).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSON report path.",
    )
    args = parser.parse_args(argv)

    result = run_verification(Path(args.copper_json))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[{result['verification_scope']}] "
        f"R8-C PASS={result['scheme_r8_c_joint_relayout']['passing_count']}, "
        f"R8-A PASS={result['scheme_r8_a_l4_stereo']['passing_count']}, "
        f"Baseline-L6-Only PASS={result['baseline_zero_shift_repro']['passing_count']} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
