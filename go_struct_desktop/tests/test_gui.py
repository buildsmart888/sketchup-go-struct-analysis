from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QDockWidget

from go_struct_desktop.app import MainWindow
from go_struct_desktop.beam_workspace import BeamMainWindow
from go_struct_desktop.beam_canvas import BeamCanvas
from go_struct_desktop.beam_templates import simply_supported_template
from go_struct_desktop.truss_canvas import TrussCanvas
from go_struct_desktop.truss_workspace import TrussMainWindow
from go_struct_desktop.display import DisplaySettings
from go_struct_desktop.examples import FRAME_EXAMPLES
from go_struct_desktop.frame_workspace import FrameInputPanel, default_frame_model
from go_struct_desktop.template_browser import TemplateBrowserDialog, TemplateOption, TemplateParameter
from go_struct_desktop.units import get_unit_system


@pytest.fixture(scope="session")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_frame_workspace_analyzes_default_model(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.results_panel.analysis is not None
    assert window.results_panel.analysis["ok"] is True
    assert window.results_panel.result_selector.count() == 5
    assert window.results_panel.node_results.rowCount() == 4
    assert window.results_panel.member_results.rowCount() == 3
    window.results_panel.result_selector.setCurrentIndex(window.results_panel.result_selector.findData("combo:ULS"))
    app.processEvents()
    assert window.results_panel.diagrams.member_selector.count() == 3
    window.results_panel.canvas_diagram_selector.setCurrentIndex(window.results_panel.canvas_diagram_selector.findData("m_kg_m"))
    app.processEvents()
    assert window.results_panel.canvas.diagram_mode == "m_kg_m"
    assert not window.results_panel.canvas.grab().isNull()
    window.results_panel.canvas_diagram_selector.setCurrentIndex(window.results_panel.canvas_diagram_selector.findData("all"))
    app.processEvents()
    assert window.results_panel.canvas.diagram_mode == "all"
    target, _, _ = window.results_panel.canvas._hover_points[0]
    QTest.mouseMove(window.results_panel.canvas, QPoint(round(target.x()), round(target.y())))
    app.processEvents()
    assert window.results_panel.canvas.has_hover_value
    window.results_panel.diagram_values_toggle.setChecked(True)
    app.processEvents()
    assert not window.results_panel.canvas.grab().isNull()
    assert "Member calculations" in window.results_panel.calculation_details.toPlainText()
    assert not window.results_panel.diagrams.canvas.grab().isNull()
    assert not window.results_panel.canvas.grab().isNull()

    window.close()


def test_beam_workspace_opens_with_its_own_solver_and_examples(app: QApplication) -> None:
    window = BeamMainWindow()
    window.show()
    app.processEvents()

    assert "1D Beam" in window.windowTitle()
    assert window.results_panel.analysis is not None
    assert window.results_panel.analysis["ok"] is True
    assert window.results_panel.analysis["analysisType"] == "Beam"
    assert window._workspace.normalize_model(window.input_panel.model_data())["projectInfo"]["analysisType"] == "Beam"
    assert len(window._workspace.examples) == 4
    window.close()


def test_beam_canvas_locks_vertical_authoring_and_appends_spans(app: QApplication) -> None:
    window = BeamMainWindow()
    canvas = window.results_panel.canvas
    assert isinstance(canvas, BeamCanvas)

    window.input_panel.nodes.table.item(1, 2).setText("9.0")
    app.processEvents()
    table_locked = next(node for node in window.input_panel.model_data()["nodes"] if node["id"] == 2)
    assert table_locked["y"] == 0.0

    canvas._move_node(2, (4.5, 9.0))
    app.processEvents()
    moved = next(node for node in window.input_panel.model_data()["nodes"] if node["id"] == 2)
    assert (moved["x"], moved["y"]) == (4.5, 0.0)

    canvas.add_span(3.0, support="RollerX")
    app.processEvents()
    model = window.input_panel.model_data()
    added = max(model["nodes"], key=lambda node: node["id"])
    member = max(model["elements"], key=lambda item: item["id"])
    assert (added["x"], added["y"], added["support"]) == (11.0, 0.0, "RollerX")
    assert member["n2"] == added["id"]
    canvas._set_selection(set(), {1})
    canvas.resize_selected_span(4.0)
    app.processEvents()
    resized = window.input_panel.model_data()
    first_member = next(item for item in resized["elements"] if item["id"] == 1)
    nodes = {node["id"]: node for node in resized["nodes"]}
    assert nodes[first_member["n2"]]["x"] - nodes[first_member["n1"]]["x"] == pytest.approx(4.0)
    window.run_analysis()
    assert window.results_panel.analysis and window.results_panel.analysis["ok"] is True
    window.close()


def test_beam_canvas_inserts_supported_station_by_splitting_a_span(app: QApplication) -> None:
    window = BeamMainWindow()
    window.set_model(simply_supported_template(6.0))

    window.results_panel.canvas.insert_support(3.0, "RollerX")
    app.processEvents()
    model = window.input_panel.model_data()
    inserted = next(node for node in model["nodes"] if node["id"] == 3)

    assert (inserted["x"], inserted["support"]) == (3.0, "RollerX")
    assert {(member["n1"], member["n2"]) for member in model["elements"]} == {(1, 3), (3, 2)}
    window.close()


def test_truss_workspace_uses_axial_only_authoring_and_results(app: QApplication) -> None:
    window = TrussMainWindow()
    window.show()
    app.processEvents()

    assert "2D Truss" in window.windowTitle()
    assert isinstance(window.results_panel.canvas, TrussCanvas)
    assert window.results_panel.analysis and window.results_panel.analysis["analysisType"] == "Truss"
    assert not window.results_panel._tool_buttons["member_load"].isVisible()
    assert not window.diagram_buttons["v_kg"].isVisible()
    assert window.results_panel.diagrams.quantity_selector.count() == 2
    assert window.results_panel.diagrams.quantity_selector.currentData() == "n_kg"
    assert window.results_panel.diagrams.quantity_selector.itemText(window.results_panel.diagrams.quantity_selector.findData("v_mm")) == "Deflected Shape"
    assert window.diagram_buttons["v_mm"].isVisible()
    window.results_panel.canvas.set_diagram_mode("v_mm")
    assert window.results_panel.canvas.diagram_mode == "none"
    assert window.results_panel.canvas._show_deformed is True
    assert "Max tension" in window.results_panel.summary.horizontalHeaderItem(1).text()
    member_load_tab = window.input_panel.tabs.indexOf(window.input_panel.element_loads)
    assert not window.input_panel.tabs.isTabVisible(member_load_tab)
    assert window.input_panel.sections.table.isColumnHidden(3)
    assert window.input_panel.sections.table.isColumnHidden(4)
    assert not window.input_panel.self_weight.isVisible()
    assert len(window._workspace.examples) == 5
    window.results_panel.canvas.set_tool("member_load")
    assert window.results_panel.canvas.tool == "select"
    window.close()


def test_template_catalog_draws_a_dimensioned_preview_and_collects_parameters(app: QApplication) -> None:
    option = TemplateOption(
        "simple",
        "Simply Supported",
        "Pinned and roller supports.",
        "simple",
        (TemplateParameter("span_m", "Span (m)", 6.0),),
    )
    dialog = TemplateBrowserDialog("Template test", (option,))
    dialog.show()
    app.processEvents()

    assert dialog.parameters.rowCount() == 1
    assert dialog.selected_values()["span_m"] == pytest.approx(6.0)
    assert not dialog.preview.grab().isNull()
    dialog.close()


def test_model_view_draws_all_input_load_cases_while_results_uses_active_case(app: QApplication) -> None:
    window = MainWindow()
    canvas = window.results_panel.canvas

    canvas.set_view_mode("model")
    assert canvas._display_load_factors() == {"DL": 1.0, "LL": 1.0}
    canvas.set_view_mode("results")
    canvas.set_load_case("LL")
    assert canvas._display_load_factors() == {"LL": 1.0}
    assert canvas._load_case_color("DL") != canvas._load_case_color("LL")
    window.close()


def test_model_view_can_display_factored_combo_loads(app: QApplication) -> None:
    window = MainWindow()
    canvas = window.results_panel.canvas
    canvas.set_view_mode("model")
    window.display_panel.load_case.setCurrentIndex(window.display_panel.load_case.findData("combo:ULS"))

    assert canvas._display_load_factors() == {"DL": 1.2, "LL": 1.6}
    assert window.display_panel.load_case.currentText() == "Combo: ULS"
    window.close()


def test_manual_analysis_reports_completion(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow()
    shown: list[tuple[int, int, float]] = []
    monkeypatch.setattr(
        window,
        "_show_analysis_complete",
        lambda model, elapsed: shown.append((len(model["nodes"]), len(model["elements"]), elapsed)),
    )

    window.run_analysis(show_completion=True)

    assert shown and shown[0][:2] == (4, 3)
    assert shown[0][2] >= 0.0
    window.close()


def test_loading_builtin_example_applies_its_result_view(app: QApplication) -> None:
    window = MainWindow()
    reaction_example = next(example for example in FRAME_EXAMPLES if example.key == "reaction_check")

    window.load_example(reaction_example)

    assert window.results_panel.analysis is not None
    assert window.input_panel.model_data()["projectInfo"]["name"] == "Reaction Check | Two-span Beam"
    assert window.results_panel.canvas._view_mode == "fbd"
    assert window.results_panel.result_selector.currentData() == "combo:Service"
    window.close()


def test_workspace_input_and_results_are_independent_docks(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.centralWidget() is window.results_panel
    assert window.input_dock.widget() is window.input_panel
    assert window.results_dock.widget() is window.results_panel.results_tabs
    assert window.results_dock.minimumHeight() == 120
    for dock in (window.input_dock, window.results_dock):
        assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable
        assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetMovable
        assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable

    assert window.results_panel._tool_buttons["node"].parentWidget() is not window.results_panel
    assert window.results_panel.result_selector.parentWidget() is not window.results_panel
    window.close()


def test_toolbar_uses_two_fixed_rows_and_diagram_mode_buttons(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.toolBarArea(window.modeling_toolbar) == Qt.ToolBarArea.TopToolBarArea
    assert window.toolBarArea(window.analysis_toolbar) == Qt.ToolBarArea.TopToolBarArea
    assert window.analysis_toolbar.geometry().top() > window.modeling_toolbar.geometry().top()
    assert not window.results_panel.canvas_diagram_selector.isVisible()
    assert set(window.diagram_buttons) == {"none", "n_kg", "v_kg", "m_kg_m", "v_mm", "all", "fbd"}

    QTest.mouseClick(window.diagram_buttons["m_kg_m"], Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.diagram_buttons["m_kg_m"].isChecked()
    assert window.results_panel.canvas.diagram_mode == "m_kg_m"
    QTest.mouseClick(window.diagram_buttons["fbd"], Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.diagram_buttons["fbd"].isChecked()
    assert window.results_panel.canvas._view_mode == "fbd"
    QTest.mouseClick(window.diagram_buttons["n_kg"], Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.results_panel.canvas._view_mode == "results"
    assert window.results_panel.canvas.diagram_mode == "n_kg"
    window.close()


def test_frame_workspace_marks_results_stale_after_input_change(app: QApplication) -> None:
    window = MainWindow()
    app.processEvents()
    window.input_panel.set_model(default_frame_model())
    window.run_analysis()
    assert window.results_panel.analysis is not None

    item = window.input_panel.nodes.table.item(2, 1)
    item.setText("0.5")
    app.processEvents()

    assert window.results_panel.analysis is None
    window.close()


def test_canvas_creates_snapped_nodes_and_members(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas

    canvas.set_tool("node")
    node_location = canvas._model_to_screen(8.26, 0.74)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(node_location.x()), round(node_location.y())))
    app.processEvents()
    model = window.input_panel.model_data()
    assert any(node["x"] == 8.0 and node["y"] == 1.0 for node in model["nodes"])

    canvas.set_tool("member")
    start = canvas._model_to_screen(6.0, 4.0)
    end = canvas._model_to_screen(8.0, 4.0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(start.x()), round(start.y())))
    QTest.mouseMove(canvas, QPoint(round(end.x()), round(end.y())))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(end.x()), round(end.y())))
    app.processEvents()
    model = window.input_panel.model_data()
    assert len(model["elements"]) == 4
    assert any(node["x"] == 8.0 and node["y"] == 4.0 for node in model["nodes"])
    assert window.results_panel.analysis is None
    assert window.undo_action.isEnabled()
    window.undo()
    assert len(window.input_panel.model_data()["elements"]) == 3
    assert window.redo_action.isEnabled()
    window.redo()
    assert len(window.input_panel.model_data()["elements"]) == 4
    window.close()


def test_canvas_selects_and_deletes_members(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    canvas.set_tool("select")
    member_location = canvas._model_to_screen(0.0, 2.0)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(member_location.x()), round(member_location.y())))
    app.processEvents()
    assert canvas.selection == {"nodes": [], "members": [1]}
    canvas.confirm_delete_selection()
    app.processEvents()
    assert len(window.input_panel.model_data()["elements"]) == 2
    assert window.results_panel.analysis is None
    window.close()


def test_canvas_selection_filter_and_crossing_window(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    canvas.set_tool("select")
    canvas.set_selection_filter("nodes")
    member_location = canvas._model_to_screen(0.0, 2.0)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(member_location.x()), round(member_location.y())))
    assert canvas.selection == {"nodes": [], "members": []}

    canvas.set_selection_filter("members")
    left_to_right_start = canvas._model_to_screen(-0.2, 3.0)
    left_to_right_end = canvas._model_to_screen(0.2, 1.0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(left_to_right_start.x()), round(left_to_right_start.y())))
    QTest.mouseMove(canvas, QPoint(round(left_to_right_end.x()), round(left_to_right_end.y())))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(left_to_right_end.x()), round(left_to_right_end.y())))
    assert canvas.selection == {"nodes": [], "members": []}

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(left_to_right_end.x()), round(left_to_right_end.y())))
    QTest.mouseMove(canvas, QPoint(round(left_to_right_start.x()), round(left_to_right_start.y())))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(left_to_right_start.x()), round(left_to_right_start.y())))
    assert canvas.selection == {"nodes": [], "members": [1]}
    window.close()


