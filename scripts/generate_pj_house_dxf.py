from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "cad" / "pj_dev_2story_house_full_A3_layouts_3d_A01-A11.dxf"

TH_COMPANY = "\u0e1a\u0e23\u0e34\u0e29\u0e31\u0e17 \u0e1e\u0e35 \u0e40\u0e08 \u0e40\u0e14\u0e1f \u0e08\u0e33\u0e01\u0e31\u0e14"
TH_PROJECT = "\u0e2d\u0e32\u0e04\u0e32\u0e23\u0e2d\u0e22\u0e39\u0e48\u0e2d\u0e32\u0e28\u0e31\u0e22 \u0e04\u0e2a\u0e25."
TH_PLAN = "\u0e41\u0e1a\u0e1a\u0e41\u0e1b\u0e25\u0e19\u0e1e\u0e37\u0e49\u0e19"
TH_COLUMN_NOTE = "\u0e41\u0e19\u0e27\u0e40\u0e2a\u0e32\u0e0a\u0e31\u0e49\u0e19 1 \u0e41\u0e25\u0e30\u0e0a\u0e31\u0e49\u0e19 2 \u0e15\u0e23\u0e07\u0e01\u0e31\u0e19"

LAYERS = {
    "A-GRID": {"color": 8, "lineweight": 13},
    "A-COLUMN": {"color": 7, "lineweight": 35},
    "A-WALL": {"color": 7, "lineweight": 30},
    "A-DOOR": {"color": 3, "lineweight": 13},
    "A-WINDOW": {"color": 4, "lineweight": 13},
    "A-STAIR": {"color": 6, "lineweight": 13},
    "A-FURN": {"color": 8, "lineweight": 13},
    "A-SANITARY": {"color": 5, "lineweight": 13},
    "A-DIMS": {"color": 2, "lineweight": 13},
    "A-TEXT": {"color": 7, "lineweight": 13},
    "A-ANNO": {"color": 1, "lineweight": 13},
    "A-ROOF": {"color": 8, "lineweight": 13},
    "A-TITLE": {"color": 7, "lineweight": 18},
    "A-HATCH": {"color": 9, "lineweight": 13},
    "3D-WALL": {"color": 7, "lineweight": 18},
    "3D-COLUMN": {"color": 8, "lineweight": 18},
    "3D-SLAB": {"color": 9, "lineweight": 18},
    "3D-ROOF": {"color": 1, "lineweight": 18},
    "3D-VIEW": {"color": 7, "lineweight": 13},
    "DEFPOINTS": {"color": 7, "lineweight": 0},
}


def setup_doc() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    doc.header["$INSUNITS"] = 6
    # TrueType is required for Thai text. SHX fonts such as txt.shx render Thai
    # as question marks in many CAD applications.
    doc.styles.new("PJ_STANDARD", dxfattribs={"font": "tahoma.ttf"})

    if "CENTER2" not in doc.linetypes:
        doc.linetypes.add(
            "CENTER2",
            pattern=[0.7, 0.35, -0.15, 0.08, -0.15],
            description="Center ____ _ ____ _",
        )
    if "DASHED2" not in doc.linetypes:
        doc.linetypes.add("DASHED2", pattern=[0.5, 0.3, -0.2], description="Dashed __ __ __")

    for name, attribs in LAYERS.items():
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs=attribs)
        else:
            layer = doc.layers.get(name)
            layer.color = attribs["color"]
            layer.dxf.lineweight = attribs["lineweight"]
    doc.layers.get("A-GRID").dxf.linetype = "CENTER2"
    doc.layers.get("A-ROOF").dxf.linetype = "DASHED2"
    return doc


def text(msp, value, point, height=0.22, layer="A-TEXT", align="LEFT", rotation=0):
    entity = msp.add_text(
        value,
        dxfattribs={
            "layer": layer,
            "height": height,
            "style": "PJ_STANDARD",
            "rotation": rotation,
        },
    )
    if align == "CENTER":
        entity.set_placement(point, align=TextEntityAlignment.MIDDLE_CENTER)
    elif align == "RIGHT":
        entity.set_placement(point, align=TextEntityAlignment.MIDDLE_RIGHT)
    else:
        entity.set_placement(point, align=TextEntityAlignment.LEFT)
    return entity


def line(msp, p1, p2, layer="A-WALL", linetype=None):
    attribs = {"layer": layer}
    if linetype:
        attribs["linetype"] = linetype
    return msp.add_line(p1, p2, dxfattribs=attribs)


def rect(msp, x1, y1, x2, y2, layer="A-WALL", linetype=None):
    line(msp, (x1, y1), (x2, y1), layer, linetype)
    line(msp, (x2, y1), (x2, y2), layer, linetype)
    line(msp, (x2, y2), (x1, y2), layer, linetype)
    line(msp, (x1, y2), (x1, y1), layer, linetype)


def circle(msp, center, radius, layer="A-GRID"):
    return msp.add_circle(center, radius, dxfattribs={"layer": layer})


