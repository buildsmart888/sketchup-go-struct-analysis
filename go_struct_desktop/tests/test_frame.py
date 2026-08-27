from __future__ import annotations

import json
from pathlib import Path

import pytest

from go_struct_core import FrameModel, analyze_frame_data


FIXTURE = Path(__file__).parent / "fixtures" / "portal_frame.json"


def load_portal() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def cantilever_model() -> dict:
    return {
        "settings": {"include_self_weight": False},
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 0.0, "y": 3.0, "support": "Free"},
        ],
        "sections": [{"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1000000.0, "density": 0.0}],
        "elements": [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
        "loadcases": ["DL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0}}],
        "nloads": [{"node": 2, "lcase": "DL", "fx": 10.0, "fy": 0.0, "mz": 0.0}],
        "eloads": [],
    }


def test_cantilever_displacement_matches_closed_form() -> None:
    result = analyze_frame_data(cantilever_model())

    assert result["ok"] is True
    expected_dx = 10.0 * 3.0**3 / (3.0 * 2.0e9 * (1000000.0 * 1.0e-8))
    assert result["combos"]["Service"]["nodes"][1]["dx"] == pytest.approx(expected_dx, rel=1e-10)
    assert result["combos"]["Service"]["nodes"][1]["dy"] == pytest.approx(0.0, abs=1e-12)


def test_portal_frame_combinations_are_linear_and_equilibrated() -> None:
    model = load_portal()
    result = analyze_frame_data(model)

    assert result["ok"] is True
    dl = result["cases"]["DL"]
    ll = result["cases"]["LL"]
    uls = result["combos"]["ULS"]
    for index in range(len(model["nodes"])):
        assert uls["nodes"][index]["dx"] == pytest.approx(1.2 * dl["nodes"][index]["dx"] + 1.6 * ll["nodes"][index]["dx"])
        assert uls["nodes"][index]["dy"] == pytest.approx(1.2 * dl["nodes"][index]["dy"] + 1.6 * ll["nodes"][index]["dy"])

    applied_vertical = sum(load["w1"] * 4.0 for load in model["eloads"] if load["lcase"] == "DL")
    reaction_vertical = sum(node["fy"] for node in dl["nodes"])
    assert reaction_vertical + applied_vertical == pytest.approx(0.0, abs=1e-8)


def test_equation_style_combination_matches_factor_object() -> None:
    model = load_portal()
    model["loadcombos"] = [
        {"name": "By equation", "eq": "1.2DL + 1.6LL"},
        {"name": "By factors", "factors": {"DL": 1.2, "LL": 1.6}},
    ]
    result = analyze_frame_data(model)

    equation = result["combos"]["By equation"]
    factors = result["combos"]["By factors"]
    assert equation["nodes"][2]["dx"] == pytest.approx(factors["nodes"][2]["dx"])
    assert equation["elements"][2]["n1_forces"]["moment"] == pytest.approx(factors["elements"][2]["n1_forces"]["moment"])


def test_invalid_references_return_json_errors_without_throwing() -> None:
    model = load_portal()
    model["elements"][0]["sec"] = 999

    result = analyze_frame_data(model)

    assert result["ok"] is False
    assert "missing section" in result["error"]


def test_schema_accepts_legacy_uniform_load_w_field() -> None:
    model = cantilever_model()
    model["eloads"] = [{"elem": 1, "lcase": "DL", "dir": "Local Y", "w": -4.0}]

    parsed = FrameModel.from_dict(model)

    assert parsed.element_loads[0].w1 == -4.0
    assert parsed.element_loads[0].w2 == -4.0


def test_schema_round_trips_to_go_frame_json_shape() -> None:
    parsed = FrameModel.from_dict(load_portal())
    serialized = parsed.to_dict()

    assert serialized["nodes"] == load_portal()["nodes"]
    assert serialized["elements"] == load_portal()["elements"]
    assert serialized["sections"] == load_portal()["sections"]
    assert json.loads(json.dumps(serialized)) == serialized