def test_canvas_zoom_preserves_model_point_under_cursor(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    cursor = canvas._model_to_screen(6.0, 4.0)
    before = canvas._screen_to_model(cursor)
    local = QPoint(round(cursor.x()), round(cursor.y()))
    event = QWheelEvent(
        cursor,
        QPointF(canvas.mapToGlobal(local)),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(canvas, event)
    app.processEvents()
    after = canvas._screen_to_model(cursor)
    assert abs(after[0] - before[0]) < 1.0e-9
    assert abs(after[1] - before[1]) < 1.0e-9
    window.close()


def test_canvas_moves_nodes_and_splits_members(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    canvas.set_tool("select")
    start = canvas._model_to_screen(6.0, 4.0)
    end = canvas._model_to_screen(7.0, 5.0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(start.x()), round(start.y())))
    QTest.mouseMove(canvas, QPoint(round(end.x()), round(end.y())))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(end.x()), round(end.y())))
    app.processEvents()
    moved = next(node for node in window.input_panel.model_data()["nodes"] if node["id"] == 4)
    assert (moved["x"], moved["y"]) == (7.0, 5.0)

    canvas.set_tool("split")
    middle = canvas._model_to_screen(3.5, 4.5)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(middle.x()), round(middle.y())))
    app.processEvents()
    model = window.input_panel.model_data()
    assert len(model["nodes"]) == 5
    assert len(model["elements"]) == 4
    assert len(model["eloads"]) == 2
    window.close()