def arc(msp, center, radius, start, end, layer="A-DOOR"):
    return msp.add_arc(center, radius, start, end, dxfattribs={"layer": layer})


def hatch_rect(msp, x1, y1, x2, y2, pattern="ANSI31", scale=0.08, color=9):
    hatch = msp.add_hatch(color=color, dxfattribs={"layer": "A-HATCH"})
    if pattern == "SOLID":
        hatch.set_solid_fill(color=color)
    else:
        hatch.set_pattern_fill(pattern, scale=scale)
    hatch.paths.add_polyline_path([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], is_closed=True)
    return hatch


def wall(msp, x1, y1, x2, y2, thickness=0.15):
    if abs(y2 - y1) < 1e-6:
        rect(msp, x1, y1 - thickness / 2, x2, y1 + thickness / 2, "A-WALL")
        hatch_rect(msp, x1, y1 - thickness / 2, x2, y1 + thickness / 2, "ANSI31", 0.05, 9)
    elif abs(x2 - x1) < 1e-6:
        rect(msp, x1 - thickness / 2, y1, x1 + thickness / 2, y2, "A-WALL")
        hatch_rect(msp, x1 - thickness / 2, y1, x1 + thickness / 2, y2, "ANSI31", 0.05, 9)
    else:
        line(msp, (x1, y1), (x2, y2), "A-WALL")


def dim_h(msp, x1, x2, y, label):
    line(msp, (x1, y), (x2, y), "A-DIMS")
    line(msp, (x1, y - 0.13), (x1, y + 0.13), "A-DIMS")
    line(msp, (x2, y - 0.13), (x2, y + 0.13), "A-DIMS")
    text(msp, label, ((x1 + x2) / 2, y + 0.16), 0.18, "A-DIMS", "CENTER")


def dim_v(msp, x, y1, y2, label):
    line(msp, (x, y1), (x, y2), "A-DIMS")
    line(msp, (x - 0.13, y1), (x + 0.13, y1), "A-DIMS")
    line(msp, (x - 0.13, y2), (x + 0.13, y2), "A-DIMS")
    text(msp, label, (x - 0.25, (y1 + y2) / 2), 0.18, "A-DIMS", "CENTER", 90)


def add_grid(msp, ox, oy):
    xs = [0, 2, 5, 8, 12, 14, 16]
    ys = [0, 2, 6, 10.5, 14]
    for x, label in zip(xs, "ABCDEFG"):
        line(msp, (ox + x, oy - 0.75), (ox + x, oy + 14.75), "A-GRID", "CENTER2")
        circle(msp, (ox + x, oy + 15.25), 0.25, "A-GRID")
        text(msp, label, (ox + x, oy + 15.25), 0.26, "A-GRID", "CENTER")
    for y, label in zip(ys, ["1", "2", "3", "4", "5"]):
        line(msp, (ox - 0.75, oy + y), (ox + 16.75, oy + y), "A-GRID", "CENTER2")
        circle(msp, (ox - 1.18, oy + y), 0.25, "A-GRID")
        text(msp, label, (ox - 1.18, oy + y), 0.26, "A-GRID", "CENTER")

    for a, b, label in zip(xs, xs[1:], ["2.00", "3.00", "3.00", "4.00", "2.00", "2.00"]):
        dim_h(msp, ox + a, ox + b, oy + 14.55, label)
    dim_h(msp, ox, ox + 16, oy + 14.95, "16.00")

    for a, b, label in zip(ys, ys[1:], ["2.00", "4.00", "4.50", "3.50"]):
        dim_v(msp, ox - 0.52, oy + a, oy + b, label)
    dim_v(msp, ox - 0.9, oy, oy + 14, "14.00")


def columns(msp, ox, oy):
    xs = [0, 2, 5, 8, 12, 14, 16]
    ys = [0, 2, 6, 10.5, 14]
    for x in xs:
        for y in ys:
            perimeter = x in (0, 16) or y in (0, 14)
            internal = x in (5, 8, 12) and y in (2, 6, 10.5)
            if perimeter or internal:
                rect(msp, ox + x - 0.12, oy + y - 0.12, ox + x + 0.12, oy + y + 0.12, "A-COLUMN")
                hatch_rect(msp, ox + x - 0.12, oy + y - 0.12, ox + x + 0.12, oy + y + 0.12, "SOLID", 0.05, 8)


