from __future__ import annotations

import json
from pathlib import Path

import pytest

from go_struct_core import analyze_frame_data, build_frame_postprocess


FIXTURE = Path(__file__).parent / "fixtures" / "portal_frame.json"


def portal_model() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_member_diagram_matches_member_end_actions() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    postprocess = build_frame_postprocess(model, analysis)
    member = next(item for item in postprocess["combos"]["ULS"]["members"] if item["id"] == 3)

    assert postprocess["ok"] is True
    assert len(member["points"]) == 41
    assert member["points"][0]["n_kg"] == pytest.approx(member["end_actions"]["n_i"])
    assert member["points"][0]["v_kg"] == pytest.approx(member["end_actions"]["v_i"])
    assert member["points"][0]["m_kg_m"] == pytest.approx(member["end_actions"]["m_i"])
    assert member["points"][-1]["n_kg"] == pytest.approx(member["end_actions"]["n_j"])
    assert member["points"][-1]["v_kg"] == pytest.approx(member["end_actions"]["v_j"])
    assert member["points"][-1]["m_kg_m"] == pytest.approx(member["end_actions"]["m_j"])


def test_deformed_curve_hits_solved_node_positions() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    postprocess = build_frame_postprocess(model, analysis)
    member = next(item for item in postprocess["combos"]["ULS"]["members"] if item["id"] == 3)
    combo_nodes = {node["id"]: node for node in analysis["combos"]["ULS"]["nodes"]}

    first, last = member["points"][0], member["points"][-1]
    assert first["x_deformed_m"] == pytest.approx(combo_nodes[3]["x"] + combo_nodes[3]["dx"])
    assert first["y_deformed_m"] == pytest.approx(combo_nodes[3]["y"] + combo_nodes[3]["dy"])
    assert last["x_deformed_m"] == pytest.approx(combo_nodes[4]["x"] + combo_nodes[4]["dx"])
    assert last["y_deformed_m"] == pytest.approx(combo_nodes[4]["y"] + combo_nodes[4]["dy"])


def test_postprocess_envelope_records_governing_combination_and_equilibrium() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    postprocess = build_frame_postprocess(model, analysis)
    point = postprocess["envelope"]["members"][0]["points"][0]

    assert point["m_kg_m_combo"] in {"Service", "ULS"}
    assert point["deformation_combo"] in {"Service", "ULS"}
    assert postprocess["envelope"]["members"][0]["extrema"]["m_kg_m"]["abs"]["combo"] in {"Service", "ULS"}
    assert all(check["ok"] for check in postprocess["diagnostics"]["equilibrium"])


def test_diagnostics_warn_about_duplicate_and_crossing_geometry() -> None:
    model = portal_model()
    model["nodes"].extend(
        [
            {"id": 5, "x": 0.0, "y": 0.0, "support": "Free"},
            {"id": 6, "x": 3.0, "y": -1.0, "support": "Free"},
            {"id": 7, "x": 3.0, "y": 5.0, "support": "Free"},
        ]
    )
    model["elements"].extend(
        [
            {"id": 4, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 5, "n1": 6, "n2": 7, "sec": 1, "release": "Rigid-Rigid"},
        ]
    )

    items = build_frame_postprocess(model, analyze_frame_data(model))["diagnostics"]["items"]
    messages = "\n".join(item["message"] for item in items)

    assert "share coordinates" in messages
    assert "duplicate" in messages
    assert "intersect" in messages
