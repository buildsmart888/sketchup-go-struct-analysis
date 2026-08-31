"""Generate deterministic canvas screenshots used by the Markdown user manual."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from go_struct_desktop.app import MainWindow
from go_struct_desktop.beam_workspace import BeamMainWindow
from go_struct_desktop.hybrid_templates import hybrid_truss_on_columns_template
from go_struct_desktop.truss_workspace import TrussMainWindow
from go_struct_desktop.display import DisplaySettings


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "images"
WINDOWS_UI_FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")


def configure_font(app: QApplication) -> None:
    """Load a real Windows UI font for offscreen screenshots.

    Qt's offscreen platform can expose no system font families, which otherwise turns
    canvas labels into missing-glyph boxes in the manual images.
    """

    font_id = QFontDatabase.addApplicationFont(str(WINDOWS_UI_FONT))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError(f"Unable to load manual screenshot font: {WINDOWS_UI_FONT}")
    app.setFont(QFont(families[0], 10))


def capture(window: MainWindow, name: str, diagram: str, display: DisplaySettings | None = None) -> None:
    window.resize(1280, 820)
    window.show()
    QApplication.processEvents()
    if display is not None:
        window.results_panel.set_display_settings(display)
    window.results_panel.canvas.set_diagram_mode(diagram)
    window.results_panel.canvas.set_show_diagram_values(False)
    QApplication.processEvents()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not window.results_panel.canvas.grab().save(str(OUTPUT / name), "PNG"):
        raise RuntimeError(f"Unable to capture {name}")
    window.close()


def main() -> None:
    app = QApplication.instance() or QApplication([])
    configure_font(app)
    capture(MainWindow(), "frame-workspace.png", "m_kg_m")
    capture(BeamMainWindow(), "beam-workspace.png", "m_kg_m")
    capture(
        TrussMainWindow(),
        "truss-workspace.png",
        "n_kg",
        DisplaySettings(contour_enabled=True, contour_palette="truss_axial"),
    )
    hybrid = MainWindow()
    hybrid.set_model(hybrid_truss_on_columns_template("gable", panel_count=4, web_pattern="pratt"))
    hybrid.run_analysis()
    capture(hybrid, "hybrid-workspace.png", "n_kg")
    app.quit()


if __name__ == "__main__":
    main()
