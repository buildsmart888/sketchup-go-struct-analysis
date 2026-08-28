"""Application entry point for the GO Struct Desktop Frame workspace."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QSplitter, QStyle

from go_struct_core import FrameModel, ModelValidationError, analyze_frame_data, build_frame_postprocess

from .frame_workspace import FrameInputPanel, FrameResultsPanel, default_frame_model


class MainWindow(QMainWindow):
    """A practical desktop shell for authoring and analysing one 2D frame model."""

    def __init__(self) -> None:
        super().__init__()
        application = QApplication.instance()
        if application is not None:
            application.setFont(QFont("Segoe UI", 10))
        self._current_path: Path | None = None
        self._history: list[dict[str, Any]] = []
        self._history_index = -1
        self._suppress_model_events = False
        self.input_panel = FrameInputPanel(self)
        self.results_panel = FrameResultsPanel(self)
        self._build_window()
        self.input_panel.model_changed.connect(self._model_edited)
        self.results_panel.model_change_requested.connect(self._canvas_model_edited)
        self.results_panel.canvas_status_changed.connect(self.statusBar().showMessage)
        self.set_model(default_frame_model())
        self.run_analysis()

    def _build_window(self) -> None:
        self.setWindowTitle("GO Struct Desktop | 2D Frame")
        self.setMinimumSize(1100, 720)
        self.resize(1440, 900)
        self.setStyleSheet(
            """
            QMainWindow { background: #f8fafc; }
            QToolBar { background: #ffffff; border-bottom: 1px solid #cbd5e1; spacing: 4px; padding: 5px; }
            QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; }
            QTabBar::tab { background: #e2e8f0; color: #334155; border: 0; padding: 8px 11px; margin-right: 1px; }
            QTabBar::tab:selected { background: #0f766e; color: #ffffff; }
            QTableWidget { background: #ffffff; alternate-background-color: #f1f5f9; gridline-color: #dbe4ee; selection-background-color: #ccfbf1; selection-color: #0f172a; }
            QHeaderView::section { background: #e2e8f0; color: #334155; border: 0; border-bottom: 1px solid #cbd5e1; padding: 6px; font-weight: 600; }
            QLineEdit, QComboBox { background: #ffffff; border: 1px solid #cbd5e1; min-height: 28px; padding: 2px 6px; }
            QToolButton { background: #ffffff; border: 1px solid #cbd5e1; font-weight: 700; }
            QToolButton:hover { background: #ccfbf1; border-color: #0f766e; }
            QStatusBar { background: #ffffff; border-top: 1px solid #cbd5e1; color: #475569; }
            """
        )
        splitter = QSplitter(self)
        splitter.addWidget(self.input_panel)
        splitter.addWidget(self.results_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([510, 930])
        self.setCentralWidget(splitter)
        self._build_actions()
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        style = self.style()
        new_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setToolTip("New frame model")
        new_action.triggered.connect(self.new_model)

        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setToolTip("Open GOFrame JSON")
        open_action.triggered.connect(self.open_model)

        save_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setToolTip("Save GOFrame JSON")
        save_action.triggered.connect(self.save_model)

        save_as_action = QAction("Save As", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_model_as)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setToolTip("Undo the last model edit")
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setToolTip("Redo the next model edit")
        self.redo_action.triggered.connect(self.redo)

        analyze_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Analyze", self)
        analyze_action.setShortcut(QKeySequence("F5"))
        analyze_action.setToolTip("Run 2D frame analysis")
        analyze_action.triggered.connect(self.run_analysis)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        analysis_menu = self.menuBar().addMenu("Analysis")
        analysis_menu.addAction(analyze_action)
        toolbar = self.addToolBar("Frame")
        toolbar.setMovable(False)
        toolbar.addAction(new_action)
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(analyze_action)
        self._update_history_actions()

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._set_input_model(model)
        current_model = self.input_panel.model_data()
        self.results_panel.set_model(current_model)
        self.results_panel.clear_analysis()
        self._history = [copy.deepcopy(current_model)]
        self._history_index = 0
        self._update_history_actions()

    def new_model(self) -> None:
        self._current_path = None
        self.set_model(default_frame_model())
        self.run_analysis()
        self.statusBar().showMessage("New portal frame")

    def open_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Frame", str(self._current_path.parent if self._current_path else Path.home()), "GOFrame Files (*.goframe.json *.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            model = FrameModel.from_dict(data).to_dict()
        except (OSError, json.JSONDecodeError, ModelValidationError) as exc:
            self._show_error("Unable to open model", str(exc))
            return
        self._current_path = Path(path)
        self.set_model(model)
        self.run_analysis()
        self.statusBar().showMessage(f"Opened {self._current_path.name}")

    def save_model(self) -> None:
        if self._current_path is None:
            self.save_model_as()
            return
        self._write_model(self._current_path)

    def save_model_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Frame", str(self._current_path or Path.home() / "Frame1.goframe.json"), "GOFrame Files (*.goframe.json)")
        if path:
            self._current_path = Path(path)
            self._write_model(self._current_path)

    def run_analysis(self) -> None:
        try:
            model = FrameModel.from_dict(self.input_panel.model_data()).to_dict()
        except (ModelValidationError, ValueError) as exc:
            self._show_error("Model needs attention", str(exc))
            return
        result = analyze_frame_data(model)
        self.results_panel.set_model(model)
        if not result.get("ok"):
            self.results_panel.clear_analysis()
            self._show_error("Analysis failed", str(result.get("error", "Unknown error")))
            return
        self.results_panel.set_analysis(result, build_frame_postprocess(model, result))
        self.statusBar().showMessage(f"Analysis complete: {len(model['nodes'])} nodes, {len(model['elements'])} members")

    def _model_edited(self) -> None:
        if self._suppress_model_events:
            return
        try:
            model = self.input_panel.model_data()
            self.results_panel.set_model(model)
        except (TypeError, ValueError):
            return
        self._record_history(model)
        self.results_panel.clear_analysis()
        self.statusBar().showMessage("Model changed. Run analysis to refresh results.")

    def _canvas_model_edited(self, model: Mapping[str, Any]) -> None:
        self._set_input_model(model)
        self._model_edited()

    def _set_input_model(self, model: Mapping[str, Any]) -> None:
        self._suppress_model_events = True
        try:
            self.input_panel.set_model(model)
        finally:
            self._suppress_model_events = False

    def _record_history(self, model: Mapping[str, Any]) -> None:
        snapshot = copy.deepcopy(dict(model))
        if self._history and self._history[self._history_index] == snapshot:
            return
        self._history = self._history[: self._history_index + 1]
        self._history.append(snapshot)
        self._history_index = len(self._history) - 1
        self._update_history_actions()

    def undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._restore_history("Undo")

    def redo(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._restore_history("Redo")

    def _restore_history(self, action: str) -> None:
        self._set_input_model(self._history[self._history_index])
        self.results_panel.set_model(self.input_panel.model_data())
        self.results_panel.clear_analysis()
        self._update_history_actions()
        self.statusBar().showMessage(f"{action}. Run analysis to refresh results.")

    def _update_history_actions(self) -> None:
        if not hasattr(self, "undo_action"):
            return
        self.undo_action.setEnabled(self._history_index > 0)
        self.redo_action.setEnabled(self._history_index >= 0 and self._history_index < len(self._history) - 1)

    def _write_model(self, path: Path) -> None:
        try:
            model = FrameModel.from_dict(self.input_panel.model_data()).to_dict()
            path.write_text(json.dumps(model, indent=2), encoding="utf-8")
        except (OSError, ModelValidationError, ValueError) as exc:
            self._show_error("Unable to save model", str(exc))
            return
        self.statusBar().showMessage(f"Saved {path.name}")

    def _show_error(self, title: str, detail: str) -> None:
        QMessageBox.critical(self, title, detail)
        self.statusBar().showMessage(title)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GO Struct Desktop")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
