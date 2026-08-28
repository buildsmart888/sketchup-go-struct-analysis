"""Small reusable template catalog for specialised workspace starters."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QListWidget, QListWidgetItem, QPlainTextEdit, QVBoxLayout, QWidget


@dataclass(frozen=True)
class TemplateOption:
    key: str
    title: str
    description: str
    preview: str


class TemplateBrowserDialog(QDialog):
    """Choose an editable template after inspecting its intended structural behaviour."""

    def __init__(self, title: str, options: tuple[TemplateOption, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options
        self.setWindowTitle(title)
        self.resize(620, 360)
        self.listing = QListWidget(self)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setMinimumWidth(340)
        for option in options:
            item = QListWidgetItem(option.title, self.listing)
            item.setData(256, option.key)
            item.setToolTip(option.description)
        self.listing.currentRowChanged.connect(self._show_option)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        content = QHBoxLayout()
        content.addWidget(self.listing, 1)
        content.addWidget(self.preview, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(content)
        layout.addWidget(buttons)
        if options:
            self.listing.setCurrentRow(0)

    def selected_key(self) -> str | None:
        item = self.listing.currentItem()
        return str(item.data(256)) if item is not None else None

    def _show_option(self, row: int) -> None:
        if 0 <= row < len(self._options):
            option = self._options[row]
            self.preview.setPlainText(f"{option.title}\n\n{option.description}\n\nPreview\n{option.preview}")
