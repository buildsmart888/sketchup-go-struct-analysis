"""Analysis-ready Frame-Truss starters for roof systems carried by columns."""

from __future__ import annotations

from typing import Any

from .truss_profiles import PROFILE_KINDS, WEB_PATTERNS, profile_truss_geometry


def hybrid_truss_on_columns_template(
    kind: str = "gable",
    panel_count: int = 4,
    panel_m: float = 3.0,
    depth_m: float = 1.5,
    rise_m: float = 1.5,
    bottom_rise_m: float = 0.75,
    column_height_m: float = 5.0,
    column_material: str = "Steel",
    web_pattern: str = "pratt",
) -> dict[str, Any]:
    """Create a Frame-column / pin-jointed-Truss roof model in one solveable project."""

    if kind not in PROFILE_KINDS:
        raise ValueError(f"Unsupported hybrid truss profile {kind!r}")
    if web_pattern not in WEB_PATTERNS:
        raise ValueError(f"Unsupported truss web pattern {web_pattern!r}")
    if column_height_m <= 0.0:
        raise ValueError("Column height must be greater than zero")
    material = str(column_material).strip().title()
    if material not in {"Steel", "Concrete"}:
        raise ValueError("Column material must be Steel or Concrete")
    columns = {
        "Steel": {"e": 2.0e9, "a": 1800.0, "i": 500000.0, "density": 7850.0, "name": "Steel Column", "material": "Steel", "width_cm": 25.0, "depth_cm": 25.0},
        "Concrete": {"e": 1.5e9, "a": 2500.0, "i": 520833.333, "density": 2400.0, "name": "Concrete Column", "material": "Concrete", "width_cm": 30.0, "depth_cm": 30.0},
    }[material]
    nodes, elements = profile_truss_geometry(
        kind,
        panel_count,
        panel_m,
        depth_m,
        rise_m,
        bottom_rise_m,
        base_y=column_height_m,
        top_section=1,
        bottom_section=2,
        web_section=3,
        member_type="Truss",
        end_supports=False,
        web_pattern=web_pattern,
    )
    panel_nodes = panel_count + 1
    left_base_id = len(nodes) + 1
    right_base_id = left_base_id + 1
    span = panel_count * panel_m
    nodes.extend(
        [
            {"id": left_base_id, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": right_base_id, "x": span, "y": 0.0, "support": "Fixed"},
        ]
    )
    elements.extend(
        [
            {"id": len(elements) + 1, "n1": left_base_id, "n2": 1, "sec": 4, "release": "Rigid-Rigid"},
            {"id": len(elements) + 2, "n1": right_base_id, "n2": panel_nodes, "sec": 4, "release": "Rigid-Rigid"},
        ]
    )
    loaded_top_nodes = [panel_nodes + index + 1 for index in range(1, panel_count)]
    return {
        "projectInfo": {
            "name": f"Hybrid {kind.replace('_', ' ').title()} Truss on {material} Columns",
            "analysisType": "Hybrid Frame-Truss",
            "units": "legacy_kg_m",
            "hybridTemplate": {
                "kind": kind,
                "panel_count": panel_count,
                "panel_m": panel_m,
                "depth_m": depth_m,
                "rise_m": rise_m,
                "bottom_rise_m": bottom_rise_m,
                "column_height_m": column_height_m,
                "column_material": material,
                "web_pattern": web_pattern,
                "dimension": "2D",
                "support_placement": "bottom_chord",
                "joint_model": "pinned",
            },
        },
        "settings": {"include_self_weight": False},
        "nodes": nodes,
        "sections": [
            {"id": 1, "e": 2.0e9, "a": 1200.0, "i": 1.0, "density": 7850.0, "name": "Top Chord", "material": "Steel"},
            {"id": 2, "e": 2.0e9, "a": 1100.0, "i": 1.0, "density": 7850.0, "name": "Bottom Chord", "material": "Steel"},
            {"id": 3, "e": 2.0e9, "a": 700.0, "i": 1.0, "density": 7850.0, "name": "Web / Brace", "material": "Steel"},
            {"id": 4, **columns},
        ],
        "elements": elements,
        "loadcases": ["DL", "LL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0, "LL": 1.0}}, {"name": "ULS", "factors": {"DL": 1.2, "LL": 1.6}}],
        "nloads": [{"node": node_id, "lcase": "DL", "fx": 0.0, "fy": -8.0, "mz": 0.0} for node_id in loaded_top_nodes],
        "eloads": [],
    }
