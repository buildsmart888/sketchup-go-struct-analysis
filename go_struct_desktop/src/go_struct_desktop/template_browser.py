"""Visual, parameter-aware template catalog dialogs for specialised workspaces."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class TemplateParameter:
    key: str
    label: str
    default: float
    minimum: float = 0.1
    maximum: float = 10000.0
    integer: bool = False


@dataclass(frozen=True)
class TemplateOption:
    key: str
    title: str
    description: str
    preview_kind: str
    parameters: tuple[TemplateParameter, ...]
    repeated_parameter: TemplateParameter | None = None
    repeat_count_key: str | None = None


class TemplatePreview(QWidget):
    """Compact engineering sketch for a template and its editable geometric parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._option: TemplateOption | None = None
        self._values: dict[str, float] = {}
        self.setMinimumSize(400, 260)

    def set_template(self, option: TemplateOption, values: dict[str, float]) -> None:
        self._option, self._values = option, dict(values)
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        if self._option is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#1e293b"), 3.0))
        kind = self._option.preview_kind
        if kind in {"cantilever", "simple", "continuous"}:
            self._draw_beam(painter, kind)
        else:
            self._draw_truss(painter, kind)
        painter.setPen(QColor("#334155"))
        painter.drawText(12, self.height() - 12, self._dimension_text())

    def _draw_beam(self, painter: QPainter, kind: str) -> None:
        left, right, y = 48.0, float(self.width() - 48), self.height() * 0.48
        painter.drawLine(int(left), int(y), int(right), int(y))
        if kind == "cantilever":
            painter.setPen(QPen(QColor("#475569"), 4.0))
            painter.drawLine(int(left), int(y - 42), int(left), int(y + 42))
            painter.setPen(QPen(QColor("#94a3b8"), 1.0))
            for offset in range(-38, 43, 9):
                painter.drawLine(int(left - 12), int(y + offset), int(left), int(y + offset - 7))
        else:
            panels = max(1, int(self._values.get("span_count", 1)))
            span_lengths = self._beam_span_lengths(panels)
            total_length = sum(span_lengths)
            supports = [left]
            if kind == "continuous":
                for length in span_lengths:
                    supports.append(supports[-1] + (right - left) * length / total_length)
            else:
                supports = [left, right]
            for index, x in enumerate(supports):
                self._support(painter, x, y, roller=kind == "continuous" and index == len(supports) - 1)
        if kind == "continuous":
            for index, (start, end) in enumerate(zip(supports, supports[1:]), start=1):
                self._dimension(painter, start, end, y + 56, f"span_{index}_m", f"S{index}")
        else:
            self._dimension(painter, left, right, y + 56, "span_m", "Span")
        if kind == "continuous":
            painter.setPen(QColor("#64748b"))
            painter.drawText(12, 24, "Intermediate supports: Pinned")

    def _beam_span_lengths(self, count: int) -> list[float]:
        default = float(self._values.get("span_m", 5.0))
        return [max(0.001, float(self._values.get(f"span_{index}_m", default))) for index in range(1, count + 1)]

    def _draw_truss(self, painter: QPainter, kind: str) -> None:
        left, right, base = 42.0, float(self.width() - 42), self.height() * 0.72
        panels = max(2, int(self._values.get("panel_count", 4)))
        if kind == "triangle":
            self._line(painter, left, base, right, base)
            self._line(painter, left, base, (left + right) / 2.0, base - 110)
            self._line(painter, right, base, (left + right) / 2.0, base - 110)
            self._support(painter, left, base, False)
            self._support(painter, right, base, True)
            self._dimension(painter, left, right, base + 48, "span_m", "Span")
            self._vertical_dimension(painter, (left + right) / 2.0 + 34, base, base - 110, "height_m", "Height")
            return
        step = (right - left) / panels
        top: list[tuple[float, float]] = []
        for index in range(panels + 1):
            x = left + index * step
            rise = 1.0 - abs(2.0 * index / panels - 1.0) if kind == "roof" else 1.0
            top.append((x, base - 96 * rise))
            if index < panels:
                self._line(painter, x, base, x + step, base)
        for index in range(panels):
            self._line(painter, top[index][0], top[index][1], top[index + 1][0], top[index + 1][1])
            if kind == "warren":
                apex_x, apex_y = left + (index + 0.5) * step, base - 96
                self._line(painter, left + index * step, base, apex_x, apex_y)
                self._line(painter, apex_x, apex_y, left + (index + 1) * step, base)
            else:
                self._line(painter, left + index * step, base, top[index][0], top[index][1])
                if kind == "pratt":
                    self._line(painter, left + index * step, base, top[index + 1][0], top[index + 1][1])
                elif kind == "howe":
                    self._line(painter, left + (index + 1) * step, base, top[index][0], top[index][1])
        if kind != "warren":
            self._line(painter, right, base, top[-1][0], top[-1][1])
        self._support(painter, left, base, False)
        self._support(painter, right, base, True)
        self._dimension(painter, left, right, base + 48, "panel_m", "Panel width")
        self._vertical_dimension(painter, (left + right) / 2.0 + 34, base, min(value[1] for value in top), "height_m", "Height")

    @staticmethod
    def _line(painter: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
        painter.drawLine(round(x1), round(y1), round(x2), round(y2))

    def _support(self, painter: QPainter, x: float, y: float, roller: bool) -> None:
        painter.setPen(QPen(QColor("#475569"), 1.5))
        points = [(x, y + 2), (x - 10, y + 17), (x + 10, y + 17)]
        for first, second in zip(points, points[1:] + points[:1]):
            self._line(painter, *first, *second)
        if roller:
            painter.drawEllipse(round(x - 7), round(y + 20), 5, 5)
            painter.drawEllipse(round(x + 2), round(y + 20), 5, 5)
        painter.setPen(QPen(QColor("#1e293b"), 3.0))

    def _dimension(self, painter: QPainter, left: float, right: float, y: float, key: str, label: str) -> None:
        painter.setPen(QPen(QColor("#0f766e"), 1.2))
        self._line(painter, left, y, right, y)
        self._line(painter, left, y - 5, left, y + 5)
        self._line(painter, right, y - 5, right, y + 5)
        painter.drawText(round((left + right) / 2.0 - 45), round(y - 8), f"{label}: {self._values.get(key, 0):g} m")
        painter.setPen(QPen(QColor("#1e293b"), 3.0))

    def _vertical_dimension(self, painter: QPainter, x: float, bottom: float, top: float, key: str, label: str) -> None:
        painter.setPen(QPen(QColor("#0f766e"), 1.2))
        self._line(painter, x, bottom, x, top)
        self._line(painter, x - 5, bottom, x + 5, bottom)
        self._line(painter, x - 5, top, x + 5, top)
        painter.drawText(round(x + 7), round((bottom + top) / 2.0), f"{label}: {self._values.get(key, 0):g} m")
        painter.setPen(QPen(QColor("#1e293b"), 3.0))

    def _dimension_text(self) -> str:
        parameters = list(self._option.parameters)
        if self._option.repeated_parameter and self._option.repeat_count_key:
            count = max(1, int(self._values.get(self._option.repeat_count_key, 1)))
            repeated = self._option.repeated_parameter
            parameters.extend(
                TemplateParameter(f"{repeated.key}_{index}", repeated.label.format(index=index), repeated.default, repeated.minimum, repeated.maximum, repeated.integer)
                for index in range(1, count + 1)
            )
        return ", ".join(f"{item.label} = {self._values.get(item.key, item.default):g}" for item in parameters)


class TemplateBrowserDialog(QDialog):
    """Select a template, inspect a dimensioned preview, and edit its geometry before creation."""

    def __init__(self, title: str, options: tuple[TemplateOption, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options
        self._editors: dict[str, QDoubleSpinBox | QSpinBox] = {}
        self._active_option: TemplateOption | None = None
        self.setWindowTitle(title)
        self.resize(900, 540)
        self.listing = QListWidget(self)
        self.preview = TemplatePreview(self)
        self.description = QLabel(self)
        self.description.setWordWrap(True)
        self.parameters = QFormLayout()
        parameter_host = QWidget(self)
        parameter_host.setLayout(self.parameters)
        for option in options:
            item = QListWidgetItem(option.title, self.listing)
            item.setData(Qt.ItemDataRole.UserRole, option.key)
            item.setToolTip(option.description)
        self.listing.currentRowChanged.connect(self._show_option)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right = QVBoxLayout()
        right.addWidget(self.description)
        right.addWidget(self.preview, 1)
        right.addWidget(parameter_host)
        content = QHBoxLayout()
        content.addWidget(self.listing, 1)
        content.addLayout(right, 3)
        layout = QVBoxLayout(self)
        layout.addLayout(content)
        layout.addWidget(buttons)
        if options:
            self.listing.setCurrentRow(0)

    def selected_key(self) -> str | None:
        item = self.listing.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def selected_values(self) -> dict[str, float | int]:
        return {key: editor.value() for key, editor in self._editors.items()}

    def _show_option(self, row: int) -> None:
        if not 0 <= row < len(self._options):
            return
        option = self._options[row]
        self._active_option = option
        self.description.setText(option.description)
        self._rebuild_parameter_rows({})

    def _rebuild_parameter_rows(self, previous: dict[str, float | int]) -> None:
        option = self._active_option
        if option is None:
            return
        while self.parameters.rowCount():
            self.parameters.removeRow(0)
        self._editors.clear()
        for parameter in option.parameters:
            self._add_parameter(parameter, previous.get(parameter.key, parameter.default))
        if option.repeated_parameter and option.repeat_count_key:
            count = max(1, int(self._editors[option.repeat_count_key].value()))
            repeated = option.repeated_parameter
            for index in range(1, count + 1):
                parameter = TemplateParameter(
                    f"{repeated.key}_{index}",
                    repeated.label.format(index=index),
                    repeated.default,
                    repeated.minimum,
                    repeated.maximum,
                    repeated.integer,
                )
                self._add_parameter(parameter, previous.get(parameter.key, repeated.default))
        self._refresh_preview()

    def _add_parameter(self, parameter: TemplateParameter, value: float | int) -> None:
        editor: QDoubleSpinBox | QSpinBox
        if parameter.integer:
            editor = QSpinBox(self)
            editor.setRange(round(parameter.minimum), round(parameter.maximum))
            editor.setValue(round(value))
        else:
            editor = QDoubleSpinBox(self)
            editor.setDecimals(3)
            editor.setRange(parameter.minimum, parameter.maximum)
            editor.setValue(float(value))
            editor.setSingleStep(max(parameter.default / 10.0, 0.1))
        editor.valueChanged.connect(lambda _value, key=parameter.key: self._parameter_changed(key))
        self.parameters.addRow(parameter.label, editor)
        self._editors[parameter.key] = editor

    def _parameter_changed(self, key: str) -> None:
        option = self._active_option
        if option and key == option.repeat_count_key:
            values = self.selected_values()
            self._rebuild_parameter_rows(values)
            return
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self._active_option is not None:
            self.preview.set_template(self._active_option, {key: float(editor.value()) for key, editor in self._editors.items()})
