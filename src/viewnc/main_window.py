from __future__ import annotations

from pathlib import Path

import colormaps as colormaps_pkg
import matplotlib.dates as mdates
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
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

MPL_CMAPS = ["viridis", "plasma", "inferno", "cividis", "coolwarm", "RdBu_r", "jet", "turbo", "gray"]
DEFAULT_CMAP = "WhiteBlueGreenYellowRed"

FILE_FILTER = "NetCDF/HDF5 files (*.nc *.nc4 *.cdf *.h5 *.hdf5);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.setWindowTitle("viewnc")
        self.resize(1050, 800)

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

        self.y_label = QLabel("Y axis:")
        self.y_combo = QComboBox()
        self.x_label = QLabel("X axis:")
        self.x_combo = QComboBox()
        self.x_combo.currentIndexChanged.connect(self._on_axis_changed)
        self.y_combo.currentIndexChanged.connect(self._on_axis_changed)

        self.cmap_label = QLabel("Colormap:")
        self.cmap_combo = QComboBox()
        for cmap_name in MPL_CMAPS:
            self.cmap_combo.addItem(cmap_name, cmap_name)
        self.cmap_combo.addItem(DEFAULT_CMAP, getattr(colormaps_pkg, DEFAULT_CMAP))
        self.cmap_combo.setCurrentText(DEFAULT_CMAP)
        self.cmap_combo.currentIndexChanged.connect(self._redraw)

        self._axis_widgets = [self.y_label, self.y_combo, self.x_label, self.x_combo, self.cmap_label, self.cmap_combo]

        self.dim_panel = DimControlsPanel()
        self.dim_panel.changed.connect(self._redraw)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.addWidget(QLabel("Group:"))
        sidebar_layout.addWidget(self.group_combo)
        sidebar_layout.addWidget(QLabel("Variable:"))
        sidebar_layout.addWidget(self.var_combo)
        for w in self._axis_widgets:
            sidebar_layout.addWidget(w)
        sidebar_layout.addWidget(self.dim_panel)
        sidebar_layout.addStretch(1)

        dock = QDockWidget("Controls", self)
        dock.setWidget(sidebar)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(230)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.resizeDocks([dock], [230], Qt.Horizontal)

        self.plot_widget = PlotWidget()
        self.plot_widget.pointClicked.connect(self._on_plot_clicked)
        self.setCentralWidget(self.plot_widget)

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

        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.x_combo.clear()
        self.y_combo.clear()
        self.x_combo.addItems(info.dims)
        self.y_combo.addItems(info.dims)
        if is_2d_plot:
            y_dim, x_dim = default_xy((info.dims[-2], info.dims[-1]))
            self.y_combo.setCurrentText(y_dim)
            self.x_combo.setCurrentText(x_dim)
        self.x_combo.blockSignals(False)
        self.y_combo.blockSignals(False)

        self._update_dim_panel()
        self._redraw()

    def _on_axis_changed(self, _index: int = 0) -> None:
        self._update_dim_panel()
        self._redraw()

    def _update_dim_panel(self) -> None:
        """Rebuild the slice-dimension sliders for every dim that isn't
        currently plotted on the x/y axis, keeping any prior slider
        positions that still apply."""
        if self.backend is None or self.current_group is None or self.current_var is None:
            return
        info = self.backend.variables(self.current_group)[self.current_var]

        x_dim = self.x_combo.currentText()
        y_dim = self.y_combo.currentText()
        if len(info.dims) >= 2 and x_dim and y_dim and x_dim != y_dim and x_dim in info.dims and y_dim in info.dims:
            slice_dims = [d for d in info.dims if d not in (x_dim, y_dim)]
        else:
            slice_dims = list(info.dims[:-2])

        previous = self.dim_panel.indexers()
        dims_sizes = [(d, s) for d, s in zip(info.dims, info.shape) if d in slice_dims]
        coords = {d: self.backend.coord(self.current_group, d) for d, _ in dims_sizes}
        self.dim_panel.set_dims(dims_sizes, coords, initial=previous)

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
                x, y, data2d, xlabel=x_dim, ylabel=y_dim, title=name, cmap=self.cmap_combo.currentData()
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
