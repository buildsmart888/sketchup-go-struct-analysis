from __future__ import annotations

import math

import pytest

from go_struct_core import TrussModel, analyze_truss_data, build_frame_postprocess
from go_struct_desktop.truss_templates import howe_truss_template, pratt_truss_template, roof_truss_template, triangle_truss_template, warren_truss_template


def triangle_truss() -> dict:
    return {
        "projectInfo": {"name": "Triangle truss", "analysisType": "Truss"},
        "settings": {"include_self_weight": False},
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"},
            {"id": 2, "x": 4.0, "y": 0.0, "support": "RollerX"},
            {"id": 3, "x": 2.0, "y": 3.0, "support": "Free"},
        ],
        "sections": [{"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1.0, "density": 0.0}],
        "elements": [
            {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 2, "n1": 1, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
            {"id": 3, "n1": 2, "n2": 3, "sec": 1, "release": "Rigid-Rigid"},
        ],
        "loadcases": ["DL", "WL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0, "WL": 1.0}}, {"name": "ULS", "factors": {"DL": 1.2, "WL": 1.6}}],
        "nloads": [{"node": 3, "lcase": "DL", "fx": 0.0, "fy": -10.0, "mz": 0.0}, {"node": 3, "lcase": "WL", "fx": 3.0, "fy": 0.0, "mz": 0.0}],
        "eloads": [],
    }


def test_triangle_truss_reactions_and_member_states_match_statics() -> None:
    result = analyze_truss_data(triangle_truss())

    expected_diagonal = -10.0 * math.sqrt(13.0) / 6.0
    assert result["ok"] is True
    assert result["analysisType"] == "Truss"
    dl = result["cases"]["DL"]
    assert dl["nodes"][0]["fy"] == pytest.approx(5.0)
    assert dl["nodes"][1]["fy"] == pytest.approx(5.0)
    assert dl["elements"][1]["n1_forces"]["axial"] == pytest.approx(expected_diagonal)
    assert dl["elements"][2]["n1_forces"]["axial"] == pytest.approx(expected_diagonal)


def test_truss_combinations_are_linear_and_postprocess_can_render_axial_results() -> None:
    model = triangle_truss()
    result = analyze_truss_data(model)
    postprocess = build_frame_postprocess(model, result)

    service = result["combos"]["Service"]
    for index in range(3):
        assert service["nodes"][index]["dx"] == pytest.approx(result["cases"]["DL"]["nodes"][index]["dx"] + result["cases"]["WL"]["nodes"][index]["dx"])
    assert postprocess["ok"] is True
    assert postprocess["cases"]["DL"]["members"][1]["points"][0]["n_kg"] < 0.0


def test_truss_rejects_member_loads_moments_and_frame_releases() -> None:
    member_load = triangle_truss()
    member_load["eloads"] = [{"elem": 1, "lcase": "DL", "dir": "Global Y", "w1": -1.0, "w2": -1.0}]
    assert "member loads" in analyze_truss_data(member_load)["error"]

    moment = triangle_truss()
    moment["nloads"][0]["mz"] = 1.0
    with pytest.raises(Exception, match="cannot use Mz"):
        TrussModel.from_dict(moment)

    release = triangle_truss()
    release["elements"][0]["release"] = "Rigid-Pin"
    assert "cannot use a frame end release" in analyze_truss_data(release)["error"]


def test_truss_sections_do_not_require_frame_inertia() -> None:
    model = triangle_truss()
    model["sections"][0].pop("i")

    normalized = TrussModel.from_dict(model).to_dict()

    assert normalized["sections"][0]["i"] == 1.0
    assert analyze_truss_data(model)["ok"] is True


def test_truss_templates_are_stable_and_ready_for_nodal_loads() -> None:
    for model in (triangle_truss_template(), warren_truss_template(4), pratt_truss_template(4), howe_truss_template(4), roof_truss_template(4)):
        assert TrussModel.from_dict(model).to_dict()["projectInfo"]["analysisType"] == "Truss"
        assert analyze_truss_data(model)["ok"] is True

    with pytest.raises(ValueError, match="at least two"):
        warren_truss_template(1)
    with pytest.raises(ValueError, match="at least two"):
        pratt_truss_template(1)
    with pytest.raises(ValueError, match="at least two"):
        howe_truss_template(1)
    with pytest.raises(ValueError, match="even number"):
        roof_truss_template(3)