def outline(msp, ox, oy, second=False):
    rect(msp, ox, oy, ox + 16, oy + 14, "A-WALL")
    hatch_rect(msp, ox, oy - 0.075, ox + 16, oy + 0.075, "ANSI31", 0.05, 9)
    hatch_rect(msp, ox, oy + 13.925, ox + 16, oy + 14.075, "ANSI31", 0.05, 9)
    hatch_rect(msp, ox - 0.075, oy, ox + 0.075, oy + 14, "ANSI31", 0.05, 9)
    hatch_rect(msp, ox + 15.925, oy, ox + 16.075, oy + 14, "ANSI31", 0.05, 9)
    rect(msp, ox - 0.55, oy - 0.55, ox + 16.55, oy + 14.55, "A-ROOF", "DASHED2")
    for y in [2, 6, 10.5]:
        wall(msp, ox, oy + y, ox + 16, oy + y)
    for x in [5, 8, 12]:
        wall(msp, ox + x, oy, ox + x, oy + 14)
    if second:
        wall(msp, ox + 2, oy + 6, ox + 2, oy + 14)
        wall(msp, ox + 14, oy + 6, ox + 14, oy + 14)
    columns(msp, ox, oy)


def door(msp, x, y, width=0.9, orient="N"):
    if orient == "N":
        line(msp, (x, y), (x + width, y), "A-DOOR")
        line(msp, (x, y), (x, y + width), "A-DOOR")
        arc(msp, (x, y), width, 0, 90)
    elif orient == "S":
        line(msp, (x, y), (x + width, y), "A-DOOR")
        line(msp, (x, y), (x, y - width), "A-DOOR")
        arc(msp, (x, y), width, 270, 360)
    elif orient == "E":
        line(msp, (x, y), (x, y + width), "A-DOOR")
        line(msp, (x, y), (x + width, y), "A-DOOR")
        arc(msp, (x, y), width, 0, 90)
    else:
        line(msp, (x, y), (x, y + width), "A-DOOR")
        line(msp, (x, y), (x - width, y), "A-DOOR")
        arc(msp, (x, y), width, 90, 180)


def window(msp, x1, y1, x2, y2):
    line(msp, (x1, y1), (x2, y2), "A-WINDOW")
    if abs(y2 - y1) < 1e-6:
        line(msp, (x1, y1 + 0.08), (x2, y2 + 0.08), "A-WINDOW")
        line(msp, (x1, y1 - 0.08), (x2, y2 - 0.08), "A-WINDOW")
    else:
        line(msp, (x1 + 0.08, y1), (x2 + 0.08, y2), "A-WINDOW")
        line(msp, (x1 - 0.08, y1), (x2 - 0.08, y2), "A-WINDOW")


def box_label(msp, x1, y1, x2, y2, label, layer="A-FURN"):
    rect(msp, x1, y1, x2, y2, layer)
    text(msp, label, ((x1 + x2) / 2, (y1 + y2) / 2), 0.18, layer, "CENTER")


def stair(msp, x1, y1, x2, y2, up=True):
    rect(msp, x1, y1, x2, y2, "A-STAIR")
    for i in range(1, 9):
        y = y1 + (y2 - y1) * i / 9
        line(msp, (x1, y), (x2, y), "A-STAIR")
    line(msp, ((x1 + x2) / 2, y1 + 0.25), ((x1 + x2) / 2, y2 - 0.25), "A-STAIR")
    text(msp, "UP" if up else "DN", ((x1 + x2) / 2 + 0.25, (y1 + y2) / 2), 0.22, "A-STAIR")


def toilet(msp, x, y):
    circle(msp, (x, y), 0.18, "A-SANITARY")
    rect(msp, x - 0.25, y - 0.55, x + 0.25, y - 0.2, "A-SANITARY")


def sink(msp, x, y):
    rect(msp, x - 0.25, y - 0.18, x + 0.25, y + 0.18, "A-SANITARY")
    circle(msp, (x, y), 0.07, "A-SANITARY")


def car(msp, x, y):
    rect(msp, x - 0.75, y - 1.6, x + 0.75, y + 1.6, "A-FURN")
    arc(msp, (x, y + 0.75), 0.5, 0, 180, "A-FURN")
    arc(msp, (x, y - 0.75), 0.5, 180, 360, "A-FURN")


