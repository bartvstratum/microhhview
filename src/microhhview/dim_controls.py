from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QSpinBox, QVBoxLayout, QWidget


class DimSlider(QWidget):
    valueChanged = Signal()

    def __init__(
        self,
        dim: str,
        size: int,
        coord: np.ndarray | None,
        units: str | None = None,
        initial: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.dim = dim
        self.coord = coord
        self.units = units
        max_index = max(size - 1, 0)
        initial = min(max(initial, 0), max_index)

        self.name_label = QLabel()

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, max_index)
        self.slider.setValue(initial)
        self.spin = QSpinBox()
        self.spin.setRange(0, max_index)
        self.spin.setValue(initial)

        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self._update_label(initial)

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
            value = self.coord[index]
            if np.issubdtype(self.coord.dtype, np.datetime64):
                text = str(np.datetime64(value, "s")).replace("T", " ")
            else:
                text = str(value)
                if self.units and self.dim != "time":
                    text = f"{text} {self.units}"
            self.name_label.setText(f"{self.dim} ({text})")
        else:
            self.name_label.setText(self.dim)

    def index(self) -> int:
        return self.slider.value()


class DimControlsPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._sliders: dict[str, DimSlider] = {}

    def set_dims(
        self,
        dims: list[tuple[str, int]],
        coords: dict[str, np.ndarray],
        units: dict[str, str | None] | None = None,
        initial: dict[str, int] | None = None,
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._sliders.clear()

        units = units or {}
        initial = initial or {}
        for dim, size in dims:
            slider = DimSlider(dim, size, coords.get(dim), units.get(dim), initial.get(dim, 0))
            slider.valueChanged.connect(self.changed.emit)
            self._sliders[dim] = slider
            self._layout.addWidget(slider.name_label)
            self._layout.addWidget(slider)

    def indexers(self) -> dict[str, int]:
        return {dim: s.index() for dim, s in self._sliders.items()}
