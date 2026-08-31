from __future__ import annotations

import pytest

from go_struct_core import FrameModel, analyze_frame_data, build_frame_matrix_view, build_frame_postprocess
from go_struct_desktop.hybrid_templates import hybrid_truss_on_columns_template
from go_struct_desktop.truss_templates import profiled_truss_template


PROFILE_KINDS = ("flat", "sloping", "mono", "gable", "raised_bottom", "curved")
WEB_PATTERNS = ("pratt", "howe", "warren", "x")


@pytest.mark.parametrize("kind", PROFILE_KINDS)
def test_profiled_truss_forms_are_valid_geometry(kind: str) -> None:
    model = profiled_truss_template(kind, panel_count=4)

    normalized = FrameModel.from_dict(model).to_dict()
    result = analyze_frame_data(normalized)

    assert result["ok"] is True
    assert {element.get("memberType") for element in normalized["elements"]} == {"Truss"}
    assert normalized["projectInfo"]["trussTemplate"]["kind"] == kind


@pytest.mark.parametrize("kind", PROFILE_KINDS)
def test_hybrid_profiles_solve_with_axial_only_truss_and_frame_columns(kind: str) -> None:
    model = hybrid_truss_on_columns_template(kind, panel_count=4, column_material="Concrete")
    result = analyze_frame_data(model)
    postprocess = build_frame_postprocess(model, result)

    assert result["ok"] is True
    assert result["analysisType"] == "Hybrid Frame-Truss"
    assert model["sections"][-1]["material"] == "Concrete"
    truss_results = [element for element in result["cases"]["DL"]["elements"] if element["memberType"] == "Truss"]
    frame_results = [element for element in result["cases"]["DL"]["elements"] if element["memberType"] == "Frame"]
    assert truss_results and len(frame_results) == 2
    assert all(element["n1_forces"]["shear"] == 0.0 and element["n1_forces"]["moment"] == 0.0 for element in truss_results)
    assert all(member["memberType"] == "Truss" for member in postprocess["cases"]["DL"]["members"] if member["id"] in {item["id"] for item in truss_results})
    applied_vertical = sum(float(load["fy"]) for load in model["nloads"] if load["lcase"] == "DL")
    reaction_vertical = sum(float(node["fy"]) for node in result["cases"]["DL"]["nodes"])
    assert reaction_vertical + applied_vertical == pytest.approx(0.0, abs=1.0e-8)


@pytest.mark.parametrize("web_pattern", WEB_PATTERNS)
def test_profiled_and_hybrid_templates_preserve_selectable_web_patterns(web_pattern: str) -> None:
    truss = profiled_truss_template("gable", panel_count=4, web_pattern=web_pattern)
    hybrid = hybrid_truss_on_columns_template("gable", panel_count=4, web_pattern=web_pattern)

    assert analyze_frame_data(truss)["ok"] is True
    assert analyze_frame_data(hybrid)["ok"] is True
    assert truss["projectInfo"]["trussTemplate"]["web_pattern"] == web_pattern
    assert truss["projectInfo"]["trussTemplate"]["dimension"] == "2D"
    assert hybrid["projectInfo"]["hybridTemplate"]["web_pattern"] == web_pattern
    assert hybrid["projectInfo"]["hybridTemplate"]["joint_model"] == "pinned"


def test_hybrid_matrix_uses_axial_only_stiffness_for_truss_members() -> None:
    model = hybrid_truss_on_columns_template("gable")
    analysis = analyze_frame_data(model)
    matrix = build_frame_matrix_view(model, analysis)

    truss = next(member for member in matrix["members"] if member["memberType"] == "Truss")
    frame = next(member for member in matrix["members"] if member["memberType"] == "Frame")

    assert truss["local_stiffness"][0][0] > 0.0
    assert truss["local_stiffness"][1][1] == 0.0
    assert truss["local_stiffness"][2][2] == 0.0
    assert frame["local_stiffness"][2][2] > 0.0


def test_hybrid_validation_rejects_truss_member_loads_releases_and_unstiffened_moments() -> None:
    member_load = hybrid_truss_on_columns_template("flat")
    truss_id = next(element["id"] for element in member_load["elements"] if element.get("memberType") == "Truss")
    member_load["eloads"] = [{"elem": truss_id, "lcase": "DL", "dir": "Global Y", "w1": -1.0, "w2": -1.0}]
    assert "member loads" in analyze_frame_data(member_load)["error"]

    release = hybrid_truss_on_columns_template("flat")
    next(element for element in release["elements"] if element.get("memberType") == "Truss")["release"] = "Rigid-Pin"
    assert "cannot use a frame end release" in analyze_frame_data(release)["error"]

    moment = hybrid_truss_on_columns_template("flat")
    top_node = max(moment["nodes"], key=lambda node: float(node["y"]))
    moment["nloads"].append({"node": top_node["id"], "lcase": "DL", "fx": 0.0, "fy": 0.0, "mz": 10.0})
    assert "unsupported hybrid DOF" in analyze_frame_data(moment)["error"]