def ground_floor(msp, ox, oy):
    add_grid(msp, ox, oy)
    outline(msp, ox, oy)
    text(msp, "GROUND FLOOR PLAN", (ox + 8, oy - 1.2), 0.32, "A-TEXT", "CENTER")
    text(msp, "SCALE 1:100", (ox + 8, oy - 1.6), 0.2, "A-TEXT", "CENTER")
    car(msp, ox + 1.0, oy + 3.0)
    car(msp, ox + 3.5, oy + 3.0)
    text(msp, "Parking 1", (ox + 1.0, oy + 1.0), 0.2, "A-TEXT", "CENTER")
    text(msp, "Parking 2", (ox + 3.5, oy + 1.0), 0.2, "A-TEXT", "CENTER")
    text(msp, "Front Terrace / Porch", (ox + 10, oy + 1.0), 0.2, "A-TEXT", "CENTER")
    box_label(msp, ox + 8.4, oy + 2.5, ox + 11.5, oy + 5.5, "Living")
    box_label(msp, ox + 8.3, oy + 6.8, ox + 11.5, oy + 8.3, "Dining")
    box_label(msp, ox + 0.6, oy + 6.7, ox + 4.5, oy + 9.9, "Kitchen")
    text(msp, "Washing / Laundry Area", (ox + 2.5, oy + 12.8), 0.18, "A-TEXT", "CENTER")
    sink(msp, ox + 1.5, oy + 12.0)
    sink(msp, ox + 2.2, oy + 12.0)
    box_label(msp, ox + 5.3, oy + 10.9, ox + 7.7, oy + 13.6, "Storage Room")
    stair(msp, ox + 12.2, oy + 2.2, ox + 13.8, oy + 5.8, True)
    text(msp, "Stairs", (ox + 13.0, oy + 6.25), 0.2, "A-TEXT", "CENTER")
    text(msp, "Bathroom 1", (ox + 14.7, oy + 7.0), 0.2, "A-TEXT", "CENTER")
    toilet(msp, ox + 15.0, oy + 7.9)
    sink(msp, ox + 14.4, oy + 7.2)
    door(msp, ox + 9.2, oy + 2, 0.9, "N")
    door(msp, ox + 12, oy + 6.2, 0.8, "E")
    door(msp, ox + 5, oy + 10.7, 0.8, "E")
    window(msp, ox + 8.5, oy, ox + 11.5, oy)
    window(msp, ox, oy + 8.3, ox, oy + 9.5)
    window(msp, ox + 16, oy + 7.0, ox + 16, oy + 8.2)


def second_floor(msp, ox, oy):
    add_grid(msp, ox, oy)
    outline(msp, ox, oy, second=True)
    text(msp, "SECOND FLOOR PLAN", (ox + 8, oy - 1.2), 0.32, "A-TEXT", "CENTER")
    text(msp, "SCALE 1:100", (ox + 8, oy - 1.6), 0.2, "A-TEXT", "CENTER")
    for label, x1, y1, x2, y2 in [
        ("Bedroom 1", 0.6, 0.5, 4.6, 5.5),
        ("Bedroom 2", 8.5, 0.5, 11.7, 5.5),
        ("Bedroom 3", 0.6, 6.5, 4.6, 10.0),
        ("Bedroom 4", 8.5, 6.5, 11.7, 10.0),
    ]:
        text(msp, label, (ox + (x1 + x2) / 2, oy + (y1 + y2) / 2), 0.2, "A-TEXT", "CENTER")
        box_label(msp, ox + x1 + 0.3, oy + y1 + 0.3, ox + x1 + 1.4, oy + y1 + 2.2, "Bed")
        box_label(msp, ox + x2 - 1.3, oy + y1 + 0.3, ox + x2 - 0.2, oy + y1 + 0.8, "WR")
    stair(msp, ox + 12.2, oy + 2.2, ox + 13.8, oy + 5.8, False)
    text(msp, "Stairs", (ox + 13.0, oy + 6.25), 0.2, "A-TEXT", "CENTER")
    text(msp, "Bathroom 2", (ox + 6.5, oy + 7.9), 0.2, "A-TEXT", "CENTER")
    toilet(msp, ox + 6.7, oy + 8.7)
    sink(msp, ox + 6.1, oy + 8.2)
    text(msp, "Hall", (ox + 7.0, oy + 4.0), 0.2, "A-TEXT", "CENTER")
    door(msp, ox + 2.2, oy + 6, 0.8, "N")
    door(msp, ox + 9.1, oy + 6, 0.8, "N")
    door(msp, ox + 8, oy + 2.3, 0.8, "E")
    door(msp, ox + 5, oy + 7.0, 0.8, "E")
    window(msp, ox + 1.2, oy + 14, ox + 3.2, oy + 14)
    window(msp, ox + 9.2, oy + 14, ox + 11.2, oy + 14)
    window(msp, ox + 1.2, oy, ox + 3.2, oy)
    window(msp, ox + 9.2, oy, ox + 11.2, oy)


def roof_plan(msp, ox, oy):
    add_grid(msp, ox, oy)
    rect(msp, ox - 0.55, oy - 0.55, ox + 16.55, oy + 14.55, "A-ROOF", "DASHED2")
    ridge_y = oy + 7.0
    ridge_x1 = ox + 3.0
    ridge_x2 = ox + 13.0
    line(msp, (ridge_x1, ridge_y), (ridge_x2, ridge_y), "A-ROOF")
    for p in [(ox - 0.55, oy - 0.55), (ox - 0.55, oy + 14.55), (ox + 16.55, oy - 0.55), (ox + 16.55, oy + 14.55)]:
        line(msp, p, (ridge_x1 if p[0] < ox + 8 else ridge_x2, ridge_y), "A-ROOF")
    line(msp, (ox + 8, oy - 0.55), (ox + 8, oy + 14.55), "A-ROOF", "CENTER2")
    hatch_rect(msp, ox - 0.55, oy - 0.55, ox + 16.55, oy + 14.55, "ANSI31", 0.22, 8)
    text(msp, "ROOF PLAN", (ox + 8, oy - 1.2), 0.32, "A-TEXT", "CENTER")
    text(msp, "HIP ROOF / EAVE PROJECTION", (ox + 8, oy + 7.6), 0.25, "A-TEXT", "CENTER")
    dim_h(msp, ox - 0.55, ox + 16.55, oy + 15.55, "17.10")
    dim_v(msp, ox - 1.5, oy - 0.55, oy + 14.55, "15.10")


