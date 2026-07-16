from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .axis_prefs import default_xy
from .backends import Backend, open_dataset
from .dim_controls import DimControlsPanel
from .plot_widget import PlotWidget
from .point_dialog import PointDialog

CMAPS = ["viridis", "plasma", "inferno", "cividis", "coolwarm", "RdBu_r", "jet", "turbo", "gray"]

FILE_FILTER = "NetCDF/HDF5 files (*.nc *.nc4 *.cdf *.h5 *.hdf5);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.setWindowTitle("viewnc")
        self.resize(1000, 850)

        self.backend: Backend | None = None
        self.current_group: str | None = None
        self.current_var: str | None = None
        self._current_2d: dict | None = None
        self._popups: list[PointDialog] = []

        self._build_ui()

        if path:
            self.open_file(path)

    def _build_ui(self) -> None:
        self.group_combo = QComboBox()
        self.group_combo.currentIndexChanged.connect(self._on_group_selected)
        self.var_combo = QComboBox()
        self.var_combo.currentIndexChanged.connect(self._on_variable_selected)

        selector = QWidget()
        selector_layout = QVBoxLayout(selector)
        selector_layout.addWidget(QLabel("Group:"))
        selector_layout.addWidget(self.group_combo)
        selector_layout.addWidget(QLabel("Variable:"))
        selector_layout.addWidget(self.var_combo)
        selector_layout.addStretch(1)

        dock = QDockWidget("Variables", self)
        dock.setWidget(selector)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMaximumWidth(320)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self.y_label = QLabel("Y axis:")
        self.y_combo = QComboBox()
        self.x_label = QLabel("X axis:")
        self.x_combo = QComboBox()
        self.x_combo.currentIndexChanged.connect(self._redraw)
        self.y_combo.currentIndexChanged.connect(self._redraw)

        self.cmap_label = QLabel("Colormap:")
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(CMAPS)
        self.cmap_combo.currentIndexChanged.connect(self._redraw)

        self._axis_widgets = [self.y_label, self.y_combo, self.x_label, self.x_combo, self.cmap_label, self.cmap_combo]

        controls = QHBoxLayout()
        for w in self._axis_widgets:
            controls.addWidget(w)
        controls.addStretch(1)

        self.dim_panel = DimControlsPanel()
        self.dim_panel.changed.connect(self._redraw)

        self.plot_widget = PlotWidget()
        self.plot_widget.pointClicked.connect(self._on_plot_clicked)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(controls)
        layout.addWidget(self.dim_panel)
        layout.addWidget(self.plot_widget, 1)
        self.setCentralWidget(central)

        self._set_2d_controls_visible(False)

        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open...")
        open_action.triggered.connect(self._on_open_clicked)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Quit")
        quit_action.triggered.connect(self.close)

    def _set_2d_controls_visible(self, visible: bool) -> None:
        for w in self._axis_widgets:
            w.setVisible(visible)

    def _on_open_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open dataset", "", FILE_FILTER)
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        try:
            backend = open_dataset(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to open file", str(exc))
            return

        if self.backend is not None:
            self.backend.close()
        self.backend = backend
        self.current_group = None
        self.current_var = None
        self.setWindowTitle(f"viewnc — {Path(path).name}")

        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        for g in backend.groups:
            label = "(root)" if g == "/" else g.lstrip("/")
            self.group_combo.addItem(label, g)
        self.group_combo.blockSignals(False)

        if backend.groups:
            self._on_group_selected(0)

    def _on_group_selected(self, _index: int) -> None:
        if self.backend is None:
            return
        group = self.group_combo.currentData()
        if group is None:
            return
        self.current_group = group

        self.var_combo.blockSignals(True)
        self.var_combo.clear()
        self.var_combo.addItems(sorted(self.backend.variables(group).keys()))
        self.var_combo.blockSignals(False)

        if self.var_combo.count():
            self._on_variable_selected(0)
        else:
            self.current_var = None
            self.plot_widget.figure.clear()
            self.plot_widget.canvas.draw_idle()

    def _on_variable_selected(self, _index: int) -> None:
        if self.backend is None or self.current_group is None:
            return
        name = self.var_combo.currentText()
        if not name:
            return
        self.current_var = name
        info = self.backend.variables(self.current_group)[name]

        is_2d_plot = len(info.dims) >= 2
        self._set_2d_controls_visible(is_2d_plot)

        if is_2d_plot:
            plot_dims = list(info.dims[-2:])
            slice_dims = list(info.dims[:-2])
        else:
            plot_dims = list(info.dims)
            slice_dims = []

        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.x_combo.clear()
        self.y_combo.clear()
        self.x_combo.addItems(info.dims)
        self.y_combo.addItems(info.dims)
        if is_2d_plot:
            y_dim, x_dim = default_xy((plot_dims[0], plot_dims[1]))
            self.y_combo.setCurrentText(y_dim)
            self.x_combo.setCurrentText(x_dim)
        self.x_combo.blockSignals(False)
        self.y_combo.blockSignals(False)

        dims_sizes = [(d, s) for d, s in zip(info.dims, info.shape) if d in slice_dims]
        coords = {d: self.backend.coord(self.current_group, d) for d, _ in dims_sizes}
        self.dim_panel.set_dims(dims_sizes, coords)

        self._redraw()

    def _redraw(self) -> None:
        if self.backend is None or self.current_group is None or self.current_var is None:
            return
        group = self.current_group
        name = self.current_var
        info = self.backend.variables(group)[name]
        indexers = self.dim_panel.indexers()

        raw = self.backend.read(group, name, indexers)
        result_dims = [d for d in info.dims if d not in indexers]

        if len(result_dims) == 1:
            self._current_2d = None
            dim = result_dims[0]
            coord = self.backend.coord(group, dim)
            x = coord if coord is not None else np.arange(raw.shape[0])
            self.plot_widget.plot_line(x, raw, xlabel=dim, ylabel=name, title=name)
        elif len(result_dims) == 2:
            y_dim = self.y_combo.currentText() or result_dims[0]
            x_dim = self.x_combo.currentText() or result_dims[1]
            if y_dim not in result_dims or x_dim not in result_dims or x_dim == y_dim:
                y_dim, x_dim = default_xy((result_dims[0], result_dims[1]))

            data2d = np.transpose(raw, (result_dims.index(y_dim), result_dims.index(x_dim)))
            xc = self.backend.coord(group, x_dim)
            yc = self.backend.coord(group, y_dim)
            x = xc if xc is not None else np.arange(data2d.shape[1])
            y = yc if yc is not None else np.arange(data2d.shape[0])
            self.plot_widget.plot_pcolormesh(
                x, y, data2d, xlabel=x_dim, ylabel=y_dim, title=name, cmap=self.cmap_combo.currentText()
            )
            self._current_2d = {
                "x_dim": x_dim,
                "y_dim": y_dim,
                "x_coord": x,
                "y_coord": y,
                "slice_indexers": dict(indexers),
            }

    @staticmethod
    def _nearest_index(coord: np.ndarray, value: float) -> int:
        coord = np.asarray(coord)
        if np.issubdtype(coord.dtype, np.datetime64):
            coord = mdates.date2num(coord)
        return int(np.argmin(np.abs(coord - value)))

    def _on_plot_clicked(self, xdata: float, ydata: float) -> None:
        if self.backend is None or self.current_group is None or self.current_var is None:
            return
        if self._current_2d is None:
            return

        state = self._current_2d
        x_idx = self._nearest_index(state["x_coord"], xdata)
        y_idx = self._nearest_index(state["y_coord"], ydata)

        point_indexers = dict(state["slice_indexers"])
        point_indexers[state["x_dim"]] = x_idx
        point_indexers[state["y_dim"]] = y_idx

        info = self.backend.variables(self.current_group)[self.current_var]
        dlg = PointDialog(self, self.backend, self.current_group, self.current_var, info, point_indexers)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.destroyed.connect(lambda: self._popups.remove(dlg) if dlg in self._popups else None)
        self._popups.append(dlg)
        dlg.show()
