from __future__ import annotations

import pytest

from go_struct_core import BeamModel, analyze_beam_data, build_frame_postprocess
from go_struct_desktop.examples import BUILT_IN_BEAM_EXAMPLES


def beam_model() -> dict:
    return {
        "projectInfo": {"name": "Beam benchmark", "analysisType": "Beam"},
        "settings": {"include_self_weight": False},
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "support": "Fixed"},
            {"id": 2, "x": 6.0, "y": 0.0, "support": "Free"},
        ],
        "sections": [{"id": 1, "e": 2.0e9, "a": 1000.0, "i": 1000000.0, "density": 0.0}],
        "elements": [{"id": 1, "n1": 1, "n2": 2, "sec": 1, "release": "Rigid-Rigid"}],
        "loadcases": ["DL", "LL"],
        "loadcombos": [{"name": "Service", "factors": {"DL": 1.0, "LL": 1.0}}, {"name": "ULS", "factors": {"DL": 1.2, "LL": 1.6}}],
        "nloads": [{"node": 2, "lcase": "DL", "fx": 0.0, "fy": -10.0, "mz": 0.0}],
        "eloads": [],
    }


def test_beam_cantilever_matches_closed_form_reaction_and_deflection() -> None:
    model = beam_model()
    result = analyze_beam_data(model)

    expected = -10.0 * 6.0**3 / (3.0 * 2.0e9 * 0.01)
    assert result["ok"] is True
    assert result["analysisType"] == "Beam"
    assert result["cases"]["DL"]["nodes"][1]["dy"] == pytest.approx(expected, rel=1e-11)
    assert result["cases"]["DL"]["nodes"][0]["fy"] == pytest.approx(10.0)
    assert result["cases"]["DL"]["nodes"][0]["mz"] == pytest.approx(60.0)


def test_beam_support_reactions_and_combinations_are_linear() -> None:
    model = beam_model()
    model["nodes"] = [
        {"id": 1, "x": 0.0, "y": 0.0, "support": "Pinned"},
        {"id": 2, "x": 8.0, "y": 0.0, "support": "RollerX"},
    ]
    model["nloads"] = []
    model["eloads"] = [
        {"elem": 1, "lcase": "DL", "type": "Distributed", "dir": "Global Y", "w1": -8.0, "w2": -8.0},
        {"elem": 1, "lcase": "LL", "type": "Point Force", "dir": "Local Y", "x_m": 2.0, "p": -12.0},
    ]
    result = analyze_beam_data(model)

    assert result["ok"] is True
    dl, ll, uls = result["cases"]["DL"], result["cases"]["LL"], result["combos"]["ULS"]
    assert dl["nodes"][0]["fy"] == pytest.approx(32.0)
    assert dl["nodes"][1]["fy"] == pytest.approx(32.0)
    assert sum(node["fy"] for node in ll["nodes"]) == pytest.approx(12.0)
    assert uls["nodes"][0]["fy"] == pytest.approx(1.2 * dl["nodes"][0]["fy"] + 1.6 * ll["nodes"][0]["fy"])


def test_beam_postprocess_reuses_shared_v_m_and_deflection_contract() -> None:
    model = beam_model()
    analysis = analyze_beam_data(model)
    postprocess = build_frame_postprocess(model, analysis)

    member = postprocess["cases"]["DL"]["members"][0]
    assert postprocess["ok"] is True
    assert member["points"][0]["v_kg"] == pytest.approx(member["end_actions"]["v_i"])
    assert member["points"][-1]["m_kg_m"] == pytest.approx(member["end_actions"]["m_j"])


def test_beam_rejects_nonhorizontal_members_and_axial_loads() -> None:
    tilted = beam_model()
    tilted["nodes"][1]["y"] = 1.0
    with pytest.raises(Exception, match="horizontal"):
        BeamModel.from_dict(tilted)

    axial = beam_model()
    axial["nloads"][0]["fx"] = 1.0
    result = analyze_beam_data(axial)
    assert result["ok"] is False
    assert "cannot use Fx" in result["error"]


def test_builtin_beam_examples_are_valid_and_analysis_ready() -> None:
    assert len(BUILT_IN_BEAM_EXAMPLES) == 4
    for example in BUILT_IN_BEAM_EXAMPLES:
        assert BeamModel.from_dict(example.model()).to_dict()["projectInfo"]["analysisType"] == "Beam"
        assert analyze_beam_data(example.model())["ok"] is True, example.title
