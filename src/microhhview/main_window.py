from __future__ import annotations

from pathlib import Path

import colormaps as colormaps_pkg
import matplotlib as mpl
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .axis_prefs import default_xy
from .backends import Backend, open_dataset
from .config import load_config
from .dim_controls import DimControlsPanel
from .plot_widget import PlotWidget, nearest_index
from .point_dialog import PointDialog

FILE_FILTER = "NetCDF/HDF5 files (*.nc *.nc4 *.cdf *.h5 *.hdf5);;All files (*)"


def _section_header(text: str) -> QLabel:
    label = QLabel(text.upper())
    font = label.font()
    font.setBold(True)
    font.setPointSize(max(font.pointSize() - 1, 1))
    label.setFont(font)
    label.setContentsMargins(0, 12, 0, 2)
    return label


class CollapsibleSection(QWidget):
    """A sidebar section whose contents can be toggled show/hide, so
    rarely-changed controls don't crowd out the ones used every frame."""

    def __init__(self, title: str, collapsed: bool = True, parent=None):
        super().__init__(parent)
        self._title = title.upper()

        self._toggle = QPushButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setFlat(True)
        self._toggle.setStyleSheet(
            "QPushButton { text-align: left; border: none; padding: 8px 0 2px 0; }"
        )
        font = self._toggle.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize() - 1, 1))
        self._toggle.setFont(font)
        self._toggle.toggled.connect(self._on_toggled)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

        self._on_toggled(self._toggle.isChecked())

    def _on_toggled(self, expanded: bool) -> None:
        arrow = "▾" if expanded else "▸"
        self._toggle.setText(f"{arrow} {self._title}")
        self._content.setVisible(expanded)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)


def _resolve_cmap(name: str):
    """Look up a colormap name from the user config against matplotlib's
    registry first, then the `colormaps` package. Returns None if the
    name isn't recognized by either."""
    if name in mpl.colormaps:
        return name
    return getattr(colormaps_pkg, name, None)


class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.setWindowTitle("microhhview")
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

        config = load_config()

        self.cmap_label = QLabel("Colormap:")
        self.cmap_combo = QComboBox()
        for cmap_name in config["colormaps"]:
            cmap_obj = _resolve_cmap(cmap_name)
            if cmap_obj is None:
                print(f"microhhview: unknown colormap {cmap_name!r} in config, skipping")
                continue
            self.cmap_combo.addItem(cmap_name, cmap_obj)
        default_cmap = config.get("default_colormap")
        if default_cmap and self.cmap_combo.findText(default_cmap) >= 0:
            self.cmap_combo.setCurrentText(default_cmap)
        self.cmap_combo.currentIndexChanged.connect(self._redraw)

        self.autoscale_checkbox = QCheckBox("Auto scale (per frame)")
        self.autoscale_checkbox.setChecked(True)
        self.autoscale_checkbox.toggled.connect(self._on_scale_toggled)

        self.vmin_edit = QLineEdit()
        self.vmin_edit.setValidator(QDoubleValidator())
        self.vmin_edit.setEnabled(False)
        self.vmin_edit.editingFinished.connect(self._redraw)

        self.vmax_edit = QLineEdit()
        self.vmax_edit.setValidator(QDoubleValidator())
        self.vmax_edit.setEnabled(False)
        self.vmax_edit.editingFinished.connect(self._redraw)

        vrange_container = QWidget()
        vrange_layout = QHBoxLayout(vrange_container)
        vrange_layout.setContentsMargins(0, 0, 0, 0)
        vrange_layout.addWidget(QLabel("vmin:"))
        vrange_layout.addWidget(self.vmin_edit)
        vrange_layout.addWidget(QLabel("vmax:"))
        vrange_layout.addWidget(self.vmax_edit)

        self.global_range_button = QPushButton("Use global range")
        self.global_range_button.clicked.connect(self._on_global_range_clicked)

        axes_widgets = [self.x_label, self.x_combo, self.y_label, self.y_combo]
        color_widgets = [
            self.cmap_label,
            self.cmap_combo,
            self.autoscale_checkbox,
            vrange_container,
            self.global_range_button,
        ]
        self._axis_widgets = axes_widgets + color_widgets

        self.dim_panel = DimControlsPanel()
        self.dim_panel.changed.connect(self._redraw)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(4)
        sidebar_layout.addWidget(_section_header("Data"))
        sidebar_layout.addWidget(QLabel("Group:"))
        sidebar_layout.addWidget(self.group_combo)
        sidebar_layout.addWidget(QLabel("Variable:"))
        sidebar_layout.addWidget(self.var_combo)
        sidebar_layout.addWidget(_section_header("Axes"))
        for w in axes_widgets:
            sidebar_layout.addWidget(w)
        sidebar_layout.addWidget(_section_header("Dimensions"))
        sidebar_layout.addWidget(self.dim_panel)
        colors_section = CollapsibleSection("Colors", collapsed=True)
        for w in color_widgets:
            colors_section.add_widget(w)
        sidebar_layout.addWidget(colors_section)
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
        self.setWindowTitle(f"microhhview — {Path(path).name}")

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
            self.plot_widget.clear()

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

    def _on_scale_toggled(self, checked: bool) -> None:
        self.vmin_edit.setEnabled(not checked)
        self.vmax_edit.setEnabled(not checked)
        if not checked and not self.vmin_edit.text() and not self.vmax_edit.text():
            self._fill_global_range()
        self._redraw()

    def _on_global_range_clicked(self) -> None:
        self._fill_global_range()
        self.autoscale_checkbox.setChecked(False)
        self._redraw()

    def _fill_global_range(self) -> None:
        if self.backend is None or self.current_group is None or self.current_var is None:
            return
        full = self.backend.read(self.current_group, self.current_var, {})
        self.vmin_edit.setText(f"{np.nanmin(full):.4g}")
        self.vmax_edit.setText(f"{np.nanmax(full):.4g}")

    @staticmethod
    def _parse_float(text: str) -> float | None:
        try:
            return float(text)
        except ValueError:
            return None

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

            if self.autoscale_checkbox.isChecked():
                vmin = vmax = None
            else:
                vmin = self._parse_float(self.vmin_edit.text())
                vmax = self._parse_float(self.vmax_edit.text())

            self.plot_widget.plot_pcolormesh(
                x,
                y,
                data2d,
                xlabel=x_dim,
                ylabel=y_dim,
                title=name,
                cmap=self.cmap_combo.currentData(),
                vmin=vmin,
                vmax=vmax,
            )
            self._current_2d = {
                "x_dim": x_dim,
                "y_dim": y_dim,
                "x_coord": x,
                "y_coord": y,
                "slice_indexers": dict(indexers),
            }

    def _on_plot_clicked(self, xdata: float, ydata: float) -> None:
        if self.backend is None or self.current_group is None or self.current_var is None:
            return
        if self._current_2d is None:
            return

        state = self._current_2d
        x_idx = nearest_index(state["x_coord"], xdata)
        y_idx = nearest_index(state["y_coord"], ydata)

        point_indexers = dict(state["slice_indexers"])
        point_indexers[state["x_dim"]] = x_idx
        point_indexers[state["y_dim"]] = y_idx

        info = self.backend.variables(self.current_group)[self.current_var]
        dlg = PointDialog(self, self.backend, self.current_group, self.current_var, info, point_indexers)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.destroyed.connect(lambda: self._popups.remove(dlg) if dlg in self._popups else None)
        self._popups.append(dlg)
        dlg.show()
