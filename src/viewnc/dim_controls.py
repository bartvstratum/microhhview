from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QSlider, QSpinBox, QWidget


class DimSlider(QWidget):
    valueChanged = Signal()

    def __init__(self, dim: str, size: int, coord: np.ndarray | None, parent=None):
        super().__init__(parent)
        self.dim = dim
        self.coord = coord
        max_index = max(size - 1, 0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, max_index)
        self.spin = QSpinBox()
        self.spin.setRange(0, max_index)
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(140)

        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        layout.addWidget(self.value_label)
        self._update_label(0)

    def _on_slider(self, value: int) -> None:
        self.spin.blockSignals(True)
        self.spin.setValue(value)
        self.spin.blockSignals(False)
        self._update_label(value)
        self.valueChanged.emit()

    def _on_spin(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._update_label(value)
        self.valueChanged.emit()

    def _update_label(self, index: int) -> None:
        if self.coord is not None and index < len(self.coord):
            self.value_label.setText(str(self.coord[index]))
        else:
            self.value_label.setText(f"index {index}")

    def index(self) -> int:
        return self.slider.value()


class DimControlsPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._sliders: dict[str, DimSlider] = {}

    def set_dims(self, dims: list[tuple[str, int]], coords: dict[str, np.ndarray]) -> None:
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._sliders.clear()

        for dim, size in dims:
            slider = DimSlider(dim, size, coords.get(dim))
            slider.valueChanged.connect(self.changed.emit)
            self._sliders[dim] = slider
            self._layout.addRow(dim, slider)

    def indexers(self) -> dict[str, int]:
        return {dim: s.index() for dim, s in self._sliders.items()}
