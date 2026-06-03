from __future__ import annotations

from pathlib import Path
import math

import FreeCAD as App
import Part
import TechDraw


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "freecad"
FCSTD = OUT_DIR / "pj_dev_2story_house_parametric_techdraw_A01-A11.FCStd"
IFC = OUT_DIR / "pj_dev_2story_house_parametric_techdraw_A01-A11.ifc"
TEMPLATE = Path(r"C:\Program Files\FreeCAD 0.20\data\Mod\TechDraw\Templates\A3_LandscapeTD.svg")

M = 1000.0
WALL_T = 0.15 * M
FLOOR_H = 3.20 * M
WIDTH = 16.00 * M
DEPTH = 14.00 * M
RIDGE_H = 8.40 * M
EAVE_H = 6.55 * M
EAVE = 0.65 * M

X_GRID = [0, 2, 5, 8, 12, 14, 16]
Y_GRID = [0, 2, 6, 10.5, 14]
X_LABELS = list("ABCDEFG")
Y_LABELS = ["1", "2", "3", "4", "5"]


def v(x, y, z=0):
    return App.Vector(x, y, z)


def add_obj(doc, name, shape, group=None, color=None):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if group:
        group.addObject(obj)
    if color and getattr(obj, "ViewObject", None):
        obj.ViewObject.ShapeColor = color
    return obj


def make_box(doc, name, x, y, z, dx, dy, dz, group, color):
    shape = Part.makeBox(dx, dy, dz, v(x, y, z))
    return add_obj(doc, name, shape, group, color)


def make_wall(doc, name, x1, y1, x2, y2, z1, z2, group):
    if abs(y2 - y1) < 1:
        return make_box(doc, name, x1, y1 - WALL_T / 2, z1, x2 - x1, WALL_T, z2 - z1, group, (0.82, 0.82, 0.82))
    if abs(x2 - x1) < 1:
        return make_box(doc, name, x1 - WALL_T / 2, y1, z1, WALL_T, y2 - y1, z2 - z1, group, (0.82, 0.82, 0.82))
    raise ValueError("Only orthogonal walls are supported")


def make_roof(doc, group):
    c1 = v(-EAVE, -EAVE, EAVE_H)
    c2 = v(WIDTH + EAVE, -EAVE, EAVE_H)
    c3 = v(WIDTH + EAVE, DEPTH + EAVE, EAVE_H)
    c4 = v(-EAVE, DEPTH + EAVE, EAVE_H)
    r1 = v(3 * M, 7 * M, RIDGE_H)
    r2 = v(13 * M, 7 * M, RIDGE_H)
    faces = []
    for pts in ([c1, c2, r2, r1, c1], [c4, c3, r2, r1, c4], [c1, c4, r1, c1], [c2, c3, r2, c2]):
        faces.append(Part.Face(Part.makePolygon(pts)))
    roof = Part.makeCompound(faces)
    return add_obj(doc, "Hip_Roof_Schematic", roof, group, (0.45, 0.12, 0.08))


def add_3d_model(doc):
    model = doc.addObject("App::DocumentObjectGroup", "MODEL_3D")
    slabs = doc.addObject("App::DocumentObjectGroup", "3D_Slabs")
    cols = doc.addObject("App::DocumentObjectGroup", "3D_RC_Columns")
    walls = doc.addObject("App::DocumentObjectGroup", "3D_Walls")
    roof_g = doc.addObject("App::DocumentObjectGroup", "3D_Roof")
    for g in [slabs, cols, walls, roof_g]:
        model.addObject(g)

    make_box(doc, "Ground_Floor_Slab", 0, 0, -200, WIDTH, DEPTH, 200, slabs, (0.65, 0.65, 0.65))
    make_box(doc, "Second_Floor_Slab", 0, 0, FLOOR_H - 150, WIDTH, DEPTH, 200, slabs, (0.65, 0.65, 0.65))
    make_box(doc, "Roof_Level_Ring_Slab", 0, 0, FLOOR_H * 2 - 150, WIDTH, DEPTH, 200, slabs, (0.65, 0.65, 0.65))

    for level, z1 in enumerate([0, FLOOR_H], start=1):
        z2 = z1 + FLOOR_H
        make_wall(doc, f"L{level}_Wall_South", 0, 0, WIDTH, 0, z1, z2, walls)
        make_wall(doc, f"L{level}_Wall_North", 0, DEPTH, WIDTH, DEPTH, z1, z2, walls)
        make_wall(doc, f"L{level}_Wall_West", 0, 0, 0, DEPTH, z1, z2, walls)
        make_wall(doc, f"L{level}_Wall_East", WIDTH, 0, WIDTH, DEPTH, z1, z2, walls)
        for y in [2 * M, 6 * M, 10.5 * M]:
            make_wall(doc, f"L{level}_Wall_Y_{y/M:g}", 0, y, WIDTH, y, z1, z2, walls)
        for x in [5 * M, 8 * M, 12 * M]:
            make_wall(doc, f"L{level}_Wall_X_{x/M:g}", x, 0, x, DEPTH, z1, z2, walls)

    for x in X_GRID:
        for y in Y_GRID:
            perimeter = x in (0, 16) or y in (0, 14)
            internal = x in (5, 8, 12) and y in (2, 6, 10.5)
            if perimeter or internal:
                make_box(
                    doc,
                    f"RC_Column_{x:g}_{y:g}",
                    x * M - 150,
                    y * M - 150,
                    0,
                    300,
                    300,
                    FLOOR_H * 2,
                    cols,
                    (0.45, 0.45, 0.45),
                )

    make_roof(doc, roof_g)
    return model