def elev_grid(msp, ox, oy, labels, bays, height=8.8):
    pos = [0.0]
    for bay in bays:
        pos.append(pos[-1] + bay)
    top_y = oy + height + 0.65
    for p, label in zip(pos, labels):
        x = ox + p
        line(msp, (x, oy - 0.55), (x, oy + height), "A-GRID", "CENTER2")
        circle(msp, (x, top_y), 0.22, "A-GRID")
        text(msp, label, (x, top_y), 0.22, "A-GRID", "CENTER")
    for a, b, bay in zip(pos, pos[1:], bays):
        dim_h(msp, ox + a, ox + b, oy - 0.55, f"{bay:.2f}")
    dim_h(msp, ox, ox + pos[-1], oy - 0.95, f"{pos[-1]:.2f}")


def elevation(msp, ox, oy, name, width=16.0, grid_labels=None, bays=None):
    if grid_labels is None:
        grid_labels = list("ABCDEFG")
    if bays is None:
        bays = [2.0, 3.0, 3.0, 4.0, 2.0, 2.0]
    ground = oy
    f2 = oy + 3.2
    eave = oy + 6.4
    ridge = oy + 8.4
    elev_grid(msp, ox, oy, grid_labels, bays, height=8.8)
    line(msp, (ox, ground), (ox + width, ground), "A-WALL")
    rect(msp, ox, ground, ox + width, eave, "A-WALL")
    hatch_rect(msp, ox, ground, ox + width, ground + 0.25, "ANSI31", 0.08, 9)
    hatch_rect(msp, ox, f2 - 0.12, ox + width, f2 + 0.12, "ANSI31", 0.08, 9)
    line(msp, (ox - 0.6, f2), (ox + width + 0.6, f2), "A-DIMS")
    text(msp, "F.F.L. +3.20", (ox + width + 0.8, f2), 0.18, "A-DIMS")
    text(msp, "G.L. +/-0.00", (ox + width + 0.8, ground), 0.18, "A-DIMS")
    text(msp, "ROOF RIDGE +8.40", (ox + width + 0.8, ridge), 0.18, "A-DIMS")
    msp.add_lwpolyline([(ox - 0.8, eave), (ox + width / 2, ridge), (ox + width + 0.8, eave)], dxfattribs={"layer": "A-ROOF"})
    hatch = msp.add_hatch(color=8, dxfattribs={"layer": "A-HATCH"})
    hatch.set_pattern_fill("ANSI31", scale=0.18)
    hatch.paths.add_polyline_path([(ox - 0.8, eave), (ox + width / 2, ridge), (ox + width + 0.8, eave)], is_closed=True)
    for x in [ox + 2.0, ox + 6.0, ox + 10.0, ox + 14.0]:
        rect(msp, x - 0.45, ground + 1.2, x + 0.45, ground + 2.2, "A-WINDOW")
        rect(msp, x - 0.45, f2 + 1.0, x + 0.45, f2 + 2.0, "A-WINDOW")
    rect(msp, ox + width / 2 - 0.45, ground, ox + width / 2 + 0.45, ground + 2.1, "A-DOOR")
    dim_h(msp, ox, ox + width, ground - 0.6, f"{width:.2f}")
    dim_v(msp, ox - 1.0, ground, ridge, "8.40")
    text(msp, name, (ox + width / 2, oy - 1.2), 0.32, "A-TEXT", "CENTER")


def section(msp, ox, oy, name, grid_labels=None, bays=None):
    if grid_labels is None:
        grid_labels = list("ABCDEFG")
    if bays is None:
        bays = [2.0, 3.0, 3.0, 4.0, 2.0, 2.0]
    ground = oy
    f2 = oy + 3.2
    roof = oy + 6.4
    ridge = oy + 8.4
    elev_grid(msp, ox, oy, grid_labels, bays, height=8.8)
    rect(msp, ox, ground, ox + 16, roof, "A-WALL")
    hatch_rect(msp, ox, ground - 0.3, ox + 16, ground, "ANSI31", 0.08, 9)
    hatch_rect(msp, ox, f2 - 0.15, ox + 16, f2 + 0.15, "ANSI31", 0.08, 9)
    for x in [ox, ox + 5, ox + 8, ox + 12, ox + 16]:
        rect(msp, x - 0.15, ground, x + 0.15, roof, "A-COLUMN")
        hatch_rect(msp, x - 0.15, ground, x + 0.15, roof, "ANSI31", 0.08, 8)
    stair(msp, ox + 12.2, ground + 0.3, ox + 13.8, f2 - 0.2, True)
    stair(msp, ox + 12.2, f2 + 0.3, ox + 13.8, roof - 0.2, False)
    msp.add_lwpolyline([(ox - 0.8, roof), (ox + 8, ridge), (ox + 16.8, roof)], dxfattribs={"layer": "A-ROOF"})
    hatch = msp.add_hatch(color=8, dxfattribs={"layer": "A-HATCH"})
    hatch.set_pattern_fill("ANSI31", scale=0.18)
    hatch.paths.add_polyline_path([(ox - 0.8, roof), (ox + 8, ridge), (ox + 16.8, roof)], is_closed=True)
    text(msp, "RC COLUMN", (ox + 1.0, f2 + 0.7), 0.18, "A-ANNO")
    text(msp, "RC SLAB / BEAM", (ox + 6.0, f2 + 0.35), 0.18, "A-ANNO")
    dim_v(msp, ox - 1.0, ground, f2, "3.20")
    dim_v(msp, ox - 1.4, f2, roof, "3.20")
    dim_v(msp, ox - 1.8, ground, ridge, "8.40")
    text(msp, name, (ox + 8, oy - 1.2), 0.32, "A-TEXT", "CENTER")


