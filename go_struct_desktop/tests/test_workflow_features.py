from __future__ import annotations

import json
import csv
import zipfile
from pathlib import Path

import pytest

from go_struct_core import analyze_frame_data, build_frame_matrix_view, build_frame_postprocess
from go_struct_core.preflight import check_frame_model
from go_struct_desktop.reporting import ReportOptions, available_report_selections, build_html_report, report_result_tables, truss_axial_extrema, write_csv_bundle, write_html_report, write_xlsx


FIXTURE = Path(__file__).parent / "fixtures" / "portal_frame.json"


def portal_model() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_preflight_flags_unrestrained_and_invalid_spring() -> None:
    model = portal_model()
    for node in model["nodes"]:
        node["support"] = "Free"
    issues = check_frame_model(model)
    assert any(item["severity"] == "error" and "no restraints" in item["message"] for item in issues)

    model = portal_model()
    model["nodes"][0].update({"support": "Spring", "kx": 0.0, "ky": 0.0, "kr": 0.0})
    issues = check_frame_model(model)
    assert any("spring support" in item["message"].lower() for item in issues)


def test_partial_distributed_load_solves_and_flows_to_postprocess() -> None:
    model = portal_model()
    model["eloads"] = [{"elem": 3, "lcase": "DL", "dir": "Global Y", "w1": -20.0, "w2": -20.0, "x1_m": 0.5, "x2_m": 3.5}]
    result = analyze_frame_data(model)
    assert result["ok"] is True
    member = next(item for item in build_frame_postprocess(model, result)["cases"]["DL"]["members"] if item["id"] == 3)
    assert member["points"][0]["v_kg"] == pytest.approx(member["end_actions"]["v_i"])
    assert "stress_top_kg_cm2" in member["points"][0]


def test_matrix_view_has_case_combo_and_no_envelope() -> None:
    model = portal_model()
    result = analyze_frame_data(model)
    view = build_frame_matrix_view(model, result)
    assert "case:DL" in view["selections"]
    assert "combo:ULS" in view["selections"]
    assert "envelope" not in view["selections"]
    assert max(abs(value) for value in view["selections"]["case:DL"]["free_residual"]) < 1.0e-5


def test_report_exports_are_portable(tmp_path: Path) -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    html_path = tmp_path / "report.html"
    xlsx_path = tmp_path / "results.xlsx"
    write_html_report(html_path, model, analysis, "combo:ULS")
    write_xlsx(xlsx_path, model, analysis, "combo:ULS")
    csv_paths = write_csv_bundle(tmp_path / "csv", model, analysis, "combo:ULS")
    assert "GO Struct Analysis Report" in html_path.read_text(encoding="utf-8")
    assert len(csv_paths) == 3 and all(path.exists() for path in csv_paths)
    expected_nodes = report_result_tables(model, analysis, "combo:ULS")["Nodes"]
    with (tmp_path / "csv" / "nodes.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.reader(stream)) == expected_nodes[0]
    with zipfile.ZipFile(xlsx_path) as archive:
        assert "xl/workbook.xml" in archive.namelist()
        assert b"Ux (mm)" in archive.read("xl/worksheets/sheet2.xml")


def test_html_report_can_include_selected_canvas_and_engineering_schedules() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    options = ReportOptions(selections=("case:DL", "combo:ULS"), include_canvas=True)

    report = build_html_report(
        model,
        analysis,
        options.selections,
        options=options,
        canvas_images={"case:DL": {"Model": "aGVsbG8=", "N": "aGVsbG8=", "V": "aGVsbG8=", "M": "aGVsbG8=", "D": "aGVsbG8=", "FBD": "aGVsbG8="}},
    )

    assert available_report_selections(analysis) == tuple(f"case:{name}" for name in analysis["cases"]) + tuple(f"combo:{name}" for name in analysis["combos"])
    assert report.count("data:image/png;base64,aGVsbG8=") == 6
    assert "Model view: case:DL" in report and "FBD view: case:DL" in report
    assert "width:460px" in report and "@page{size:A4;margin:14mm}" in report
    assert "Node Schedule" in report
    assert "Results: combo:ULS" in report


def test_html_report_keeps_current_canvas_figures_when_tables_cover_other_results() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    options = ReportOptions(
        selections=("case:DL", "combo:ULS"),
        include_canvas=True,
        figure_scope="current_full",
        figure_views=("Model", "D"),
    )

    report = build_html_report(
        model,
        analysis,
        options.selections,
        options=options,
        canvas_images={"envelope": {"Model": "aGVsbG8=", "D": "aGVsbG8="}},
    )

    assert "Canvas views: envelope" in report
    assert report.count("data:image/png;base64,aGVsbG8=") == 2


def test_report_result_tables_use_four_decimals_and_mm_displacements() -> None:
    model = portal_model()
    analysis = analyze_frame_data(model)
    tables = report_result_tables(model, analysis, "combo:ULS")

    assert "Ux (mm)" in tables["Nodes"][0]
    assert len(tables["Nodes"][1][1].split(".")[1]) == 4
    assert len(tables["Nodes"][1][3].split(".")[1]) == 4
    assert len(tables["Members"][1][3].split(".")[1]) == 4


def test_hybrid_truss_report_identifies_maximum_tension_and_compression() -> None:
    model = portal_model()
    model["elements"][0]["memberType"] = "Truss"
    model["elements"][1]["memberType"] = "Truss"
    analysis = analyze_frame_data(model)

    rows = truss_axial_extrema(model, analysis, "case:DL")

    assert rows[0][0] == "State"
    assert any("tension" in str(row[0]).lower() or "compression" in str(row[0]).lower() for row in rows[1:])