def edge_line(x1, y1, x2, y2, z=0):
    return Part.makeLine(v(x1, y1, z), v(x2, y2, z))


def edge_circle(x, y, r, z=0):
    return Part.makeCircle(r, v(x, y, z), v(0, 0, 1))


def add_compound(doc, name, edges, group, color=(0, 0, 0)):
    obj = add_obj(doc, name, Part.Compound(edges), group, color)
    return obj


def add_grid_2d(edges, ox, oy, labels, bays, height, vertical=True):
    pos = [0]
    for b in bays:
        pos.append(pos[-1] + b * M)
    for p, label in zip(pos, labels):
        x = ox + p
        edges.append(edge_line(x, oy - 500, x, oy + height))
        edges.append(edge_circle(x, oy + height + 500, 220))
    return pos[-1]


def elevation_edges(width_m=16.0):
    width = width_m * M
    edges = []
    ground, f2, eave, ridge = 0, FLOOR_H, FLOOR_H * 2, RIDGE_H
    edges += [
        edge_line(0, ground, width, ground),
        edge_line(0, ground, 0, eave),
        edge_line(width, ground, width, eave),
        edge_line(0, eave, width / 2, ridge),
        edge_line(width, eave, width / 2, ridge),
        edge_line(0, f2, width, f2),
    ]
    for x in [2, 6, 10, 14]:
        if x * M < width:
            edges += [
                edge_line(x * M - 450, 1200, x * M + 450, 1200),
                edge_line(x * M + 450, 1200, x * M + 450, 2200),
                edge_line(x * M + 450, 2200, x * M - 450, 2200),
                edge_line(x * M - 450, 2200, x * M - 450, 1200),
                edge_line(x * M - 450, f2 + 1000, x * M + 450, f2 + 1000),
                edge_line(x * M + 450, f2 + 1000, x * M + 450, f2 + 2000),
                edge_line(x * M + 450, f2 + 2000, x * M - 450, f2 + 2000),
                edge_line(x * M - 450, f2 + 2000, x * M - 450, f2 + 1000),
            ]
    return edges


def section_edges(width_m=16.0):
    width = width_m * M
    edges = elevation_edges(width_m)
    for x in [0, 5, 8, 12, 16]:
        if x * M <= width:
            edges += [
                edge_line(x * M - 150, 0, x * M - 150, FLOOR_H * 2),
                edge_line(x * M + 150, 0, x * M + 150, FLOOR_H * 2),
            ]
    for z in [0, FLOOR_H, FLOOR_H * 2]:
        edges.append(edge_line(0, z, width, z))
    return edges


def add_2d_views(doc):
    views = doc.addObject("App::DocumentObjectGroup", "DRAWING_VIEWS_2D")
    specs = [
        ("Elevation_1_A_G", elevation_edges(16), 0),
        ("Elevation_2_1_5", elevation_edges(14), -12000),
        ("Elevation_3_A_G", elevation_edges(16), -24000),
        ("Elevation_4_1_5", elevation_edges(14), -36000),
        ("Section_A_A_G", section_edges(16), -48000),
        ("Section_B_1_5", section_edges(14), -60000),
    ]
    for name, edges, offset_y in specs:
        moved = []
        for e in edges:
            moved.append(e.translated(v(0, offset_y, 0)))
        add_compound(doc, name, moved, views)
    return views


def export_ifc(doc):
    try:
        import importIFC
        export_objs = [obj for obj in doc.Objects if getattr(obj, "Shape", None) and not obj.Name.startswith("Elevation") and not obj.Name.startswith("Section")]
        importIFC.export(export_objs, str(IFC))
        return True, ""
    except Exception as exc:
        return False, repr(exc)


