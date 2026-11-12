"""Read the manufacturer's opened-frame STL locally; report candidate fixture datums in mm."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def slice_rectangle(triangles, a, b, windows):
    """Clip mesh triangles to a rectangular prism, retaining surface coordinates."""
    axes = (a,b)
    candidates = np.ones(len(triangles),dtype=bool)
    for axis,(low,high) in zip(axes,windows):
        candidates &= ((triangles[:,:,axis].max(axis=1) >= low)
                       & (triangles[:,:,axis].min(axis=1) <= high))
    points = []
    for tri in triangles[candidates]:
        poly = list(tri)
        for axis,(low,high) in zip(axes,windows):
            for boundary,sign in ((low,1),(high,-1)):
                clipped = []
                for prev,next_vertex in zip(poly[-1:]+poly[:-1],poly):
                    p = sign*(prev[axis]-boundary)
                    q = sign*(next_vertex[axis]-boundary)
                    if (p < 0) != (q < 0):
                        clipped.append(prev + (next_vertex-prev)*(p/(p-q)))
                    if q >= 0:
                        clipped.append(next_vertex)
                poly = clipped
        points.extend(poly)
    if not points:
        raise ValueError("No triangles in the measurement window")
    return np.asarray(points)


def check(path):
    raw = path.read_bytes()
    ntri, = struct.unpack_from('<I',raw,80)
    if len(raw) != 84 + 50*ntri:
        raise ValueError('Expected complete binary STL')
    dtype = np.dtype([('normal','<3f'),('v','<9f'),('attr','<u2')])
    xyz = np.frombuffer(raw[84:],dtype=dtype)['v'].reshape(-1,3,3).astype(float)
    # Candidate mounting pose, millimetres. Z offset is set by the nose bridge.
    tri = xyz[:,:,[0,2,1]].copy()
    tri[:,:,0] -= 71.3
    tri[:,:,1] = 159.0 - tri[:,:,1]
    p = json.loads((HERE/'design.json').read_text(encoding='utf-8'))
    bridge = slice_rectangle(tri,0,1,((-2,2),(-2,2)))
    z_offset = p['bridge_height_mm'] - bridge[:,2].min()
    tri[:,:,2] += z_offset
    supports = []
    for x in (-65,65):
        pts = slice_rectangle(tri,0,1,((x-7,x+7),(56,62)))
        supports.append(round(float(pts[:,2].min()-p['temple_height_mm']),3))
    limits = []
    for x in (-32,32):
        pts = slice_rectangle(tri,0,2,((x-15,x+15),(0,p['mask_center_height_mm']+2*p['mask_pitch_mm']+3)))
        limits.append(round(float(pts[:,1].max()),3))
    return {'source':'https://docs.brilliant.xyz/halo/halo.stl',
            'sha256':hashlib.sha256(raw).hexdigest(),'triangles':ntri,
            'model_span_mm':[round(float(v),3) for v in np.ptp(xyz.reshape(-1,3),axis=0)],
            'transform_from_source_to_deck':{'X':'source X - 71.3','Y':'159.0 - source Z',
                                              'Z_add_to_source_Y_mm':round(float(z_offset),3)},
            'uncompressed_clearance_above_temple_seats_mm':supports,
            'max_Halo_Y_in_left_right_aperture_plate_slabs_mm':limits,
            'scope':'source mesh surface only, zero pitch and roll; no material compression or optical prediction'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stl',type=Path)
    print(json.dumps(check(parser.parse_args().stl),indent=2))
