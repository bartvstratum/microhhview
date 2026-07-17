from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QVBoxLayout

from .axis_prefs import Y_AXIS_DIMS, default_sweep_dim, dim_label
from .backends import Backend, VarInfo
from .dim_controls import DimControlsPanel
from .plot_widget import PlotWidget


class PointDialog(QDialog):
    """Popup line-profile plot for a single clicked point on a pcolormesh,
    with a dropdown to choose which dimension to vary along, and sliders to
    step through the remaining (fixed) dimensions, e.g. time."""

    def __init__(
        self,
        parent,
        backend: Backend,
        group: str,
        name: str,
        info: VarInfo,
        point_indexers: dict[str, int],
    ):
        super().__init__(parent)
        self.backend = backend
        self.group = group
        self.name = name
        self.info = info
        self.other_indexers = dict(point_indexers)

        self.setWindowTitle(f"{name} — point profile")
        self.resize(800, 750)

        self.dim_combo = QComboBox()
        self.dim_combo.addItems(info.dims)
        self.dim_combo.setCurrentText(default_sweep_dim(info.dims))
        self.dim_combo.currentIndexChanged.connect(self._on_sweep_dim_changed)

        top = QHBoxLayout()
        top.addWidget(QLabel("Vary dimension:"))
        top.addWidget(self.dim_combo)
        top.addStretch(1)

        self.dim_panel = DimControlsPanel()
        self.dim_panel.changed.connect(self._redraw)

        self.plot_widget = PlotWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.dim_panel)
        layout.addWidget(self.plot_widget, 1)

        self._on_sweep_dim_changed()

    def _on_sweep_dim_changed(self) -> None:
        sweep_dim = self.dim_combo.currentText()
        self.other_indexers.update(self.dim_panel.indexers())

        other_dims = [(d, s) for d, s in zip(self.info.dims, self.info.shape) if d != sweep_dim]
        coords = {d: self.backend.coord(self.group, d) for d, _ in other_dims}
        units = {d: self.backend.units(self.group, d) for d, _ in other_dims}
        self.dim_panel.set_dims(other_dims, coords, units, initial=self.other_indexers)
        self._redraw()

    def _redraw(self) -> None:
        sweep_dim = self.dim_combo.currentText()
        indexers = self.dim_panel.indexers()
        self.other_indexers.update(indexers)

        raw = self.backend.read(self.group, self.name, indexers)
        coord = self.backend.coord(self.group, sweep_dim)
        x = coord if coord is not None else np.arange(raw.shape[0])

        others = ", ".join(f"{d}={i}" for d, i in indexers.items())
        title = f"{self.name} vs {sweep_dim}" + (f"  ({others})" if others else "")

        var_label = dim_label(self.name, self.backend.units(self.group, self.name))
        sweep_label = dim_label(sweep_dim, self.backend.units(self.group, sweep_dim))
        if sweep_dim in Y_AXIS_DIMS:
            # Vertical-profile convention: height on the y-axis, value on x.
            self.plot_widget.plot_line(raw, x, xlabel=var_label, ylabel=sweep_label, title=title)
        else:
            self.plot_widget.plot_line(x, raw, xlabel=sweep_label, ylabel=var_label, title=title)
