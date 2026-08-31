"""Application entry point for the GO Struct Desktop Frame workspace."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QSettings, QSize, QStandardPaths, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPageSize, QPdfWriter, QPen, QPixmap, QPolygonF, QTextDocument
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QProgressDialog, QStyle, QToolBar, QToolButton, QVBoxLayout, QWidget

from go_struct_core import FrameModel, ModelValidationError, analyze_frame_data, build_frame_matrix_view, build_frame_postprocess
from go_struct_core.preflight import check_frame_model

from .frame_workspace import FrameInputPanel, FrameResultsPanel, default_frame_model
from .canvas import FrameCanvas
from .display import DisplayPanel, DisplaySettings
from .engilab import EngiLabImportError, import_engilab_frame, installed_example_files
from .examples import BUILT_IN_FRAME_EXAMPLES, ENGILAB_REFERENCE_EXAMPLES, FrameExample
from .inspector import PropertyInspector
from .hybrid_templates import hybrid_truss_on_columns_template
from .matrix_viewer import MatrixViewerPanel
from .member_result_inspector import MemberResultInspector
from .template_browser import TemplateBrowserDialog, TemplateOption, TemplateParameter
from .reporting import ReportOptions, available_report_selections, build_html_report, write_csv_bundle, write_html_report, write_xlsx
from .section_view import SectionViewPanel
from .workflow import DefineHubDialog, ModelCheckDialog, ProjectStartDialog, SectionCatalogDialog


# QTextDocument maps an embedded PNG's native pixels to page units. Keep report
# canvases smaller than the A4 printable width before turning them into data URIs.
REPORT_CANVAS_IMAGE_WIDTH_PX = 460


class ReportCaptureCancelled(Exception):
    """Raised when the user cancels a potentially large canvas capture."""


@dataclass(frozen=True)
class WorkspaceDefinition:
    """Solver and file metadata for a desktop workspace sharing the common editor shell."""

    key: str
    title: str
    model_name: str
    default_model: Callable[[], dict[str, Any]]
    normalize_model: Callable[[Mapping[str, Any]], dict[str, Any]]
    analyze: Callable[[Mapping[str, Any]], dict[str, Any]]
    postprocess: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
    examples: tuple[FrameExample, ...]
    file_extension: str
    canvas_class: type[FrameCanvas] = FrameCanvas
    engilab_import: bool = False


class ReportOptionsDialog(QDialog):
    """Choose audited report content before a portable HTML or PDF export."""

    def __init__(self, analysis: Mapping[str, Any], current_selection: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Report content")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.coverage = QComboBox(self)
        self.coverage.addItem(f"Current result ({current_selection})", "current")
        self.coverage.addItem("All load cases and combinations", "all")
        if analysis.get("combos"):
            self.coverage.addItem("All combinations", "combos")
        form.addRow("Results", self.coverage)
        layout.addLayout(form)
        self.figure_scope = QComboBox(self)
        self.figure_scope.addItem("No canvas figures", "none")
        self.figure_scope.addItem("Current canvas result only - full figures", "current_full")
        self.figure_scope.addItem("Every selected result - summary (Model, D, FBD)", "selected_summary")
        self.figure_scope.addItem("Every selected result - full (Model, N, V, M, D, FBD)", "selected_full")
        self.figure_scope.addItem("Every selected result - choose views", "selected_views")
        self.figure_scope.setCurrentIndex(self.figure_scope.findData("selected_full"))
        form.addRow("Canvas figures", self.figure_scope)
        self.include_model = QCheckBox("Include model, section, load and combination schedules", self)
        self.include_model.setChecked(True)
        self.include_nodes = QCheckBox("Include node displacement and reaction table", self)
        self.include_nodes.setChecked(True)
        self.include_members = QCheckBox("Include member end-force table", self)
        self.include_members.setChecked(True)
        self.figure_views_group = QGroupBox("Selected canvas views", self)
        figure_layout = QGridLayout(self.figure_views_group)
        self.figure_view_checks: dict[str, QCheckBox] = {}
        for index, label in enumerate(("Model", "N", "V", "M", "D", "FBD")):
            control = QCheckBox(label, self.figure_views_group)
            control.setChecked(True)
            figure_layout.addWidget(control, index // 3, index % 3)
            self.figure_view_checks[label] = control
        layout.addWidget(self.figure_views_group)
        for control in (self.include_model, self.include_nodes, self.include_members):
            layout.addWidget(control)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._analysis = analysis
        self._current_selection = current_selection
        self.figure_scope.currentIndexChanged.connect(self._sync_figure_view_controls)
        self._sync_figure_view_controls()

    def _sync_figure_view_controls(self) -> None:
        self.figure_views_group.setEnabled(str(self.figure_scope.currentData()) == "selected_views")

    def options(self) -> ReportOptions:
        mode = str(self.coverage.currentData())
        if mode == "all":
            selections = available_report_selections(self._analysis)
        elif mode == "combos":
            selections = tuple(selection for selection in available_report_selections(self._analysis) if selection.startswith("combo:"))
        else:
            selections = (self._current_selection,)
        figure_scope = str(self.figure_scope.currentData())
        if figure_scope == "none":
            figure_views: tuple[str, ...] = ()
        elif figure_scope == "selected_summary":
            figure_views = ("Model", "D", "FBD")
        elif figure_scope == "selected_views":
            figure_views = tuple(label for label, control in self.figure_view_checks.items() if control.isChecked())
        else:
            figure_views = ("Model", "N", "V", "M", "D", "FBD")
        return ReportOptions(
            selections=selections or (self._current_selection,),
            include_canvas=bool(figure_views),
            include_model_input=self.include_model.isChecked(),
            include_node_results=self.include_nodes.isChecked(),
            include_member_results=self.include_members.isChecked(),
            figure_scope=figure_scope,
            figure_views=figure_views,
        )


FRAME_WORKSPACE = WorkspaceDefinition(
    key="frame",
    title="GO Struct Desktop | 2D Frame",
    model_name="frame",
    default_model=default_frame_model,
    normalize_model=lambda model: FrameModel.from_dict(model).to_dict(),
    analyze=analyze_frame_data,
    postprocess=build_frame_postprocess,
    examples=BUILT_IN_FRAME_EXAMPLES,
    file_extension=".goframe.json",
    engilab_import=True,
)


class MainWindow(QMainWindow):
    """Dockable authoring shell shared by Frame and Beam workspaces."""

    def __init__(self, workspace: WorkspaceDefinition | None = None) -> None:
        super().__init__()
        self._workspace = workspace or FRAME_WORKSPACE
        application = QApplication.instance()
        if application is not None:
            application.setFont(QFont("Segoe UI", 10))
        self._current_path: Path | None = None
        self._history: list[dict[str, Any]] = []
        self._history_index = -1
        self._suppress_model_events = False
        self._applying_project_preferences = False
        self._dirty = False
        self._workflow_state = "Edit"
        self._settings = QSettings("BuildSmart888", f"GOStructDesktop{self._workspace.key.title()}")
        self.input_panel = FrameInputPanel(self)
        self.results_panel = FrameResultsPanel(self, canvas_class=self._workspace.canvas_class)
        self.inspector = PropertyInspector(self)
        self.matrix_panel = MatrixViewerPanel(self)
        self.section_view_panel = SectionViewPanel(self)
        self.member_result_panel = MemberResultInspector(self)
        self._build_window()
        self.input_panel.model_changed.connect(self._model_edited)
        self.results_panel.model_change_requested.connect(self._canvas_model_edited)
        self.results_panel.canvas_status_changed.connect(self.statusBar().showMessage)
        self.results_panel.canvas.selection_changed.connect(self.inspector.set_selection)
        self.results_panel.canvas.selection_changed.connect(lambda selection: self.section_view_panel.set_model_and_selection(self.input_panel.model_data(), selection))
        self.results_panel.canvas.selection_changed.connect(self.member_result_panel.set_selection)
        self.results_panel.member_results_changed.connect(self.member_result_panel.set_members)
        self.input_panel.units_changed.connect(self.member_result_panel.set_unit_system)
        self.results_panel.delete_requested.connect(self._confirm_delete)
        self.inspector.model_change_requested.connect(self._canvas_model_edited)
        self.results_panel.result_selector.currentIndexChanged.connect(lambda _index: self.matrix_panel.set_result_selection(str(self.results_panel.result_selector.currentData() or "")))
        self.display_panel.settings_changed.connect(self.results_panel.set_display_settings)
        self.display_panel.settings_changed.connect(self._sync_contour_controls)
        self.display_panel.settings_changed.connect(self._save_display_settings)
        self.display_panel.settings_changed.connect(self._project_display_settings_changed)
        self.display_panel.load_case_changed.connect(self.results_panel.canvas.set_load_case)
        self.display_panel.view_mode_changed.connect(self.results_panel.canvas.set_view_mode)
        self.display_panel.view_mode_changed.connect(self._sync_result_view_buttons)
        self.results_panel.set_display_settings(self.display_panel.settings)
        self.results_panel.canvas.tool_changed.connect(self._remember_authoring_tool)
        self.results_panel.load_placement_started.connect(self._remember_load_preset)
        self._restore_display_settings()
        self._sync_contour_controls(self.display_panel.settings)
        self.set_model(self._workspace.default_model())
        self.run_analysis()

    def _build_window(self) -> None:
        self.setWindowTitle(self._workspace.title)
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
        self.setCentralWidget(self.results_panel)
        self.input_dock = self._create_dock("Model Input", "modelInputDock", self.input_panel)
        self.input_dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.input_dock)
        self.results_dock = self._create_dock("Analysis Results", "analysisResultsDock", self.results_panel.detach_results_tabs())
        self.results_dock.setMinimumHeight(120)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.results_dock)
        self.display_panel = DisplayPanel(self)
        self.display_dock = self._create_dock("Display", "displayDock", self.display_panel)
        self.display_dock.setMinimumWidth(280)
        self.display_dock.setMaximumWidth(360)
        self.display_dock.resize(320, 700)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.display_dock)
        self.display_dock.hide()
        self.inspector_dock = self._create_dock("Properties", "propertiesDock", self.inspector)
        self.inspector_dock.setMinimumWidth(280)
        self.inspector_dock.setMaximumWidth(360)
        self.inspector_dock.resize(320, 700)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.matrix_dock = self._create_dock("Matrix & DOF", "matrixDock", self.matrix_panel)
        self.matrix_dock.setMinimumWidth(420)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.matrix_dock)
        self.matrix_dock.hide()
        self.section_view_dock = self._create_dock("Section View", "sectionViewDock", self.section_view_panel)
        self.section_view_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.section_view_dock)
        self.section_view_dock.hide()
        self.member_result_dock = self._create_dock("Selected Member Results", "memberResultDock", self.member_result_panel)
        self.member_result_dock.setMinimumWidth(330)
        self.member_result_dock.setMaximumWidth(460)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.member_result_dock)
        self.member_result_dock.hide()
        self.resizeDocks([self.input_dock], [360], Qt.Orientation.Horizontal)
        self.resizeDocks([self.results_dock], [170], Qt.Orientation.Vertical)
        self._build_actions()
        self._restore_workspace()
        self.statusBar().showMessage("Ready")

    def _create_dock(self, title: str, object_name: str, widget: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setWidget(widget)
        return dock

    def _build_actions(self) -> None:
        style = self.style()
        new_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setToolTip(f"New {self._workspace.model_name} model")
        new_action.triggered.connect(self.new_model)

        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setToolTip("Open GOFrame JSON")
        open_action.triggered.connect(self.open_model)

        import_engilab_action = QAction("Import EngiLab Frame.2D", self)
        import_engilab_action.setToolTip("Import an EngiLab Frame.2D .fr2d text model")
        import_engilab_action.triggered.connect(self.import_engilab_model)

        save_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setToolTip("Save GOFrame JSON")
        save_action.triggered.connect(self.save_model)

        save_as_action = QAction("Save As", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_model_as)

        export_action = QAction("Export Analysis JSON", self)
        export_action.setToolTip("Export the normalized model, analysis, and diagrams")
        export_action.triggered.connect(self.export_analysis)

        export_html_action = QAction("Export HTML Report", self)
        export_html_action.triggered.connect(self.export_html_report)
        export_pdf_action = QAction("Export PDF Report", self)
        export_pdf_action.triggered.connect(self.export_pdf_report)
        export_csv_action = QAction("Export CSV Tables", self)
        export_csv_action.triggered.connect(self.export_csv_tables)
        export_xlsx_action = QAction("Export Excel Workbook", self)
        export_xlsx_action.triggered.connect(self.export_excel_workbook)
        export_png_action = QAction("Export Canvas PNG", self)
        export_png_action.triggered.connect(self.export_canvas_png)
        export_svg_action = QAction("Export Canvas SVG", self)
        export_svg_action.triggered.connect(self.export_canvas_svg)

        recover_action = QAction("Recover Autosave", self)
        recover_action.setToolTip("Recover the most recent unsaved model snapshot")
        recover_action.triggered.connect(self.recover_autosave)

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
        analyze_action.setToolTip(f"Run 2D {self._workspace.model_name} analysis")
        analyze_action.triggered.connect(lambda: self.run_analysis(show_completion=True))
        self._analyze_action = analyze_action

        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.results_panel.canvas._request_delete_selection)
        duplicate_action = QAction("Duplicate", self)
        duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        duplicate_action.triggered.connect(self.results_panel.canvas.duplicate_selection)
        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._select_all)
        fit_selection_action = QAction("Fit Selection", self)
        fit_selection_action.setShortcut(QKeySequence("F"))
        fit_selection_action.triggered.connect(self.results_panel.canvas.fit_selection)
        fit_diagram_action = QAction("Fit Diagram", self)
        fit_diagram_action.triggered.connect(self.display_panel.reset_diagram_scale)

        def tool_action(text: str, tool: str, shortcut: str | None = None) -> QAction:
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda: self.results_panel.canvas.set_tool(tool))
            return action

        node_tool_action = tool_action("Create Node", "node", "N")
        member_tool_action = tool_action("Draw Member", "member", "M")
        split_tool_action = tool_action("Split Member", "split")
        nodal_load_action = tool_action("Nodal Load", "nodal_load")
        member_load_action = tool_action("Member Load", "member_load")
        zoom_window_action = tool_action("Zoom Window", "zoom_window", "Z")

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        if self._workspace.engilab_import:
            file_menu.addAction(import_engilab_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        examples_menu = file_menu.addMenu("Examples")
        for example in self._workspace.examples:
            action = QAction(example.title, self)
            action.setToolTip(example.description)
            action.triggered.connect(lambda _checked=False, value=example: self.load_example(value))
            examples_menu.addAction(action)
        if self._workspace.engilab_import:
            examples_menu.addSeparator()
            installed_files = installed_example_files()
            if installed_files:
                engilab_menu = examples_menu.addMenu(f"EngiLab Installed Examples ({len(installed_files)})")
                for path in installed_files:
                    action = QAction(path.stem, self)
                    action.setToolTip(f"Import {path.name} from the installed EngiLab examples folder")
                    action.triggered.connect(lambda _checked=False, value=path: self.load_engilab_file(value))
                    engilab_menu.addAction(action)
            else:
                engilab_menu = examples_menu.addMenu("EngiLab Frame.2D References (Metric)")
                for example in ENGILAB_REFERENCE_EXAMPLES:
                    action = QAction(example.title, self)
                    action.setToolTip(example.description)
                    action.triggered.connect(lambda _checked=False, value=example: self.load_example(value))
                    engilab_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(export_action)
        file_menu.addAction(recover_action)
        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(delete_action)
        edit_menu.addAction(duplicate_action)
        edit_menu.addAction(select_all_action)
        model_menu = self.menuBar().addMenu("Model")
        model_menu.addAction(node_tool_action)
        model_menu.addAction(member_tool_action)
        model_menu.addAction(split_tool_action)
        geometry_action = QAction("Draw Member by Length / Angle", self)
        geometry_action.triggered.connect(self.draw_member_by_length_angle)
        model_menu.addAction(geometry_action)
        section_catalog_action = QAction("Section / Material Catalog", self)
        section_catalog_action.triggered.connect(self.open_section_catalog)
        model_menu.addAction(section_catalog_action)
        if self._workspace.key == "frame":
            hybrid_catalog_action = QAction("Hybrid Frame-Truss Templates", self)
            hybrid_catalog_action.setToolTip("Create a truss roof carried by steel or concrete Frame columns")
            hybrid_catalog_action.triggered.connect(self.open_hybrid_template_catalog)
            model_menu.addAction(hybrid_catalog_action)
        support_menu = model_menu.addMenu("Support")
        for support in ("Free", "Pinned", "Fixed", "RollerX", "RollerY", "Spring"):
            action = QAction(support, self)
            action.triggered.connect(lambda _checked=False, value=support: self.results_panel.canvas.set_pending_support(value))
            support_menu.addAction(action)
        model_menu.addSeparator()
        align_menu = model_menu.addMenu("Align selected nodes")
        align_x = QAction("X", self)
        align_x.triggered.connect(lambda: self.results_panel.canvas.align_selected("x"))
        align_y = QAction("Y", self)
        align_y.triggered.connect(lambda: self.results_panel.canvas.align_selected("y"))
        align_menu.addAction(align_x)
        align_menu.addAction(align_y)
        mirror_vertical = QAction("Mirror selection vertically", self)
        mirror_vertical.triggered.connect(lambda: self.results_panel.canvas.mirror_selection("vertical"))
        mirror_horizontal = QAction("Mirror selection horizontally", self)
        mirror_horizontal.triggered.connect(lambda: self.results_panel.canvas.mirror_selection("horizontal"))
        move_selection = QAction("Move selection by delta", self)
        move_selection.triggered.connect(self._move_selection_by_delta)
        array_selection = QAction("Array selection", self)
        array_selection.triggered.connect(self._array_selection)
        select_section = QAction("Select members by active section", self)
        select_section.triggered.connect(self._select_members_by_active_section)
        model_menu.addSeparator()
        model_menu.addAction(mirror_vertical)
        model_menu.addAction(mirror_horizontal)
        model_menu.addAction(move_selection)
        model_menu.addAction(array_selection)
        model_menu.addAction(select_section)
        for title in ("Nodes", "Members", "Sections"):
            action = QAction(f"Open {title} table", self)
            action.triggered.connect(lambda _checked=False, value=title: self.input_panel.activate_tab(value))
            model_menu.addAction(action)
        loads_menu = self.menuBar().addMenu("Loads")
        loads_menu.addAction(nodal_load_action)
        loads_menu.addAction(member_load_action)
        loads_menu.addSeparator()
        for title in ("Load Cases", "Nodal Loads", "Member Loads", "Combinations"):
            action = QAction(f"Open {title}", self)
            action.triggered.connect(lambda _checked=False, value=title: self.input_panel.activate_tab(value))
            loads_menu.addAction(action)
        analysis_menu = self.menuBar().addMenu("Analysis")
        define_action = QAction("Define Project Data", self)
        define_action.triggered.connect(self.open_define_hub)
        check_action = QAction("Check Model", self)
        check_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        check_action.triggered.connect(self.check_model)
        analysis_menu.addAction(define_action)
        analysis_menu.addAction(check_action)
        analysis_menu.addAction(analyze_action)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.input_dock.toggleViewAction())
        view_menu.addAction(self.results_dock.toggleViewAction())
        view_menu.addAction(self.display_dock.toggleViewAction())
        view_menu.addAction(self.inspector_dock.toggleViewAction())
        view_menu.addAction(self.matrix_dock.toggleViewAction())
        view_menu.addAction(self.section_view_dock.toggleViewAction())
        view_menu.addAction(self.member_result_dock.toggleViewAction())
        view_menu.addAction(fit_selection_action)
        view_menu.addAction(zoom_window_action)
        view_menu.addAction(fit_diagram_action)
        results_menu = self.menuBar().addMenu("Results")
        results_menu.addAction(analyze_action)
        for label, mode in (("Axial N", "n_kg"), ("Shear V", "v_kg"), ("Moment M", "m_kg_m"), ("FE Deflection", "v_mm"), ("All Diagrams", "all")):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, value=mode: self._set_canvas_diagram(value))
            results_menu.addAction(action)
        fbd_action = QAction("Free Body Diagram", self)
        fbd_action.triggered.connect(lambda: self.display_panel.view_mode.setCurrentIndex(self.display_panel.view_mode.findData("fbd")))
        results_menu.addAction(fbd_action)
        report_menu = self.menuBar().addMenu("Report")
        report_menu.addAction(export_html_action)
        report_menu.addAction(export_pdf_action)
        report_menu.addSeparator()
        report_menu.addAction(export_csv_action)
        report_menu.addAction(export_xlsx_action)
        report_menu.addSeparator()
        report_menu.addAction(export_png_action)
        report_menu.addAction(export_svg_action)
        self.modeling_toolbar = self.addToolBar("Modeling and Loading")
        self.modeling_toolbar.setObjectName("modelingToolbar")
        self.modeling_toolbar.setMovable(False)
        self.modeling_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.modeling_toolbar.addAction(new_action)
        self.modeling_toolbar.addAction(open_action)
        self.modeling_toolbar.addAction(save_action)
        self.modeling_toolbar.addSeparator()
        self.modeling_toolbar.addAction(self.undo_action)
        self.modeling_toolbar.addAction(self.redo_action)
        self.modeling_toolbar.addSeparator()
        self._add_modeling_toolbar_controls(self.modeling_toolbar)
        self.modeling_toolbar.addSeparator()
        self._add_loading_toolbar_controls(self.modeling_toolbar)

        self.addToolBarBreak()
        self.analysis_toolbar = QToolBar("Analysis and Results", self)
        self.analysis_toolbar.setObjectName("analysisToolbar")
        self.analysis_toolbar.setMovable(False)
        self.analysis_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(self.analysis_toolbar)
        self._add_analysis_toolbar_controls(self.analysis_toolbar, analyze_action)
        self.workflow_badge = QLabel("Edit", self.analysis_toolbar)
        self.workflow_badge.setStyleSheet("color: #0f766e; font-weight: 700; padding: 3px 8px;")
        self.analysis_toolbar.addWidget(self.workflow_badge)
        self._update_history_actions()

    def _add_modeling_toolbar_controls(self, toolbar: QToolBar) -> None:
        """Add direct model-authoring controls to the first toolbar row."""
        style = self.style()
        icon_map = {
            "select": QStyle.StandardPixmap.SP_ArrowForward,
            "node": QStyle.StandardPixmap.SP_FileDialogNewFolder,
            "member": QStyle.StandardPixmap.SP_ArrowRight,
            "split": QStyle.StandardPixmap.SP_DialogApplyButton,
            "pan": QStyle.StandardPixmap.SP_BrowserReload,
        }
        for key in ("select", "node", "member", "split", "pan"):
            button = self.results_panel._tool_buttons[key]
            button.setIcon(style.standardIcon(icon_map[key]))
            button.setText("")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedSize(30, 30)
            toolbar.addWidget(button)
        toolbar.addWidget(self.results_panel.support_type)
        self.results_panel.support_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        self.results_panel.support_button.setText("")
        self.results_panel.support_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.results_panel.support_button.setFixedSize(30, 30)
        toolbar.addWidget(self.results_panel.support_button)
        toolbar.addWidget(self.results_panel.selection_filter)
        toolbar.addSeparator()

        toolbar.addWidget(self.results_panel.grid_toggle)
        toolbar.addWidget(self.results_panel.snap_toggle)
        toolbar.addWidget(self.results_panel.snap_nodes_toggle)
        toolbar.addWidget(self.results_panel.grid_spacing)
        self.results_panel.fit_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.results_panel.fit_button.setText("")
        self.results_panel.fit_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.results_panel.fit_button.setFixedSize(30, 30)
        toolbar.addWidget(self.results_panel.fit_button)

    def _add_loading_toolbar_controls(self, toolbar: QToolBar) -> None:
        """Add load-authoring controls to the first toolbar row."""
        style = self.style()
        icon_map = {
            "nodal_load": QStyle.StandardPixmap.SP_ArrowDown,
            "member_load": QStyle.StandardPixmap.SP_ArrowUp,
        }
        for key in ("nodal_load", "member_load"):
            button = self.results_panel._tool_buttons[key]
            button.setIcon(style.standardIcon(icon_map[key]))
            button.setText("")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedSize(30, 30)
            toolbar.addWidget(button)
        toolbar.addSeparator()
        self.load_tool_buttons: dict[str, QToolButton] = {}
        for preset, icon, tooltip in (
            ("nodal_force", QStyle.StandardPixmap.SP_ArrowDown, "Place nodal force: enter values, then click nodes"),
            ("nodal_moment", QStyle.StandardPixmap.SP_BrowserReload, "Place nodal moment: enter value, then click nodes"),
            ("uniform_load", QStyle.StandardPixmap.SP_ArrowUp, "Place uniform member load: enter values, then click members"),
            ("triangular_load", QStyle.StandardPixmap.SP_ArrowUp, "Place triangular member load: enter values, then click members"),
            ("point_force", QStyle.StandardPixmap.SP_ArrowDown, "Place member point force: enter value, then click its station"),
            ("point_moment", QStyle.StandardPixmap.SP_BrowserReload, "Place member point moment: enter value, then click its station"),
        ):
            button = QToolButton(toolbar)
            button.setIcon(self._load_icon(preset, style.standardIcon(icon)))
            button.setToolTip(tooltip)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedSize(30, 30)
            button.clicked.connect(lambda _checked=False, value=preset: self.results_panel.begin_load_placement(value))
            self.load_tool_buttons[preset] = button
            toolbar.addWidget(button)
        toolbar.addWidget(self.results_panel.active_section)
        if self._workspace.key == "frame":
            self.results_panel.active_member_type.setToolTip("New member behaviour: Frame carries N/V/M; Truss carries axial N only")
            toolbar.addWidget(self.results_panel.active_member_type)

    @staticmethod
    def _load_icon(preset: str, fallback: QIcon) -> QIcon:
        """Small structural glyphs make load type recognisable without reading the tooltip."""
        pixmap = QPixmap(QSize(24, 24))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#7c3aed") if preset in {"nodal_moment", "point_moment"} else QColor("#15803d")
        painter.setPen(QPen(color, 2.0))
        painter.setBrush(color)

        def arrow(x: float, top: float, bottom: float) -> None:
            painter.drawLine(round(x), round(top), round(x), round(bottom))
            painter.drawPolygon(QPolygonF([QPointF(x, bottom), QPointF(x - 3.5, bottom - 6.0), QPointF(x + 3.5, bottom - 6.0)]))

        if preset in {"nodal_force", "point_force"}:
            arrow(12.0, 3.0, 18.0)
            if preset == "nodal_force":
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(9, 19, 6, 3)
        elif preset in {"nodal_moment", "point_moment"}:
            rect = (4, 4, 16, 16)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(*rect, 35 * 16, 285 * 16)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(18.0, 6.0), QPointF(12.5, 6.5), QPointF(16.5, 10.0)]))
        else:
            painter.drawLine(3, 19, 21, 19)
            arrows = (5.0, 10.5, 16.0, 21.0)
            for index, x in enumerate(arrows):
                top = 3.0 if preset == "uniform_load" else 4.0 + index * 3.0
                arrow(x, top, 17.0)
            if preset == "triangular_load":
                painter.drawLine(4, 4, 21, 13)
            else:
                painter.drawLine(4, 3, 21, 3)
        painter.end()
        return QIcon(pixmap) if not pixmap.isNull() else fallback

    def _add_analysis_toolbar_controls(self, toolbar: QToolBar, analyze_action: QAction) -> None:
        """Add result navigation and diagram mode icons to the second toolbar row."""
        toolbar.addAction(analyze_action)
        toolbar.addWidget(self.results_panel.result_selector)
        toolbar.addSeparator()
        self.results_panel.canvas_diagram_selector.hide()
        self.diagram_buttons: dict[str, QToolButton] = {}
        self.diagram_button_group = QButtonGroup(self)
        self.diagram_button_group.setExclusive(True)
        for mode, label, tooltip, color in (
            ("none", "Model", "Show model without result diagrams", "#475569"),
            ("n_kg", "N", "Show axial-force (N) diagram", "#15803d"),
            ("v_kg", "V", "Show shear-force (V) diagram", "#2563eb"),
            ("m_kg_m", "M", "Show bending-moment (M) diagram", "#dc2626"),
            ("v_mm", "D", "Show FE deflection diagram", "#0f766e"),
            ("all", "All", "Show N, V, M, and deflection diagrams", "#7c3aed"),
        ):
            button = QToolButton(toolbar)
            button.setText(label)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setStyleSheet(
                f"QToolButton {{ color: {color}; min-width: 30px; }}"
                f"QToolButton:checked {{ background: {color}; color: #ffffff; border-color: {color}; }}"
            )
            button.clicked.connect(lambda _checked=False, value=mode: self._set_canvas_diagram(value))
            self.diagram_button_group.addButton(button)
            self.diagram_buttons[mode] = button
            toolbar.addWidget(button)
        fbd_button = QToolButton(toolbar)
        fbd_button.setText("FBD")
        fbd_button.setCheckable(True)
        fbd_button.setToolTip("Show the free-body diagram with applied loads and reactions")
        fbd_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        fbd_button.setStyleSheet(
            "QToolButton { color: #9f1239; min-width: 38px; }"
            "QToolButton:checked { background: #9f1239; color: #ffffff; border-color: #9f1239; }"
        )
        fbd_button.clicked.connect(self._set_fbd_view)
        self.diagram_button_group.addButton(fbd_button)
        self.diagram_buttons["fbd"] = fbd_button
        toolbar.addWidget(fbd_button)
        self.results_panel.canvas_diagram_selector.currentIndexChanged.connect(self._sync_diagram_buttons)
        self._sync_result_view_buttons()
        toolbar.addSeparator()
        toolbar.addWidget(self.results_panel.diagram_values_toggle)
        toolbar.addWidget(self.results_panel.deformed_toggle)
        self.deformation_animation_button = QToolButton(toolbar)
        self.deformation_animation_button.setText("Animate")
        self.deformation_animation_button.setCheckable(True)
        self.deformation_animation_button.setToolTip("Animate the exaggerated deformed shape")
        self.deformation_animation_button.toggled.connect(self.results_panel.canvas.set_deformation_animation)
        toolbar.addWidget(self.deformation_animation_button)
        self.stress_button = QToolButton(toolbar)
        self.stress_button.setText("Stress")
        self.stress_button.setCheckable(True)
        self.stress_button.setToolTip("Show an approximate elastic top/bottom fibre stress contour; red is positive, blue is negative")
        self.stress_button.toggled.connect(self.results_panel.canvas.set_show_stress)
        toolbar.addWidget(self.stress_button)
        self.contour_button = QToolButton(toolbar)
        self.contour_button.setText("Contour")
        self.contour_button.setCheckable(True)
        self.contour_button.setToolTip("Fill the active N, V, M, or deflection diagram with signed result colours")
        self.contour_button.toggled.connect(self._set_contour_enabled)
        toolbar.addWidget(self.contour_button)
        self.contour_palette_button = QToolButton(toolbar)
        self.contour_palette_button.setText("Palette")
        self.contour_palette_button.setToolTip("Choose signed blue/red, spectrum, or truss axial contour colours")
        self.contour_palette_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        palette_menu = QMenu(self.contour_palette_button)
        for label, value in (
            ("Signed: blue - / red +", "signed"),
            ("Spectrum: low to high", "spectrum"),
            ("Truss N: green tension / red compression", "truss_axial"),
        ):
            action = palette_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, palette=value: self._set_contour_palette(palette))
        self.contour_palette_button.setMenu(palette_menu)
        toolbar.addWidget(self.contour_palette_button)
        self.contour_scale_button = QToolButton(toolbar)
        self.contour_scale_button.setToolTip("Switch contour scale between the global model range and each member range")
        self.contour_scale_button.clicked.connect(self._toggle_contour_scale)
        toolbar.addWidget(self.contour_scale_button)
        toolbar.addWidget(self.results_panel.selection_label)

    def _set_contour_enabled(self, enabled: bool) -> None:
        if enabled and self.results_panel.canvas.diagram_mode in {"all", "none"}:
            selector = self.results_panel.canvas_diagram_selector
            target = "n_kg" if self._workspace.key == "truss" else "m_kg_m"
            selector.setCurrentIndex(selector.findData(target))
        self.display_panel.contour_enabled.setChecked(enabled)

    def _set_contour_palette(self, palette: str) -> None:
        selector = self.display_panel.contour_palette
        index = selector.findData(palette)
        if index >= 0:
            selector.setCurrentIndex(index)

    def _toggle_contour_scale(self) -> None:
        current = str(self.display_panel.contour_scale.currentData() or "global")
        target = "member" if current == "global" else "global"
        self.display_panel.contour_scale.setCurrentIndex(self.display_panel.contour_scale.findData(target))

    def _sync_contour_controls(self, settings: DisplaySettings) -> None:
        if not hasattr(self, "contour_button"):
            return
        self.contour_button.blockSignals(True)
        self.contour_button.setChecked(settings.contour_enabled)
        self.contour_button.blockSignals(False)
        if hasattr(self, "contour_palette_button"):
            palette_text = {"signed": "Blue/Red", "spectrum": "Spectrum", "truss_axial": "Truss N"}
            self.contour_palette_button.setText(palette_text.get(settings.contour_palette, "Palette"))
        self.contour_scale_button.setText("Member" if settings.contour_scale == "member" else "Global")

    def _sync_diagram_buttons(self, _index: int | None = None) -> None:
        if str(self.display_panel.view_mode.currentData() or "results") == "fbd":
            return
        mode = str(self.results_panel.canvas_diagram_selector.currentData() or "none")
        if button := self.diagram_buttons.get(mode):
            button.setChecked(True)

    def _sync_result_view_buttons(self, _mode: str | None = None) -> None:
        if str(self.display_panel.view_mode.currentData() or "results") == "fbd":
            self.diagram_buttons["fbd"].setChecked(True)
        else:
            self._sync_diagram_buttons()

    def set_model(self, model: Mapping[str, Any]) -> None:
        self._set_input_model(model)
        current_model = self.input_panel.model_data()
        self._apply_project_preferences(current_model)
        self.inspector.set_model(current_model)
        self.display_panel.set_load_cases(list(current_model.get("loadcases", [])), list(current_model.get("loadcombos", [])))
        self.results_panel.set_model(current_model)
        self.results_panel.clear_analysis()
        self._set_workflow_state("Edit")
        self._history = [copy.deepcopy(current_model)]
        self._history_index = 0
        self._update_history_actions()
        self._set_dirty(False)

    def new_model(self) -> None:
        dialog = ProjectStartDialog(self._workspace.model_name, self._workspace.examples, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        example = dialog.selected_example()
        if example is not None:
            self.load_example(example)
            return
        self._current_path = None
        self._clear_autosave()
        self.set_model(self._workspace.default_model())
        self.run_analysis()
        self.statusBar().showMessage(f"New {self._workspace.model_name} model")

    def open_define_hub(self) -> None:
        self.input_dock.show()
        DefineHubDialog(self.input_panel.activate_tab, self).exec()

    def open_section_catalog(self) -> None:
        dialog = SectionCatalogDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        model = self.input_panel.model_data()
        section_id = self.results_panel.active_section.currentData()
        target = next((section for section in model.get("sections", []) if int(section.get("id", -1)) == int(section_id)), None)
        if target is None:
            self.statusBar().showMessage("Choose an active section before applying a catalogue profile.")
            return
        target.update(dialog.values())
        self._canvas_model_edited(model)
        self.input_panel.activate_tab("Sections")
        self.input_dock.show()

    def open_hybrid_template_catalog(self) -> None:
        """Offer roof-truss forms that remain editable Frame/Truss members after creation."""

        parameters = (
            TemplateParameter(
                "web_pattern",
                "Web pattern",
                "pratt",
                choices=(
                    ("Pratt | diagonals toward centre", "pratt"),
                    ("Howe | diagonals away from centre", "howe"),
                    ("Warren | alternating diagonals", "warren"),
                    ("X-braced | both diagonals per panel", "x"),
                ),
            ),
            TemplateParameter(
                "column_material",
                "Column material",
                "Steel",
                choices=(("Steel", "Steel"), ("Concrete", "Concrete")),
            ),
            TemplateParameter("panel_count", "Number of panels", 4, 2, 40, integer=True),
            TemplateParameter("panel_m", "Panel width (m)", 3.0),
            TemplateParameter("depth_m", "Truss depth (m)", 1.5),
            TemplateParameter("rise_m", "Top-chord rise (m)", 1.5, 0.0),
            TemplateParameter("bottom_rise_m", "Bottom-chord rise (m)", 0.75, 0.0),
            TemplateParameter("column_height_m", "Column height (m)", 5.0),
        )
        labels = {
            "flat": ("Flat", "Parallel horizontal top and bottom chords."),
            "sloping": ("Sloping Flat", "Parallel sloping chords; the bottom chord follows the roof line."),
            "mono": ("Mono", "Single-pitch top chord over a level bottom chord."),
            "gable": ("Gable", "Symmetric pitched top chord over a level bottom chord."),
            "raised_bottom": ("Raised Bottom", "Both chords rise toward the apex; useful where the ceiling follows the roof."),
            "curved": ("Curved", "Panelled approximation of a curved top chord."),
        }
        options = tuple(
            TemplateOption(
                kind,
                f"{label} Truss",
                f"{description} Choose its web pattern and Steel or Concrete columns at right.",
                f"hybrid_{kind}",
                parameters,
            )
            for kind, (label, description) in labels.items()
        )
        dialog = TemplateBrowserDialog("Hybrid Frame-Truss Template Catalog", options, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        key = dialog.selected_key()
        if not key:
            return
        values = dialog.selected_values()
        kind = key
        material = str(values["column_material"])
        try:
            model = hybrid_truss_on_columns_template(
                kind=kind,
                panel_count=int(values["panel_count"]),
                panel_m=float(values["panel_m"]),
                depth_m=float(values["depth_m"]),
                rise_m=float(values["rise_m"]),
                bottom_rise_m=float(values["bottom_rise_m"]),
                column_height_m=float(values["column_height_m"]),
                column_material=material,
                web_pattern=str(values["web_pattern"]),
            )
        except ValueError as exc:
            self._show_error("Hybrid template", str(exc))
            return
        self._current_path = None
        self._clear_autosave()
        self.set_model(model)
        self.run_analysis(show_completion=True)
        self.input_panel.activate_tab("Members")
        self.input_dock.show()
        self.statusBar().showMessage(
            f"Created Hybrid {kind.replace('_', ' ')} {values['web_pattern']} truss on {material.title()} columns."
        )

    def check_model(self) -> bool:
        """Open preflight findings and return whether no blocking errors were found."""
        try:
            model = self._workspace.normalize_model(self.input_panel.model_data())
        except (ModelValidationError, ValueError) as exc:
            self._show_error("Model needs attention", str(exc))
            return False
        issues = check_frame_model(model) if self._workspace.key == "frame" else [{"severity": "info", "message": "This workspace validates its model during analysis.", "nodes": [], "members": []}]
        dialog = ModelCheckDialog(issues, self)
        dialog.issue_selected.connect(self._select_preflight_issue)
        dialog.exec()
        errors = [issue for issue in issues if str(issue.get("severity", "")).lower() == "error"]
        self._set_workflow_state("Check failed" if errors else "Checked")
        self.statusBar().showMessage("Model check found blocking errors." if errors else "Model check complete. No blocking errors.")
        return not errors

    def _select_preflight_issue(self, issue: Mapping[str, Any]) -> None:
        nodes = {int(value) for value in issue.get("nodes", [])}
        members = {int(value) for value in issue.get("members", [])}
        if nodes or members:
            self.results_panel.canvas._set_selection(nodes, members)
            self.results_panel.canvas.fit_selection()

    def draw_member_by_length_angle(self) -> None:
        selection = self.results_panel.canvas.selection.get("nodes", [])
        if len(selection) != 1:
            self.statusBar().showMessage("Select one start node, then choose length and angle.")
            return
        units = self.input_panel.unit_system
        length, accepted = QInputDialog.getDouble(self, "Draw Member", f"Length ({units.length_unit})", 1.0, 0.001, 1.0e9, 3)
        if not accepted:
            return
        angle, accepted = QInputDialog.getDouble(self, "Draw Member", "Angle (degrees)", 0.0, -360.0, 360.0, 2)
        if accepted:
            self.results_panel.canvas.create_member_by_geometry(int(selection[0]), length / units.length_factor, angle)

    def load_example(self, example: FrameExample) -> None:
        """Load an analysis-ready teaching model without treating it as a saved project."""
        self._current_path = None
        self._clear_autosave()
        self.set_model(example.model())
        self.run_analysis()
        self.results_panel.result_selector.setCurrentIndex(self.results_panel.result_selector.findData(example.result_selection))
        self._set_canvas_diagram(example.diagram_mode)
        self.display_panel.view_mode.setCurrentIndex(self.display_panel.view_mode.findData(example.view_mode))
        self.statusBar().showMessage(f"Loaded example: {example.title}. {example.description}")

    def import_engilab_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import EngiLab Frame.2D",
            str(installed_example_files()[0].parent if installed_example_files() else Path.home()),
            "EngiLab Frame.2D Files (*.fr2d)",
        )
        if path:
            self.load_engilab_file(Path(path))

    def load_engilab_file(self, path: Path) -> None:
        try:
            imported = import_engilab_frame(path)
        except EngiLabImportError as exc:
            self._show_error("Unable to import EngiLab model", str(exc))
            return
        self._current_path = None
        self._clear_autosave()
        self.set_model(imported.model)
        self.run_analysis()
        self.results_panel.result_selector.setCurrentIndex(self.results_panel.result_selector.findData("case:DL"))
        self._set_canvas_diagram("all")
        message = f"Imported EngiLab example: {path.name}"
        if imported.warnings:
            message += f" Warning: {' '.join(imported.warnings)}"
        self.statusBar().showMessage(message)

    def open_model(self) -> None:
        extension = self._workspace.file_extension
        path, _ = QFileDialog.getOpenFileName(self, f"Open {self._workspace.model_name.title()}", str(self._current_path.parent if self._current_path else Path.home()), f"GO Struct Files (*{extension} *.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            model = self._workspace.normalize_model(data)
        except (OSError, json.JSONDecodeError, ModelValidationError) as exc:
            self._show_error("Unable to open model", str(exc))
            return
        self._current_path = Path(path)
        self._clear_autosave()
        self.set_model(model)
        self.run_analysis()
        self.statusBar().showMessage(f"Opened {self._current_path.name}")

    def save_model(self) -> None:
        if self._current_path is None:
            self.save_model_as()
            return
        self._write_model(self._current_path)

    def save_model_as(self) -> None:
        extension = self._workspace.file_extension
        path, _ = QFileDialog.getSaveFileName(self, f"Save {self._workspace.model_name.title()}", str(self._current_path or Path.home() / f"{self._workspace.model_name.title()}1{extension}"), f"GO Struct Files (*{extension})")
        if path:
            self._current_path = Path(path)
            self._write_model(self._current_path)

    def export_analysis(self) -> None:
        if self.results_panel.analysis is None:
            self._show_error("No analysis to export", "Run analysis before exporting results.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Analysis", str(self._current_path or Path.home() / "FrameAnalysis.json"), "Analysis JSON (*.json)")
        if not path:
            return
        try:
            model = self._workspace.normalize_model(self.input_panel.model_data())
            result = self.results_panel.analysis
            postprocess = self._workspace.postprocess(model, result)
            Path(path).write_text(json.dumps({"model": model, "analysis": result, "postprocess": postprocess}, indent=2), encoding="utf-8")
        except (OSError, ModelValidationError, ValueError) as exc:
            self._show_error("Unable to export analysis", str(exc))
            return
        self.statusBar().showMessage(f"Exported {Path(path).name}")

    def _export_context(self) -> tuple[dict[str, Any], Mapping[str, Any], str] | None:
        if self.results_panel.analysis is None:
            self._show_error("No analysis to export", "Run analysis before exporting results.")
            return None
        try:
            return self._workspace.normalize_model(self.input_panel.model_data()), self.results_panel.analysis, str(self.results_panel.result_selector.currentData() or "envelope")
        except (ModelValidationError, ValueError) as exc:
            self._show_error("Unable to prepare export", str(exc))
            return None

    def _report_context(self) -> tuple[dict[str, Any], Mapping[str, Any], ReportOptions, dict[str, dict[str, str]]] | None:
        context = self._export_context()
        if context is None:
            return None
        model, analysis, current_selection = context
        dialog = ReportOptionsDialog(analysis, current_selection, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        options = dialog.options()
        if not options.include_canvas:
            return model, analysis, options, {}
        figure_selections = (current_selection,) if options.figure_scope == "current_full" else options.selections
        try:
            images = self._report_canvas_images(figure_selections, options.figure_views)
        except ReportCaptureCancelled:
            self.statusBar().showMessage("Report export cancelled")
            return None
        return model, analysis, options, images

    def _report_canvas_images(
        self,
        selections: tuple[str, ...],
        figure_views: tuple[str, ...] = ("Model", "N", "V", "M", "D", "FBD"),
    ) -> dict[str, dict[str, str]]:
        """Capture a page-safe model/result figure set for every selected Case or Combo."""

        selector = self.results_panel.result_selector
        previous_index = selector.currentIndex()
        view_selector = self.display_panel.view_mode
        load_selector = self.display_panel.load_case
        canvas = self.results_panel.canvas
        previous_view = view_selector.currentIndex()
        previous_load = load_selector.currentIndex()
        previous_diagram = canvas.diagram_mode
        images: dict[str, dict[str, str]] = {}
        analysis_type = str(self.input_panel.model_data().get("projectInfo", {}).get("analysisType", "Frame")).lower()
        views = [("Model", "model", "none"), ("N", "results", "n_kg")]
        if analysis_type != "truss":
            views.extend((("V", "results", "v_kg"), ("M", "results", "m_kg_m")))
        views.append(("D", "results", "v_mm"))
        capture_plan: list[tuple[str, str, str, str]] = []
        for selection in selections:
            selected_views = views if selection == "envelope" else [*views, ("FBD", "fbd", "none")]
            for label, view_mode, diagram in selected_views:
                if label in figure_views:
                    capture_plan.append((selection, label, view_mode, diagram))
        progress = QProgressDialog("Preparing report figures...", "Cancel", 0, len(capture_plan), self)
        progress.setWindowTitle("Preparing report")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.show()
        try:
            for step, (selection, label, view_mode, diagram) in enumerate(capture_plan, start=1):
                if progress.wasCanceled():
                    raise ReportCaptureCancelled()
                progress.setLabelText(f"Capturing {label}: {selection} ({step}/{len(capture_plan)})")
                index = selector.findData(selection)
                if index < 0:
                    continue
                selector.setCurrentIndex(index)
                load_index = load_selector.findData(selection)
                if load_index >= 0:
                    load_selector.setCurrentIndex(load_index)
                images.setdefault(selection, {})
                view_index = view_selector.findData(view_mode)
                if view_index >= 0:
                    view_selector.setCurrentIndex(view_index)
                canvas.set_diagram_mode(diagram)
                QApplication.processEvents()
                data = QByteArray()
                buffer = QBuffer(data)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                snapshot = canvas.grab()
                if snapshot.width() > REPORT_CANVAS_IMAGE_WIDTH_PX:
                    snapshot = snapshot.scaledToWidth(
                        REPORT_CANVAS_IMAGE_WIDTH_PX,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                snapshot.save(buffer, "PNG")
                buffer.close()
                images[selection][label] = bytes(data.toBase64()).decode("ascii")
                progress.setValue(step)
                QApplication.processEvents()
                if progress.wasCanceled():
                    raise ReportCaptureCancelled()
        finally:
            progress.close()
            selector.setCurrentIndex(previous_index)
            view_selector.setCurrentIndex(previous_view)
            load_selector.setCurrentIndex(previous_load)
            canvas.set_diagram_mode(previous_diagram)
            QApplication.processEvents()
        return images

    def export_html_report(self) -> None:
        context = self._report_context()
        if context is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export HTML Report", str(self._current_path or Path.home() / "GOStructReport.html"), "HTML Report (*.html)")
        if path:
            try:
                model, analysis, options, images = context
                write_html_report(Path(path), model, analysis, options.selections, options=options, canvas_images=images)
                self.statusBar().showMessage(f"Exported {Path(path).name}")
            except OSError as exc:
                self._show_error("Unable to export HTML report", str(exc))

    def export_pdf_report(self) -> None:
        context = self._report_context()
        if context is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF Report", str(self._current_path or Path.home() / "GOStructReport.pdf"), "PDF Report (*.pdf)")
        if path:
            try:
                writer = QPdfWriter(path)
                writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                document = QTextDocument(self)
                model, analysis, options, images = context
                document.setHtml(build_html_report(model, analysis, options.selections, options=options, canvas_images=images))
                document.print_(writer)
                self.statusBar().showMessage(f"Exported {Path(path).name}")
            except OSError as exc:
                self._show_error("Unable to export PDF report", str(exc))

    def export_csv_tables(self) -> None:
        context = self._export_context()
        if context is None:
            return
        directory = QFileDialog.getExistingDirectory(self, "Export CSV Tables", str(self._current_path.parent if self._current_path else Path.home()))
        if directory:
            try:
                written = write_csv_bundle(Path(directory), *context)
                self.statusBar().showMessage(f"Exported {len(written)} CSV tables to {Path(directory).name}")
            except OSError as exc:
                self._show_error("Unable to export CSV tables", str(exc))

    def export_excel_workbook(self) -> None:
        context = self._export_context()
        if context is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel Workbook", str(self._current_path or Path.home() / "GOStructResults.xlsx"), "Excel Workbook (*.xlsx)")
        if path:
            try:
                write_xlsx(Path(path), *context)
                self.statusBar().showMessage(f"Exported {Path(path).name}")
            except OSError as exc:
                self._show_error("Unable to export Excel workbook", str(exc))

    def export_canvas_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Canvas PNG", str(self._current_path or Path.home() / "GOStructCanvas.png"), "PNG Image (*.png)")
        if path and self.results_panel.canvas.grab().save(path, "PNG"):
            self.statusBar().showMessage(f"Exported {Path(path).name}")

    def export_canvas_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Canvas SVG", str(self._current_path or Path.home() / "GOStructCanvas.svg"), "SVG Image (*.svg)")
        if not path:
            return
        generator = QSvgGenerator()
        generator.setFileName(path)
        generator.setSize(self.results_panel.canvas.size())
        generator.setViewBox(self.results_panel.canvas.rect())
        painter = QPainter(generator)
        self.results_panel.canvas.render(painter)
        painter.end()
        self.statusBar().showMessage(f"Exported {Path(path).name}")

    def run_analysis(self, show_completion: bool = False) -> None:
        started_at = perf_counter()
        try:
            model = self._workspace.normalize_model(self.input_panel.model_data())
        except (ModelValidationError, ValueError) as exc:
            self._show_error("Model needs attention", str(exc))
            return
        if self._workspace.key == "frame":
            issues = check_frame_model(model)
            errors = [issue for issue in issues if str(issue.get("severity", "")).lower() == "error"]
            if errors:
                self._set_workflow_state("Check failed")
                self._show_error("Model check failed", "\n".join(str(issue["message"]) for issue in errors))
                return
        self._set_workflow_state("Analyzing…")
        self._analyze_action.setEnabled(False)
        QApplication.processEvents()
        result = self._workspace.analyze(model)
        self._analyze_action.setEnabled(True)
        self.results_panel.set_model(model)
        if not result.get("ok"):
            self.results_panel.clear_analysis()
            self._set_workflow_state("Analysis failed")
            self._show_error("Analysis failed", str(result.get("error", "Unknown error")))
            return
        self.results_panel.set_analysis(result, self._workspace.postprocess(model, result))
        if self._workspace.key == "frame":
            self.matrix_panel.set_matrix_data(build_frame_matrix_view(model, result))
        self._set_workflow_state("Results")
        elapsed_seconds = perf_counter() - started_at
        self.statusBar().showMessage(
            f"Analysis complete: {len(model['nodes'])} nodes, {len(model['elements'])} members ({elapsed_seconds:.2f} s)"
        )
        if show_completion:
            self._show_analysis_complete(model, elapsed_seconds)

    def _set_workflow_state(self, state: str) -> None:
        self._workflow_state = state
        if hasattr(self, "workflow_badge"):
            colour = "#15803d" if state == "Results" else "#b45309" if state in {"Stale", "Check failed", "Analysis failed"} else "#0f766e"
            self.workflow_badge.setText(state)
            self.workflow_badge.setStyleSheet(f"color: {colour}; font-weight: 700; padding: 3px 8px;")

    def _show_analysis_complete(self, model: Mapping[str, Any], elapsed_seconds: float) -> None:
        QMessageBox.information(
            self,
            "Analysis complete",
            f"The 2D {self._workspace.model_name} analysis finished successfully.\n\n"
            f"Nodes: {len(model['nodes'])}\n"
            f"Members: {len(model['elements'])}\n"
            f"Elapsed time: {elapsed_seconds:.2f} s",
        )

    def _model_edited(self) -> None:
        if self._suppress_model_events:
            return
        try:
            model = self.input_panel.model_data()
            self.display_panel.set_load_cases(list(model.get("loadcases", [])), list(model.get("loadcombos", [])))
            self.results_panel.set_model(model)
            self.inspector.set_model(model)
        except (TypeError, ValueError):
            return
        self._record_history(model)
        self.results_panel.clear_analysis()
        self._set_workflow_state("Stale")
        self._set_dirty(True)
        self._autosave_model(model)
        self.statusBar().showMessage("Model changed. Run analysis to refresh results.")

    def _canvas_model_edited(self, model: Mapping[str, Any]) -> None:
        self._set_input_model(model)
        self._model_edited()

    def _select_all(self) -> None:
        self.results_panel.canvas._set_selection(
            {int(node["id"]) for node in self.results_panel.canvas._model.get("nodes", [])},
            {int(member["id"]) for member in self.results_panel.canvas._model.get("elements", [])},
        )

    def _move_selection_by_delta(self) -> None:
        units = self.input_panel.unit_system
        dx, accepted = QInputDialog.getDouble(self, "Move selection", f"Delta X ({units.length_unit})", 0.0, -1.0e9, 1.0e9, 3)
        if not accepted:
            return
        dy, accepted = QInputDialog.getDouble(self, "Move selection", f"Delta Y ({units.length_unit})", 0.0, -1.0e9, 1.0e9, 3)
        if accepted:
            self.results_panel.canvas.move_selection(dx / units.length_factor, dy / units.length_factor)

    def _array_selection(self) -> None:
        units = self.input_panel.unit_system
        count, accepted = QInputDialog.getInt(self, "Array selection", "Additional copies", 1, 1, 100)
        if not accepted:
            return
        dx, accepted = QInputDialog.getDouble(self, "Array selection", f"Delta X ({units.length_unit})", self.results_panel.grid_spacing.value(), -1.0e9, 1.0e9, 3)
        if not accepted:
            return
        dy, accepted = QInputDialog.getDouble(self, "Array selection", f"Delta Y ({units.length_unit})", 0.0, -1.0e9, 1.0e9, 3)
        if accepted:
            self.results_panel.canvas.array_selection(count, dx / units.length_factor, dy / units.length_factor)

    def _select_members_by_active_section(self) -> None:
        section_id = self.results_panel.active_section.currentData()
        if section_id is not None:
            self.results_panel.canvas.select_members_by_section(int(section_id))

    def _set_canvas_diagram(self, mode: str) -> None:
        self.display_panel.view_mode.setCurrentIndex(self.display_panel.view_mode.findData("results"))
        # Direct N/V/M/D/All buttons intentionally restore the familiar solid-colour diagrams.
        # Contour is opt-in from its own toggle after choosing the quantity to inspect.
        if self.display_panel.settings.contour_enabled:
            self.display_panel.contour_enabled.setChecked(False)
        if not self.display_panel.settings.diagram_fill:
            self.display_panel.diagram_fill.setChecked(True)
        selector = self.results_panel.canvas_diagram_selector
        selector.setCurrentIndex(selector.findData(mode))

    def _set_fbd_view(self) -> None:
        self.display_panel.view_mode.setCurrentIndex(self.display_panel.view_mode.findData("fbd"))

    def _confirm_delete(self, impact: Mapping[str, Any]) -> None:
        nodes = impact.get("nodes", [])
        members = impact.get("members", [])
        detail = f"Delete {len(nodes)} node(s) and {len(members)} member(s)? Associated loads will also be removed."
        answer = QMessageBox.question(self, "Delete selected objects", detail, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.results_panel.canvas.confirm_delete_selection()

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
        self._set_workflow_state("Stale")
        self._set_dirty(True)
        self._autosave_model(self.input_panel.model_data())
        self._update_history_actions()
        self.statusBar().showMessage(f"{action}. Run analysis to refresh results.")

    def _update_history_actions(self) -> None:
        if not hasattr(self, "undo_action"):
            return
        self.undo_action.setEnabled(self._history_index > 0)
        self.redo_action.setEnabled(self._history_index >= 0 and self._history_index < len(self._history) - 1)

    def _write_model(self, path: Path) -> None:
        try:
            model = self._workspace.normalize_model(self.input_panel.model_data())
            path.write_text(json.dumps(model, indent=2), encoding="utf-8")
        except (OSError, ModelValidationError, ValueError) as exc:
            self._show_error("Unable to save model", str(exc))
            return
        self._set_dirty(False)
        self._clear_autosave()
        self.statusBar().showMessage(f"Saved {path.name}")

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        title = self._workspace.title
        self.setWindowTitle(f"* {title}" if dirty else title)

    @property
    def _autosave_path(self) -> Path:
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        return root / f"recovery.{self._workspace.key}.json"

    def _autosave_model(self, model: Mapping[str, Any]) -> None:
        try:
            path = self._autosave_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._workspace.normalize_model(model), indent=2), encoding="utf-8")
        except (OSError, ModelValidationError, ValueError):
            self.statusBar().showMessage("Model changed. Autosave could not be written.")

    def _clear_autosave(self) -> None:
        try:
            self._autosave_path.unlink(missing_ok=True)
        except OSError:
            pass

    def recover_autosave(self) -> None:
        path = self._autosave_path
        if not path.exists():
            self.statusBar().showMessage("No autosave recovery file is available.")
            return
        try:
            self.set_model(json.loads(path.read_text(encoding="utf-8")))
            self.run_analysis()
        except (OSError, json.JSONDecodeError, ModelValidationError, ValueError) as exc:
            self._show_error("Unable to recover autosave", str(exc))
            return
        self._set_dirty(True)
        self.statusBar().showMessage("Recovered autosave. Save the model to keep it.")

    def _restore_workspace(self) -> None:
        if QApplication.platformName() == "offscreen":
            return
        geometry = self._settings.value("workspace/geometry")
        state = self._settings.value("workspace/state")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        canvas = self._settings.value("workspace/canvas", {})
        if isinstance(canvas, Mapping):
            self.results_panel.grid_toggle.setChecked(bool(canvas.get("grid", self.results_panel.grid_toggle.isChecked())))
            self.results_panel.snap_toggle.setChecked(bool(canvas.get("snap", self.results_panel.snap_toggle.isChecked())))
            self.results_panel.snap_nodes_toggle.setChecked(bool(canvas.get("snap_nodes", self.results_panel.snap_nodes_toggle.isChecked())))
            self.results_panel.grid_spacing.setValue(float(canvas.get("grid_spacing", self.results_panel.grid_spacing.value())))

    def _save_display_settings(self, settings) -> None:  # type: ignore[no-untyped-def]
        self._settings.setValue("workspace/display", settings.to_dict())

    def _project_display_settings_changed(self, settings: DisplaySettings) -> None:
        if self._applying_project_preferences:
            return
        self.input_panel.set_display_preferences(settings.to_dict())

    def _remember_authoring_tool(self, tool: str) -> None:
        if self._applying_project_preferences:
            return
        authoring = dict(self.input_panel.model_data().get("settings", {}).get("authoring", {}))
        authoring["last_tool"] = tool
        self.input_panel.set_authoring_preferences(authoring)

    def _remember_load_preset(self, preset: str) -> None:
        authoring = dict(self.input_panel.model_data().get("settings", {}).get("authoring", {}))
        authoring["last_load_preset"] = preset
        self.input_panel.set_authoring_preferences(authoring)

    def _apply_project_preferences(self, model: Mapping[str, Any]) -> None:
        settings = model.get("settings", {})
        display = settings.get("display", {}) if isinstance(settings, Mapping) else {}
        authoring = settings.get("authoring", {}) if isinstance(settings, Mapping) else {}
        if not (isinstance(display, Mapping) and display) and not (isinstance(authoring, Mapping) and authoring):
            return
        self._applying_project_preferences = True
        try:
            if isinstance(display, Mapping) and display:
                self.display_panel._apply_settings(DisplaySettings.from_mapping(display))
                self.results_panel.set_display_settings(self.display_panel.settings)
            if isinstance(authoring, Mapping) and authoring:
                tool = str(authoring.get("last_tool", ""))
                if tool:
                    self.results_panel.canvas.set_tool(tool)
        finally:
            self._applying_project_preferences = False

    def _restore_display_settings(self) -> None:
        saved = self._settings.value("workspace/display", {})
        if isinstance(saved, Mapping):
            self.display_panel._apply_settings(DisplaySettings.from_mapping(saved))
            self.results_panel.set_display_settings(self.display_panel.settings)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._settings.setValue("workspace/geometry", self.saveGeometry())
        self._settings.setValue("workspace/state", self.saveState())
        self._settings.setValue(
            "workspace/canvas",
            {
                "grid": self.results_panel.grid_toggle.isChecked(),
                "snap": self.results_panel.snap_toggle.isChecked(),
                "snap_nodes": self.results_panel.snap_nodes_toggle.isChecked(),
                "grid_spacing": self.results_panel.grid_spacing.value(),
            },
        )
        event.accept()

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
