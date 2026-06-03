# PJ DEV Drawing Layer Standard

Unit: meter
Scale note: 1:100
Drawing set: Full A3 landscape title block sheet set
DXF output: model-space sheet frames plus paper-space layout tabs.
Sheets:
- A-01 / 01 / 09: 1ST FLOOR PLAN
- A-02 / 02 / 09: 2ND FLOOR PLAN
- A-03 / 03 / 09: ROOF PLAN
- A-04 / 04 / 09: ELEVATION 1
- A-05 / 05 / 09: ELEVATION 2
- A-06 / 06 / 09: ELEVATION 3
- A-07 / 07 / 09: ELEVATION 4
- A-08 / 08 / 09: SECTION A
- A-09 / 09 / 11: SECTION B
- A-10 / 10 / 11: 3D ISOMETRIC VIEW
- A-11 / 11 / 11: 3D PERSPECTIVE VIEW

| Layer | Use |
| --- | --- |
| A-GRID | Structural grid centerlines and grid bubbles |
| A-COLUMN | Reinforced concrete column symbols |
| A-WALL | Exterior and interior architectural walls |
| A-DOOR | Door leaves and swing arcs |
| A-WINDOW | Window symbols |
| A-STAIR | Stair outlines, steps, and UP/DN text |
| A-FURN | Furniture, parking/car symbols, storage shelves |
| A-SANITARY | Bathroom and plumbing fixture symbols |
| A-DIMS | Dimension lines, ticks, and dimension text |
| A-TEXT | Room names, plan titles, scale labels |
| A-ANNO | General notes and construction annotations |
| A-ROOF | Dashed roof/eave projection outline |
| A-TITLE | Sheet border and title block |
| A-HATCH | Hatch/poche placeholder |
| 3D-WALL | Schematic 3D wall faces |
| 3D-COLUMN | Schematic 3D column faces |
| 3D-SLAB | Schematic 3D slab/floor faces |
| 3D-ROOF | Schematic 3D hip roof faces |
| 3D-VIEW | 2D projected isometric/perspective view linework |
| DEFPOINTS | Reference points |

Structural grid:
- Main footprint: 16.00 m x 14.00 m
- X bays: 2.00 + 3.00 + 3.00 + 4.00 + 2.00 + 2.00 = 16.00 m
- Y bays: 2.00 + 4.00 + 4.50 + 3.50 = 14.00 m
- Column centerlines align on both floors.
- Wall hatches use ANSI31 on A-HATCH.
- RC columns use solid hatch on A-HATCH.
- Roof, elevations, and sections include material hatch conventions for schematic construction drawing review.
- Elevations and sections include grid bubbles, grid extension lines, grid-to-grid dimensions, and level notes.

A3 sheet frame:
- Model space plotting setup: A3 landscape at 1:100
- Frame size in model units: 42.00 m x 29.70 m
- Paper equivalent: 420 mm x 297 mm
- Layout tabs: A-01 through A-11, each with an A3 landscape viewport at 1:100.
- Schematic 3D DXF model is placed in model space at X=60.
- A-10 and A-11 contain plotted 2D line projections for isometric and perspective previews.
