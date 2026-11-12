"""Nominal component envelopes in mm, top mounting plane z=0; OCCT via cadquery-ocp."""
from pathlib import Path
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone


def box(x, y, z, width, depth, height):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), width, depth, height).Shape()


def cylinder(x, y, z, radius, height):
    axis = gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1))
    return BRepPrimAPI_MakeCylinder(axis, radius, height).Shape()


def save(name, solid, *additional):
    for part in additional:
        solid = BRepAlgoAPI_Fuse(solid, part).Shape()
    writer = STEPControl_Writer()
    assert writer.Transfer(solid, STEPControl_AsIs) == IFSelect_RetDone
    assert writer.Write(str(Path(__file__).with_name(name + ".step"))) == IFSelect_RetDone


if __name__ == "__main__":
    # M20-9990245, the second pin points toward -Y in the local 3-D frame.
    save("Header_1x02", box(-1.27,-3.81,0,2.54,5.08,2.54),
         box(-0.32,-0.32,-3,0.64,0.64,11.64), box(-0.32,-2.86,-3,0.64,0.64,11.64))
    # Component envelope only; leads trimmed to 3 mm. Diffuser is approximated.
    save("LED_3mm", cylinder(1.27,0,0,1.6,0.7), cylinder(1.27,0,0.65,1.45,2.5),
         BRepPrimAPI_MakeSphere(gp_Pnt(1.27,0,3.15),1.45).Shape(),
         box(-0.225,-0.225,-3,0.45,0.45,3.3),box(2.315,-0.225,-3,0.45,0.45,3.3))
    # Shared 0805 envelope; height is an allowance, not a package inspection dimension.
    save("Chip_0805", box(-1,-0.625,0,2,1.25,1.35))