def title_block(
    msp,
    x,
    y,
    w=8.0,
    h=27.7,
    drawing_title=TH_PLAN,
    drawing_no="A-01",
    sheet_no="01 / 02",
):
    rect(msp, x, y, x + w, y + h, "A-TITLE")
    rows = [2.0, 1.6, 1.2, 1.2, 2.0, 1.2, 1.4, 2.2, 1.0, 1.0, 1.0]
    cy = y + h
    for row in rows:
        cy -= row
        line(msp, (x, cy), (x + w, cy), "A-TITLE")
    text(msp, TH_COMPANY, (x + w / 2, y + h - 0.65), 0.3, "A-TITLE", "CENTER")
    text(msp, "PJ DEV Co., Ltd.", (x + w / 2, y + h - 1.25), 0.3, "A-TITLE", "CENTER")

    items = [
        ("Project Name:", TH_PROJECT, 1.6),
        ("Owner:", "PJ", 1.2),
        ("Location:", "BKK", 1.2),
        ("Engineer / Architect:", "", 2.0),
        ("Drafted By:", "PJ Team", 1.2),
        ("Drawing Title:", drawing_title, 1.4),
        ("Drawing No.:", drawing_no, 2.2),
        ("Sheet No.:", sheet_no, 1.0),
        ("Scale:", "1:100", 1.0),
        ("Date:", "28/04/2569", 1.0),
    ]
    yy = y + h - 2.25
    for label, value, row_h in items:
        text(msp, label, (x + 0.25, yy), 0.18, "A-TITLE")
        if label == "Drawing No.:":
            text(msp, value, (x + w / 2, yy - 0.9), 0.75, "A-TITLE", "CENTER")
        elif label == "Engineer / Architect:":
            line(msp, (x + 1.0, yy - 0.9), (x + w - 1.0, yy - 0.9), "A-TITLE")
            text(msp, "(Signature)", (x + w - 1.45, yy - 1.15), 0.14, "A-TITLE", "CENTER")
            text(msp, "License No.", (x + 1.0, yy - 1.55), 0.14, "A-TITLE")
        else:
            text(msp, value, (x + w / 2, yy - 0.65), 0.28, "A-TITLE", "CENTER")
        yy -= row_h
    text(msp, "Notes", (x + 0.25, y + 3.2), 0.2, "A-TITLE")


def a3_sheet_frame(msp, sx, sy, drawing_no, sheet_no, title):
    # A3 landscape at 1:100 in model space: 420 mm x 297 mm -> 42.00 m x 29.70 m.
    w, h = 42.0, 29.7
    margin = 0.7
    rect(msp, sx, sy, sx + w, sy + h, "A-TITLE")
    rect(msp, sx + margin, sy + margin, sx + w - margin, sy + h - margin, "A-TITLE")
    title_block(
        msp,
        sx + 33.0,
        sy + 1.0,
        8.0,
        27.7,
        drawing_title=title,
        drawing_no=drawing_no,
        sheet_no=sheet_no,
    )
    text(msp, drawing_no, (sx + 1.2, sy + h - 1.1), 0.28, "A-TITLE")


def hatch_legend(msp, x, y):
    text(msp, "HATCH / MATERIAL LEGEND", (x, y + 1.2), 0.22, "A-TEXT")
    rect(msp, x, y + 0.65, x + 0.8, y + 1.05, "A-WALL")
    hatch_rect(msp, x, y + 0.65, x + 0.8, y + 1.05, "ANSI31", 0.05, 9)
    text(msp, "CONCRETE / RC WALL", (x + 1.0, y + 0.78), 0.18, "A-TEXT")
    rect(msp, x, y + 0.1, x + 0.8, y + 0.5, "A-COLUMN")
    hatch_rect(msp, x, y + 0.1, x + 0.8, y + 0.5, "SOLID", 0.05, 8)
    text(msp, "RC COLUMN", (x + 1.0, y + 0.23), 0.18, "A-TEXT")


