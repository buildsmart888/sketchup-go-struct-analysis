from __future__ import annotations

import json
from pathlib import Path

import pytest

from go_struct_core import FrameModel, analyze_frame_data, build_frame_postprocess
from go_struct_desktop.examples import BUILT_IN_FRAME_EXAMPLES, ENGILAB_REFERENCE_EXAMPLES, FRAME_EXAMPLES
from go_struct_desktop.engilab import import_engilab_frame, installed_example_files


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


def test_all_builtin_examples_are_valid_and_analysis_ready() -> None:
    assert len(BUILT_IN_FRAME_EXAMPLES) == 5
    assert len(ENGILAB_REFERENCE_EXAMPLES) == 5
    assert len(FRAME_EXAMPLES) == 10
    titles = " ".join(example.title for example in BUILT_IN_FRAME_EXAMPLES).lower()
    for keyword in ("cantilever", "simply supported", "portal", "released", "reaction"):
        assert keyword in titles
    for example in FRAME_EXAMPLES:
        model = example.model()
        assert FrameModel.from_dict(model).to_dict()["projectInfo"]["name"]
        assert analyze_frame_data(model)["ok"] is True, example.title


def test_all_installed_engilab_examples_import_and_analyze_when_available() -> None:
    files = installed_example_files()
    if not files:
        pytest.skip("EngiLab Frame.2D examples are not installed on this host")
    assert len(files) == 18
    for path in files:
        imported = import_engilab_frame(path)
        assert FrameModel.from_dict(imported.model).to_dict()["projectInfo"]["sourceFile"] == path.name
        assert analyze_frame_data(imported.model)["ok"] is True, path.name


def test_simply_supported_uniform_load_reactions_and_fe_deflection_are_stable() -> None:
    model = cantilever_model()
    model["nodes"] = [
        {"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"},
        {"id": 2, "x": 6.0, "y": 0.0, "support": "RollerX"},
    ]
    model["elements"][0] = {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}
    model["nloads"] = []
    model["eloads"] = [{"elem": 1, "lcase": "DL", "dir": "Global Y", "w1": -8.0, "w2": -8.0}]

    result = analyze_frame_data(model)

    postprocess = build_frame_postprocess(model, result)
    midspan = min(postprocess["cases"]["DL"]["members"][0]["points"], key=lambda point: abs(float(point["x_m"]) - 3.0))
    assert result["ok"] is True
    assert result["cases"]["DL"]["nodes"][0]["fy"] == pytest.approx(24.0)
    assert result["cases"]["DL"]["nodes"][1]["fy"] == pytest.approx(24.0)
    # A single Euler-Bernoulli element gives a cubic FE interpolation of the exact quartic UDL curve.
    assert midspan["v_mm"] / 1000.0 == pytest.approx(-5.4e-6, rel=1e-10)


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


def test_member_point_force_matches_cantilever_closed_form_and_diagram_jump() -> None:
    model = cantilever_model()
    model["nodes"][1] = {"id": 2, "x": 6.0, "y": 0.0, "support": "Free"}
    model["elements"][0] = {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}
    model["nloads"] = []
    model["eloads"] = [{"elem": 1, "lcase": "DL", "type": "Point Force", "dir": "Local Y", "x_m": 3.0, "p": -10.0}]

    result = analyze_frame_data(model)
    postprocess = build_frame_postprocess(model, result)
    member = postprocess["cases"]["DL"]["members"][0]

    expected_tip_dy = -10.0 * 3.0**2 * (3.0 * 6.0 - 3.0) / (6.0 * 2.0e9 * (1000000.0 * 1.0e-8))
    assert result["ok"] is True
    assert result["cases"]["DL"]["nodes"][1]["dy"] == pytest.approx(expected_tip_dy, rel=1e-10)
    assert result["cases"]["DL"]["nodes"][0]["fy"] == pytest.approx(10.0)
    assert result["cases"]["DL"]["nodes"][0]["mz"] == pytest.approx(30.0)
    assert member["endpoint_residual"]["v_kg"] == pytest.approx(0.0, abs=1e-9)
    assert member["point_loads"] == [{"case": "DL", "type": "Point Force", "x_m": 3.0, "px_kg": 0.0, "py_kg": -10.0, "mz_kg_m": 0.0}]


def test_member_point_moment_creates_a_moment_diagram_jump() -> None:
    model = cantilever_model()
    model["nodes"][1] = {"id": 2, "x": 6.0, "y": 0.0, "support": "Free"}
    model["elements"][0] = {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}
    model["nloads"] = []
    model["eloads"] = [{"elem": 1, "lcase": "DL", "type": "Point Moment", "x_m": 3.0, "m": 10.0}]

    result = analyze_frame_data(model)
    member = build_frame_postprocess(model, result)["cases"]["DL"]["members"][0]

    assert result["ok"] is True
    assert result["cases"]["DL"]["nodes"][0]["mz"] == pytest.approx(-10.0)
    assert member["end_actions"]["m_i"] == pytest.approx(10.0)
    assert member["end_actions"]["m_j"] == pytest.approx(0.0, abs=1e-9)
    assert member["endpoint_residual"]["m_kg_m"] == pytest.approx(0.0, abs=1e-9)


def test_member_point_load_requires_a_position_on_the_member() -> None:
    model = cantilever_model()
    model["eloads"] = [{"elem": 1, "lcase": "DL", "type": "Point Force", "dir": "Local Y", "x_m": 4.0, "p": -10.0}]

    result = analyze_frame_data(model)

    assert result["ok"] is False
    assert "requires x_m between" in result["error"]


def test_envelope_keeps_point_load_sampling_positions_for_zero_factor_combinations() -> None:
    model = cantilever_model()
    model["loadcases"] = ["DL", "LL"]
    model["loadcombos"] = [{"name": "DL only", "factors": {"DL": 1.0}}, {"name": "LL only", "factors": {"LL": 1.0}}]
    model["nloads"] = []
    model["eloads"] = [{"elem": 1, "lcase": "LL", "type": "Point Force", "dir": "Local Y", "x_m": 1.5, "p": -10.0}]

    postprocess = build_frame_postprocess(model, analyze_frame_data(model))

    for selection in (*postprocess["combos"].values(), postprocess["envelope"]):
        assert any(point["x_m"] == pytest.approx(1.5) for point in selection["members"][0]["points"])


def test_global_x_member_point_force_is_transformed_to_local_axial_load() -> None:
    model = cantilever_model()
    model["nodes"][1] = {"id": 2, "x": 3.0, "y": 0.0, "support": "Free"}
    model["elements"][0] = {"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}
    model["nloads"] = []
    model["eloads"] = [{"elem": 1, "lcase": "DL", "type": "Point Force", "dir": "Global X", "x_m": 1.5, "p": 10.0}]

    result = analyze_frame_data(model)

    expected_dx = 10.0 * 1.5 / (2.0e9 * (1000.0 * 1.0e-4))
    assert result["ok"] is True
    assert result["cases"]["DL"]["nodes"][1]["dx"] == pytest.approx(expected_dx, rel=1e-10)
    assert result["cases"]["DL"]["nodes"][0]["fx"] == pytest.approx(-10.0)