def test_property_inspector_updates_selected_node_and_member(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    canvas._set_selection({1}, set())
    window.inspector.node_support.setCurrentText("Pinned")
    window.inspector.node_fx.setValue(12.0)
    window.inspector.node_apply.click()
    app.processEvents()
    model = window.input_panel.model_data()
    assert model["nodes"][0]["support"] == "Pinned"
    assert model["nloads"][-1]["fx"] == 12.0

    canvas._set_selection(set(), {3})
    window.inspector.member_release.setCurrentText("Rigid-Pin")
    window.inspector.member_apply.click()
    app.processEvents()
    assert next(member for member in window.input_panel.model_data()["elements"] if member["id"] == 3)["release"] == "Rigid-Pin"
    window.close()


def test_canvas_finds_and_updates_member_loads(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    location = canvas._model_to_screen(3.0, 4.0)
    target = canvas._load_at(location)

    assert target is not None
    assert target[0] == "member"
    canvas.update_member_load(target[1]["index"], {"lcase": "DL", "type": "Point Force", "dir": "Global X", "x_m": 2.0, "p": 14.0, "m": 0.0, "w1": 0.0, "w2": 0.0})
    app.processEvents()
    load = window.input_panel.model_data()["eloads"][0]
    assert load["type"] == "Point Force"
    assert load["dir"] == "Global X"
    assert load["x_m"] == 2.0
    window.close()


def test_display_settings_transform_only_the_diagram_presentation(app: QApplication) -> None:
    window = MainWindow()
    canvas = window.results_panel.canvas
    canvas.set_display_settings(DisplaySettings(axial_positive="compression", shear_positive="counter_clockwise", moment_positive="top_tension", diagram_placement="local_negative"))

    assert canvas._display_diagram_value("n_kg", 10.0) == -10.0
    assert canvas._display_diagram_value("v_kg", 10.0) == -10.0
    assert canvas._display_diagram_value("m_kg_m", 10.0) == -10.0
    assert canvas._diagram_offset("n_kg", 10.0, 2.0) == 20.0
    window.close()


def test_fbd_uses_single_combo_and_balances_reactions(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    panel = window.results_panel
    panel.result_selector.setCurrentIndex(panel.result_selector.findData("combo:Service"))
    panel.canvas.set_view_mode("fbd")
    app.processEvents()

    factors = panel.canvas._display_load_factors()
    residual = panel.canvas._equilibrium_residual(factors, {node["id"]: node for node in panel.canvas._model["nodes"]})
    assert factors == {"DL": 1.0, "LL": 1.0}
    assert max(abs(value) for value in residual) < 1.0e-8
    referenced_residual = panel.canvas._equilibrium_residual(
        factors,
        {node["id"]: node for node in panel.canvas._model["nodes"]},
        (2.75, 1.25),
    )
    assert max(abs(value) for value in referenced_residual) < 1.0e-8
    assert not panel.canvas.grab().isNull()

    panel.result_selector.setCurrentIndex(panel.result_selector.findData("envelope"))
    app.processEvents()
    assert panel.canvas._display_load_factors() == {}
    window.close()


def test_member_point_load_flows_through_editor_canvas_and_fbd(app: QApplication) -> None:
    window = MainWindow()
    model = default_frame_model()
    model["eloads"].append({"elem": 3, "lcase": "LL", "type": "Point Force", "dir": "Global Y", "x_m": 3.0, "p": -12.0})
    model["eloads"].append({"elem": 3, "lcase": "LL", "type": "Point Moment", "x_m": 4.0, "m": 8.0})
    window.set_model(model)
    window.run_analysis()
    window.show()
    app.processEvents()

    stored = window.input_panel.model_data()["eloads"]
    assert stored[-2]["type"] == "Point Force"
    assert stored[-2]["x_m"] == 3.0
    assert stored[-1]["type"] == "Point Moment"
    panel = window.results_panel
    panel.result_selector.setCurrentIndex(panel.result_selector.findData("combo:Service"))
    panel.canvas.set_view_mode("fbd")
    app.processEvents()
    residual = panel.canvas._equilibrium_residual(panel.canvas._display_load_factors(), {node["id"]: node for node in panel.canvas._model["nodes"]})
    assert max(abs(value) for value in residual) < 1.0e-8
    assert not panel.canvas.grab().isNull()
    window.close()


def test_input_panel_preserves_legacy_combination_equation(app: QApplication) -> None:
    model = default_frame_model()
    model["loadcombos"] = [{"name": "Legacy", "eq": "1.2DL + 1.6LL"}]
    panel = FrameInputPanel()
    panel.set_model(model)

    stored = panel.model_data()

    assert stored["loadcombos"] == [{"name": "Legacy", "factors": {}, "eq": "1.2DL + 1.6LL"}]


def test_input_panel_preserves_dynamic_load_case_values(app: QApplication) -> None:
    panel = FrameInputPanel()
    panel.set_model(default_frame_model())

    stored = panel.model_data()

    assert stored["nloads"][0]["lcase"] == "LL"
    assert stored["eloads"][0]["lcase"] == "DL"


def test_project_units_convert_editor_values_but_keep_solver_payload_canonical(app: QApplication) -> None:
    panel = FrameInputPanel()
    panel.set_model(default_frame_model())

    panel.project.units.setCurrentIndex(panel.project.units.findData("n_mm"))
    app.processEvents()
    stored = panel.model_data()

    assert stored["projectInfo"]["units"] == "n_mm"
    assert stored["nodes"][1]["x"] == pytest.approx(6.0)
    assert stored["nloads"][0]["fx"] == pytest.approx(10.0)
    assert "mm" in panel.nodes.table.horizontalHeaderItem(1).text()
    assert "N" in panel.nodal_loads.table.horizontalHeaderItem(2).text()


def test_displacement_formatter_preserves_small_values_in_each_display_unit() -> None:
    assert get_unit_system("legacy_kg_m").format_displacement(0.0000037) == "0.000004"
    assert get_unit_system("n_mm").format_displacement(0.0000037) == "0.004"
    assert get_unit_system("legacy_kg_m").format_displacement(0.0000001) == "1.000e-07"


def test_productivity_commands_and_diagnostic_navigation(app: QApplication) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    canvas = window.results_panel.canvas
    canvas._set_selection(set(), {3})
    canvas.array_selection(1, 2.0, 0.0)
    app.processEvents()
    assert len(window.input_panel.model_data()["elements"]) == 4
    canvas.select_members_by_section(2)
    assert 3 in canvas.selection["members"]

    model = default_frame_model()
    model["elements"].append({"id": 4, "n1": 3, "n2": 4, "sec": 2, "release": "Rigid-Rigid"})
    window.set_model(model)
    window.run_analysis()
    row = next(index for index in range(window.results_panel.diagnostics.rowCount()) if "duplicate" in window.results_panel.diagnostics.item(index, 1).text().lower())
    window.results_panel._select_diagnostic(row, 1)
    assert {3, 4}.issubset(set(canvas.selection["members"]))
    window.close()
