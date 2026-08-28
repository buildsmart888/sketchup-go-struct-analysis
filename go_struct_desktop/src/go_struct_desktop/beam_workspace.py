"""Beam workspace entry point built on the shared GO Struct desktop shell."""

from __future__ import annotations

import sys
from typing import Any, Mapping

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from go_struct_core import BeamModel, analyze_beam_data, build_frame_postprocess

from .app import MainWindow, WorkspaceDefinition
from .examples import BUILT_IN_BEAM_EXAMPLES


def default_beam_model() -> dict[str, Any]:
    """Start with a continuous beam so V/M/D are immediately meaningful."""
    return BUILT_IN_BEAM_EXAMPLES[2].model()


BEAM_WORKSPACE = WorkspaceDefinition(
    key="beam",
    title="GO Struct Desktop | 1D Beam",
    model_name="beam",
    default_model=default_beam_model,
    normalize_model=lambda model: BeamModel.from_dict(model).to_dict(),
    analyze=analyze_beam_data,
    postprocess=build_frame_postprocess,
    examples=BUILT_IN_BEAM_EXAMPLES,
    file_extension=".gobeam.json",
)


class BeamMainWindow(MainWindow):
    """Dedicated entry point while retaining the common editor and result docks."""

    def __init__(self) -> None:
        super().__init__(BEAM_WORKSPACE)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GO Struct Beam")
    app.setFont(QFont("Segoe UI", 10))
    window = BeamMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