def face3d(msp, pts, layer):
    msp.add_3dface(pts, dxfattribs={"layer": layer})


def box3d(msp, x1, y1, z1, x2, y2, z2, layer):
    p = [
        (x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1),
        (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2),
    ]
    for face in [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        face3d(msp, [p[i] for i in face], layer)


def wall3d(msp, x1, y1, x2, y2, z1, z2, thickness=0.15):
    if abs(y2 - y1) < 1e-6:
        box3d(msp, x1, y1 - thickness / 2, z1, x2, y1 + thickness / 2, z2, "3D-WALL")
    elif abs(x2 - x1) < 1e-6:
        box3d(msp, x1 - thickness / 2, y1, z1, x1 + thickness / 2, y2, z2, "3D-WALL")


def build_3d_model(msp, ox=60.0, oy=0.0, oz=0.0):
    xs = [0, 2, 5, 8, 12, 14, 16]
    ys = [0, 2, 6, 10.5, 14]
    # slabs and roof-bearing floors
    box3d(msp, ox, oy, oz - 0.2, ox + 16, oy + 14, oz, "3D-SLAB")
    box3d(msp, ox, oy, oz + 3.05, ox + 16, oy + 14, oz + 3.25, "3D-SLAB")
    box3d(msp, ox, oy, oz + 6.25, ox + 16, oy + 14, oz + 6.45, "3D-SLAB")
    for z1, z2 in [(oz, oz + 3.2), (oz + 3.2, oz + 6.4)]:
        wall3d(msp, ox, oy, ox + 16, oy, z1, z2)
        wall3d(msp, ox, oy + 14, ox + 16, oy + 14, z1, z2)
        wall3d(msp, ox, oy, ox, oy + 14, z1, z2)
        wall3d(msp, ox + 16, oy, ox + 16, oy + 14, z1, z2)
        for y in [2, 6, 10.5]:
            wall3d(msp, ox, oy + y, ox + 16, oy + y, z1, z2)
        for x in [5, 8, 12]:
            wall3d(msp, ox + x, oy, ox + x, oy + 14, z1, z2)
    for x in xs:
        for y in ys:
            perimeter = x in (0, 16) or y in (0, 14)
            internal = x in (5, 8, 12) and y in (2, 6, 10.5)
            if perimeter or internal:
                box3d(msp, ox + x - 0.15, oy + y - 0.15, oz, ox + x + 0.15, oy + y + 0.15, oz + 6.4, "3D-COLUMN")
    # hip roof as simple planes
    e = 0.65
    z_eave = oz + 6.55
    z_ridge = oz + 8.4
    c1 = (ox - e, oy - e, z_eave)
    c2 = (ox + 16 + e, oy - e, z_eave)
    c3 = (ox + 16 + e, oy + 14 + e, z_eave)
    c4 = (ox - e, oy + 14 + e, z_eave)
    r1 = (ox + 3.0, oy + 7.0, z_ridge)
    r2 = (ox + 13.0, oy + 7.0, z_ridge)
    face3d(msp, [c1, c2, r2, r1], "3D-ROOF")
    face3d(msp, [c4, c3, r2, r1], "3D-ROOF")
    face3d(msp, [c1, c4, r1, r1], "3D-ROOF")
    face3d(msp, [c2, c3, r2, r2], "3D-ROOF")
    text(msp, "SCHEMATIC 3D MODEL", (ox + 8, oy - 2), 0.35, "3D-VIEW", "CENTER")


def project_iso(p, scale=0.8):
    x, y, z = p
    return ((x - y) * 0.707 * scale, ((x + y) * 0.408 + z) * scale)


def project_perspective(p, scale=1.0, camera=(24, -28, 16), dist=34):
    x, y, z = p
    cx, cy, cz = camera
    dx, dy, dz = x - cx, y - cy, z - cz
    denom = max(0.2, 1 + dy / dist)
    return (dx * scale / denom, (dz * 1.15 - dy * 0.18) * scale / denom)


def draw_projected_house(msp, ox, oy, title, projector):
    base = (0, 0, 0)
    edges = []
    def add_box(x1, y1, z1, x2, y2, z2):
        pts = [(x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1), (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2)]
        for a, b in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:
            edges.append((pts[a], pts[b]))
    add_box(0, 0, 0, 16, 14, 6.4)
    for x in [0, 5, 8, 12, 16]:
        add_box(x - 0.12, -0.12, 0, x + 0.12, 14.12, 6.4)
    roof_edges = [((-0.65,-0.65,6.55),(16.65,-0.65,6.55)),((16.65,-0.65,6.55),(16.65,14.65,6.55)),((16.65,14.65,6.55),(-0.65,14.65,6.55)),((-0.65,14.65,6.55),(-0.65,-0.65,6.55)),((3,7,8.4),(13,7,8.4)),((-0.65,-0.65,6.55),(3,7,8.4)),((-0.65,14.65,6.55),(3,7,8.4)),((16.65,-0.65,6.55),(13,7,8.4)),((16.65,14.65,6.55),(13,7,8.4))]
    edges.extend(roof_edges)
    for a, b in edges:
        ax, ay = projector(a)
        bx, by = projector(b)
        line(msp, (ox + ax, oy + ay), (ox + bx, oy + by), "3D-VIEW")
    text(msp, title, (ox + 5.5, oy - 1.3), 0.32, "A-TEXT", "CENTER")


def add_layout_tabs(doc, sheet_defs):
    # Paper space is in millimeters. Each viewport shows one 42.00 m x 29.70 m
    # A3 sheet frame from model space at 1:100.
    for name, sy in sheet_defs:
        layout = doc.layouts.new(name)
        layout.page_setup(size=(420, 297), margins=(0, 0, 0, 0), units="mm")
        layout.add_viewport(
            center=(210, 148.5),
            size=(420, 297),
            view_center_point=(21.0, sy + 14.85),
            view_height=29.7,
            dxfattribs={"layer": "DEFPOINTS"},
        )
    if "Layout1" in doc.layouts and len(doc.layouts) > 2:
        doc.layouts.delete("Layout1")


def build():
    doc = setup_doc()
    msp = doc.modelspace()

    sheets = [
        ("A-01", "01 / 11", "1ST FLOOR PLAN", ground_floor),
        ("A-02", "02 / 11", "2ND FLOOR PLAN", second_floor),
        ("A-03", "03 / 11", "ROOF PLAN", roof_plan),
    ]
    for idx, (dwg, sheet_no, title, fn) in enumerate(sheets):
        sy = -34.0 * idx
        a3_sheet_frame(msp, 0, sy, dwg, sheet_no, title)
        fn(msp, 8.0, sy + 7.0)
        text(msp, "COLUMN CENTERLINES ALIGN ON BOTH FLOORS", (18.5, sy + 3.6), 0.22, "A-ANNO", "CENTER")
        text(msp, TH_COLUMN_NOTE, (18.5, sy + 3.25), 0.22, "A-ANNO", "CENTER")
        hatch_legend(msp, 2.0, sy + 2.0)

    elev_specs = [
        ("ELEVATION 1", list("ABCDEFG"), [2.0, 3.0, 3.0, 4.0, 2.0, 2.0], 16.0),
        ("ELEVATION 2", ["1", "2", "3", "4", "5"], [2.0, 4.0, 4.5, 3.5], 14.0),
        ("ELEVATION 3", list("ABCDEFG"), [2.0, 3.0, 3.0, 4.0, 2.0, 2.0], 16.0),
        ("ELEVATION 4", ["1", "2", "3", "4", "5"], [2.0, 4.0, 4.5, 3.5], 14.0),
    ]
    for i, (title, labels, bays, width) in enumerate(elev_specs, start=3):
        sy = -34.0 * i
        dwg = f"A-{i + 1:02d}"
        a3_sheet_frame(msp, 0, sy, dwg, f"{i + 1:02d} / 11", title)
        elevation(msp, 8.0, sy + 10.0, title, width, labels, bays)
        hatch_legend(msp, 2.0, sy + 2.0)

    section_specs = [
        ("SECTION A", list("ABCDEFG"), [2.0, 3.0, 3.0, 4.0, 2.0, 2.0]),
        ("SECTION B", ["1", "2", "3", "4", "5"], [2.0, 4.0, 4.5, 3.5]),
    ]
    for i, (title, labels, bays) in enumerate(section_specs, start=7):
        sy = -34.0 * i
        dwg = f"A-{i + 1:02d}"
        a3_sheet_frame(msp, 0, sy, dwg, f"{i + 1:02d} / 11", title)
        section(msp, 8.0, sy + 9.0, title, labels, bays)
        hatch_legend(msp, 2.0, sy + 2.0)

    build_3d_model(msp)
    sy = -34.0 * 9
    a3_sheet_frame(msp, 0, sy, "A-10", "10 / 11", "3D ISOMETRIC VIEW")
    draw_projected_house(msp, 10.5, sy + 8.0, "3D ISOMETRIC VIEW", project_iso)
    text(msp, "Schematic 3D DXF model is placed in model space at X=60.", (18.5, sy + 3.2), 0.2, "A-ANNO", "CENTER")

    sy = -34.0 * 10
    a3_sheet_frame(msp, 0, sy, "A-11", "11 / 11", "3D PERSPECTIVE VIEW")
    draw_projected_house(msp, 17.0, sy + 10.0, "3D PERSPECTIVE VIEW", project_perspective)
    text(msp, "Perspective sheet is a 2D line projection for plotting; orbit the 3D model in model space for live views.", (18.5, sy + 3.2), 0.18, "A-ANNO", "CENTER")

    add_layout_tabs(doc, [(f"A-{i + 1:02d}", -34.0 * i) for i in range(11)])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