def model_sources(doc):
    return [
        obj
        for obj in doc.Objects
        if getattr(obj, "Shape", None)
        and obj.TypeId == "Part::Feature"
        and not obj.Name.startswith(("Elevation_", "Section_"))
    ]


def add_annotation(doc, page, name, lines, x, y, size=4):
    anno = doc.addObject("TechDraw::DrawViewAnnotation", name)
    anno.Text = lines if isinstance(lines, list) else [lines]
    anno.TextSize = size
    anno.X = x
    anno.Y = y
    page.addView(anno)
    return anno


def add_arbitrary_dimension(doc, page, name, text_value, x, y, dim_type="DistanceX"):
    dim = doc.addObject("TechDraw::DrawViewDimension", name)
    dim.Type = dim_type
    dim.Arbitrary = True
    dim.FormatSpec = text_value
    dim.X = x
    dim.Y = y
    page.addView(dim)
    return dim


def add_page(doc, name, title, drawing_no, sheet_no):
    page = doc.addObject("TechDraw::DrawPage", name)
    template = doc.addObject("TechDraw::DrawSVGTemplate", f"{name}_Template")
    template.Template = str(TEMPLATE)
    page.Template = template
    add_annotation(
        doc,
        page,
        f"{name}_TitleBlockText",
        [
            "PJ DEV Co., Ltd.",
            "Project: อาคารอยู่อาศัย คสล.",
            f"Drawing: {title}",
            f"No.: {drawing_no}    Sheet: {sheet_no}    Scale: 1:100",
            "Date: 28/04/2569",
        ],
        295,
        24,
        3,
    )
    return page


def add_part_view(doc, page, name, sources, direction, x, y, scale=0.01, rotation=0):
    view = doc.addObject("TechDraw::DrawViewPart", name)
    view.Source = sources
    view.Direction = direction
    view.ScaleType = "Custom"
    view.Scale = scale
    view.Rotation = rotation
    view.X = x
    view.Y = y
    view.HardHidden = True
    page.addView(view)
    return view


def add_section_view(doc, page, name, base_view, origin, normal, direction, x, y):
    section = doc.addObject("TechDraw::DrawViewSection", name)
    section.BaseView = base_view
    section.SectionOrigin = origin
    section.SectionNormal = normal
    section.SectionDirection = direction
    section.Direction = direction
    section.ScaleType = "Custom"
    section.Scale = 0.01
    section.X = x
    section.Y = y
    section.CutSurfaceDisplay = "SvgHatch"
    section.HatchScale = 2.0
    page.addView(section)
    return section


