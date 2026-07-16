from __future__ import annotations

import matplotlib.dates as mdates
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.colors import Colormap
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget


def nearest_index(coord, value: float) -> int:
    coord = np.asarray(coord)
    if np.issubdtype(coord.dtype, np.datetime64):
        coord = mdates.date2num(coord)
    return int(np.argmin(np.abs(coord - value)))


class PlotWidget(QWidget):
    pointClicked = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(constrained_layout=True)
        self.figure.get_layout_engine().set(w_pad=0.08, h_pad=0.08)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self._ax = None
        self._clickable = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect("button_press_event", self._on_click)

    def _on_click(self, event) -> None:
        if not self._clickable or event.inaxes is not self._ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        self.pointClicked.emit(event.xdata, event.ydata)

    def plot_line(self, x, y, *, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(x, y)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.format_coord = lambda x, y: f"(x, y) = ({ax.format_xdata(x)}, {ax.format_ydata(y)})"
        self._ax = ax
        self._clickable = False
        self.canvas.draw_idle()

    def plot_pcolormesh(
        self,
        x,
        y,
        data,
        *,
        xlabel: str = "",
        ylabel: str = "",
        title: str = "",
        cmap: str | Colormap = "viridis",
        vmin: float | None = None,
        vmax: float | None = None,
    ) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        mesh = ax.pcolormesh(x, y, data, cmap=cmap, shading="auto", vmin=vmin, vmax=vmax)
        mesh.set_mouseover(False)  # avoid a duplicate auto "[value]" line from the mesh itself
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        self.figure.colorbar(mesh, ax=ax, shrink=0.75)
        ax.format_coord = self._make_format_coord(ax, x, y, data)
        self._ax = ax
        self._clickable = True
        self.canvas.draw_idle()

    @staticmethod
    def _make_format_coord(ax, x_coord, y_coord, data):
        """"(x, y, z) = (...)" status text, using the axis major formatter
        for x/y (so date axes still read as dates)."""

        def format_coord(x, y):
            xi = nearest_index(x_coord, x)
            yi = nearest_index(y_coord, y)
            x_str = ax.format_xdata(x)
            y_str = ax.format_ydata(y)
            if 0 <= yi < data.shape[0] and 0 <= xi < data.shape[1]:
                z_str = f"{data[yi, xi]:.4g}"
                return f"(x, y, z) = ({x_str}, {y_str}, {z_str})"
            return f"(x, y) = ({x_str}, {y_str})"

        return format_coord
