from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from go_struct_desktop.app import MainWindow
from go_struct_desktop.frame_workspace import FrameInputPanel, default_frame_model


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
    window.results_panel.diagram_values_toggle.setChecked(True)
    app.processEvents()
    assert not window.results_panel.canvas.grab().isNull()
    assert "Member calculations" in window.results_panel.calculation_details.toPlainText()
    assert not window.results_panel.diagrams.canvas.grab().isNull()
    assert not window.results_panel.canvas.grab().isNull()

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