def add_techdraw_pages(doc):
    sources = model_sources(doc)
    section_a_line = doc.getObject("Section_A_A_G")
    section_b_line = doc.getObject("Section_B_1_5")
    roof_source = [doc.getObject("Hip_Roof_Schematic")] if doc.getObject("Hip_Roof_Schematic") else sources
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)

    page = add_page(doc, "TD_A01_1st_Floor_Plan", "1ST FLOOR PLAN", "A-01", "01 / 11")
    add_part_view(doc, page, "TD_A01_1st_Floor_Top", sources, App.Vector(0, 0, 1), 210, 155, 0.012)
    add_annotation(doc, page, "TD_A01_Notes", ["1ST FLOOR PLAN", "Grid A-G / 1-5", "Main footprint 16.00 m x 14.00 m"], 210, 48, 4)
    add_arbitrary_dimension(doc, page, "TD_A01_Dim_X", "16.00 m", 210, 42, "DistanceX")
    add_arbitrary_dimension(doc, page, "TD_A01_Dim_Y", "14.00 m", 72, 150, "DistanceY")

    page = add_page(doc, "TD_A02_2nd_Floor_Plan", "2ND FLOOR PLAN", "A-02", "02 / 11")
    add_part_view(doc, page, "TD_A02_2nd_Floor_Top", sources, App.Vector(0, 0, 1), 210, 155, 0.012)
    add_annotation(doc, page, "TD_A02_Notes", ["2ND FLOOR PLAN", "Column centerlines align with first floor"], 210, 48, 4)
    add_arbitrary_dimension(doc, page, "TD_A02_Dim_X", "16.00 m", 210, 42, "DistanceX")
    add_arbitrary_dimension(doc, page, "TD_A02_Dim_Y", "14.00 m", 72, 150, "DistanceY")

    page = add_page(doc, "TD_A03_Roof_Plan", "ROOF PLAN", "A-03", "03 / 11")
    add_part_view(doc, page, "TD_A03_Roof_Top", roof_source, App.Vector(0, 0, 1), 210, 155, 0.012)
    add_annotation(doc, page, "TD_A03_Notes", ["ROOF PLAN", "Hip roof with eave projection", "Ridge +8.40 m"], 210, 48, 4)
    add_arbitrary_dimension(doc, page, "TD_A03_Dim_X", "17.30 m incl. eaves", 210, 42, "DistanceX")

    elevation_defs = [
        ("TD_A04_Elevation_1", "ELEVATION 1", "A-04", "04 / 11", App.Vector(0, -1, 0)),
        ("TD_A05_Elevation_2", "ELEVATION 2", "A-05", "05 / 11", App.Vector(0, 1, 0)),
        ("TD_A06_Elevation_3", "ELEVATION 3", "A-06", "06 / 11", App.Vector(-1, 0, 0)),
        ("TD_A07_Elevation_4", "ELEVATION 4", "A-07", "07 / 11", App.Vector(1, 0, 0)),
    ]
    for page_name, title, drawing_no, sheet_no, direction in elevation_defs:
        page = add_page(doc, page_name, title, drawing_no, sheet_no)
        add_part_view(doc, page, f"{page_name}_View", sources, direction, 210, 152, 0.012)
        add_annotation(doc, page, f"{page_name}_Notes", [title, "RIDGE +8.40 m", "EAVE +6.55 m", "F.F.L. +3.20 m"], 210, 48, 4)
        add_arbitrary_dimension(doc, page, f"{page_name}_Level_Dim", "8.40 m", 70, 150, "DistanceY")

    page = add_page(doc, "TD_A08_Section_A", "SECTION A", "A-08", "08 / 11")
    add_part_view(doc, page, "TD_A08_Section_Base", sources, App.Vector(0, -1, 0), 210, 205, 0.008)
    if section_a_line:
        add_part_view(doc, page, "TD_A08_Section_A_Linework", [section_a_line], App.Vector(0, 0, 1), 210, 125, 0.01)
    add_annotation(doc, page, "TD_A08_Notes", ["SECTION A-A", "Schematic section linework with floor levels"], 210, 45, 4)
    add_arbitrary_dimension(doc, page, "TD_A08_FloorHeight", "3.20 m floor-to-floor", 70, 125, "DistanceY")

    page = add_page(doc, "TD_A09_Section_B", "SECTION B", "A-09", "09 / 11")
    add_part_view(doc, page, "TD_A09_Section_Base", sources, App.Vector(1, 0, 0), 210, 205, 0.008)
    if section_b_line:
        add_part_view(doc, page, "TD_A09_Section_B_Linework", [section_b_line], App.Vector(0, 0, 1), 210, 125, 0.01)
    add_annotation(doc, page, "TD_A09_Notes", ["SECTION B-B", "Schematic section linework with floor levels"], 210, 45, 4)
    add_arbitrary_dimension(doc, page, "TD_A09_FloorHeight", "3.20 m floor-to-floor", 70, 125, "DistanceY")

    page = add_page(doc, "TD_A10_3D_Isometric_View", "3D ISOMETRIC VIEW", "A-10", "10 / 11")
    iso = add_part_view(doc, page, "TD_A10_3D_Isometric", sources, App.Vector(1, -1, 0.65), 210, 150, 0.008)
    iso.Perspective = False
    add_annotation(doc, page, "TD_A10_Notes", ["3D ISOMETRIC VIEW", "Generated from FreeCAD Part geometry", "IFC exported separately"], 210, 45, 4)

    page = add_page(doc, "TD_A11_3D_Perspective_View", "3D PERSPECTIVE VIEW", "A-11", "11 / 11")
    persp = add_part_view(doc, page, "TD_A11_3D_Perspective", sources, App.Vector(1, -1, 0.45), 210, 150, 0.008)
    persp.Perspective = True
    add_annotation(doc, page, "TD_A11_Notes", ["3D PERSPECTIVE VIEW", "Perspective viewport from schematic 3D model"], 210, 45, 4)

    return [obj for obj in doc.Objects if obj.TypeId.startswith("TechDraw::")]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("PJ_DEV_2Story_Parametric")
    doc.addObject("App::DocumentObjectGroup", "PROJECT_INFO")
    add_3d_model(doc)
    add_2d_views(doc)
    add_techdraw_pages(doc)
    doc.recompute()
    doc.saveAs(str(FCSTD))
    ok, err = export_ifc(doc)
    report = OUT_DIR / "freecad_export_report.txt"
    report.write_text(
        f"FCStd: {FCSTD}\nIFC: {IFC if ok else 'FAILED'}\nIFC export ok: {ok}\nError: {err}\n",
        encoding="utf-8",
    )
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
