"""Build H04 bench tooling in millimetres. Requires numpy and manifold3d 3.5.4."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import manifold3d as m
import numpy as np

HERE = Path(__file__).resolve().parent
M3_CLEARANCE = 3.5
DECK = 4.0


def box(x, y, z, dx, dy, dz):
    return m.Manifold.cube((dx, dy, dz)).translate((x, y, z))


def cylinder(x, y, z, diameter, height):
    return m.Manifold.cylinder(height, diameter / 2, circular_segments=36).translate((x, y, z))


def slot(x0, y0, x1, y1, diameter=M3_CLEARANCE):
    return m.Manifold.batch_hull([cylinder(x, y, -1, diameter, 7) for x, y in ((x0,y0),(x1,y1))])


def join(parts):
    return m.Manifold.batch_boolean(parts, m.OpType.Add)


def subtract(part, cuts):
    return m.Manifold.batch_boolean([part, *cuts], m.OpType.Subtract)


def base():
    # Two transverse beams and longitudinal tracks form a single open deck.
    beams = [box(-84, y, 0, 168, width, DECK) for y, width in ((-8, 16), (48, 22))]
    cuts = [cylinder(x, 0, -1, M3_CLEARANCE, 7) for x in (-10, 10)]
    for sign in (-1, 1):
        beams.append(box(sign * 79 - 5, 0, 0, 10, 52, DECK))
        for x in (sign * 22, sign * 42):
            beams.append(box(x - 5, 0, 0, 10, 52, DECK))
            cuts.append(slot(x, 14, x, 39))
        for y in (52, 66):
            cuts.append(slot(sign * 55, y, sign * 76, y))
    return subtract(join(beams), cuts)


def bridge(p):
    height = p['bridge_height_mm']
    foot = box(-15, -5, 0, 30, 10, 3)
    ridge = m.Manifold.batch_hull([
        box(-6, -3, 2, 12, 6, 1), box(-2, -2, height - 1, 4, 4, 1)
    ])
    return subtract(foot + ridge, [cylinder(x, 0, -1, M3_CLEARANCE, 6) for x in (-10, 10)])


def temple(p):
    # Padded flat seat; slack temporary strap can pass across the full arm.
    height = p['temple_height_mm']
    foot = box(-6, -11, 0, 12, 22, 3)
    post = box(-3.5, -3, 2, 7, 6, height-2)
    seat = box(-7, -3, height-1.6, 14, 6, 1.6)
    return subtract(join([foot, post, seat]), [cylinder(0, y, -1, M3_CLEARANCE, 6) for y in (-7,7)])


def pupil_mask(p):
    # Local origin at the eye-facing surface of the mask, z=deck top.
    pitch, diameter, h = p['mask_pitch_mm'], p['mask_hole_diameter_mm'], p['mask_center_height_mm']
    if not 0 < diameter < pitch or 3*pitch+diameter/2 > 14 or h-2*pitch < 8:
        raise ValueError("Aperture grid does not fit mask")
    wall = box(-15, -1.2, 0, 30, 1.2, h+2*pitch+3)
    foot = box(-16, -1.2, 0, 32, 11.2, 3)
    cuts = [cylinder(x, 5, -1, M3_CLEARANCE, 6) for x in (-10,10)]
    for i in range(-3,4):
        for j in range(-2,3):
            aperture = m.Manifold.cylinder(4, diameter/2, circular_segments=36)
            cuts.append(aperture.rotate((90,0,0)).translate((i*pitch,1,h+j*pitch)))
    return subtract(wall + foot, cuts)


def pcb_tray(p):
    length, width = p['pcb_length_mm'], p['pcb_width_mm']
    gap, bearing = p['tray_side_clearance_mm'], p['tray_corner_bearing_mm']
    underside = p['tray_under_board_mm']
    if not (0 < gap < bearing <= 1 and length > 6 and width > 6 and underside >= 3 and p['pcb_thickness_mm'] > 0):
        raise ValueError("Tray clearances or corner bearing out of range")
    depth, rim = 2.0, 1.8
    x, y = length/2+gap, width/2+gap
    # Solid floor, four corner bearing pads, short open side fences. Through-pin tails clear the floor.
    floor = box(-x-rim, -y-rim, 0, 2*(x+rim), 2*(y+rim), depth)
    parts = [floor]
    for sx in (-1,1):
        for sy in (-1,1):
            cx, cy = sx*x, sy*y
            b = bearing+gap
            x0 = cx-b if sx > 0 else cx-rim
            y0 = cy-b if sy > 0 else cy-rim
            parts.append(box(x0, y0, depth-.2, b+rim, b+rim, underside+.2))
            # Only outside the PCB after reaching its bottom surface.
            fence_h = p['pcb_thickness_mm']+.2
            parts.append(box(cx if sx>0 else cx-rim, y0, depth+underside-.2, rim, b+rim, fence_h))
            parts.append(box(x0, cy if sy>0 else cy-rim, depth+underside-.2, b+rim, rim, fence_h))
    return join(parts)


def validate_and_export(name, solid, out):
    solid = solid.simplify(0.0001)  # remove coplanar seams before single-precision STL tessellation
    if solid.status() != m.Error.NoError or len(solid.decompose()) != 1 or solid.volume() <= 0:
        raise ValueError(f"{name}: expected one positive-volume solid")
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties[:, :3])
    tri = verts[mesh.tri_verts]
    # Check serialized vertices, including seam welding and edge winding.
    from collections import Counter
    edges = Counter()
    for a,b,c in tri:
        a,b,c = tuple(a),tuple(b),tuple(c)
        edges.update(((a,b),(b,c),(c,a)))
    if any(n != 1 or edges[v,u] != 1 for (u,v),n in edges.items()):
        raise ValueError(f"{name}: open or non-manifold STL edge")
    normals = np.cross(tri[:,1] - tri[:,0], tri[:,2] - tri[:,0])
    norms = np.linalg.norm(normals, axis=1)
    if np.min(norms) < 1e-8:
        raise ValueError(f"{name}: degenerate facet")
    path = out / (name + '.stl')
    with path.open('wb') as stream:
        stream.write(f'H04 Rev A | {name} | mm'.encode().ljust(80, b' '))
        stream.write(struct.pack('<I', len(tri)))
        for normal, triangle in zip(normals / norms[:,None], tri):
            stream.write(struct.pack('<12fH', *normal, *triangle.flatten(), 0))
    return {'triangles':len(tri), 'bbox_mm':[round(v,3) for v in solid.bounding_box()],
            'volume_mm3':round(solid.volume(),2), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def check_mating(parts, p):
    # Sweep both eyes, extreme arm widths and eye-mask slide end stops.
    for sign in (-1,1):
        for half_span in (55,76):
            for measure_y in (9,34):
                placed = [parts['deck'], parts['bridge'].translate((0,0,DECK)),
                          parts['pupil_mask'].translate((sign*32,measure_y,DECK))]
                placed.extend(parts['temple'].translate((side*half_span,59,DECK)) for side in (-1,1))
                for i, a in enumerate(placed):
                    if any((a ^ b).volume() > 1e-5 for b in placed[:i]):
                        raise ValueError("Fixture assembly collision")
    length, width = p['pcb_length_mm'], p['pcb_width_mm']
    pcb_bottom = 2 + p['tray_under_board_mm']
    board = box(-length/2,-width/2,pcb_bottom,length,width,p['pcb_thickness_mm'])
    # Based on CAM-RAIL-A J1/J2/J3 front-view footprint coordinates (y down).
    for x,y in ((2.5,4),(21.5,4),(7,3)):
        for dy in (0,2.54):
            board += box(-length/2+x-.5,width/2-y-dy-.5,pcb_bottom-3,1,1,3)
    if (board ^ parts['cam_rail_tray']).volume() > 1e-5:
        raise ValueError("PCB/through-pin envelope intersects tray")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params', type=Path, default=HERE/'design.json')
    parser.add_argument('--out', type=Path, default=HERE/'stl')
    args = parser.parse_args()
    p = json.loads(args.params.read_text(encoding='utf-8'))
    args.out.mkdir(parents=True, exist_ok=True)
    parts = {'deck':base(), 'bridge':bridge(p), 'temple':temple(p),
             'pupil_mask':pupil_mask(p), 'cam_rail_tray':pcb_tray(p)}
    check_mating(parts,p)
    report = {name:validate_and_export(name,solid,args.out) for name,solid in parts.items()}
    evidence = {'units':'mm', 'model_only':True, 'physical_test':'NOT_RUN',
                'clearance_check':'8 fixture endpoint configurations + bare PCB and six modeled pin tails',
                'meshes':report}
    (args.out/'geometry.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(f"{len(parts)} closed solids exported, CAD assembly checks passed")


if __name__ == '__main__':
    main()
