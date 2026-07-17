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
        self._mesh = None
        self._pcolor_xlabel: str | None = None
        self._pcolor_ylabel: str | None = None
        self._pcolor_cmap: str | Colormap | None = None
        self._pcolor_x: np.ndarray | None = None
        self._pcolor_y: np.ndarray | None = None
        self._blit_bg = None

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

    def clear(self) -> None:
        self.figure.clear()
        self._ax = None
        self._clickable = False
        self._mesh = None
        self._blit_bg = None
        self.canvas.draw_idle()

    def begin_fast_updates(self) -> None:
        """Cache a blit background for update_data_fast(), used while
        animating: a full canvas.draw() (rasterizing the mesh, colorbar,
        axes, ticks) is the actual bottleneck for playback -- blitting just
        the mesh onto a cached background is far cheaper. Only applies to
        the current pcolormesh, if there is one."""
        if self._mesh is not None and self._ax is not None:
            self.canvas.draw()
            self._blit_bg = self.canvas.copy_from_bbox(self._ax.bbox)
        else:
            self._blit_bg = None

    def end_fast_updates(self) -> None:
        self._blit_bg = None

    def update_data_fast(self, data) -> bool:
        """Blit new mesh data over the cached background. Returns False
        (nothing drawn) if there's no cached background to blit onto, e.g.
        because the current plot isn't a pcolormesh -- caller should fall
        back to plot_pcolormesh() in that case."""
        if self._blit_bg is None or self._mesh is None:
            return False
        self._mesh.set_array(data.ravel())
        self.canvas.restore_region(self._blit_bg)
        self._ax.draw_artist(self._mesh)
        self.canvas.blit(self._ax.bbox)
        if self._pcolor_x is not None and self._pcolor_y is not None:
            self._ax.format_coord = self._make_format_coord(self._ax, self._pcolor_x, self._pcolor_y, data)
        return True

    def plot_line(self, x, y, *, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
        self.figure.clear()
        self._mesh = None
        self._blit_bg = None
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
        x = np.asarray(x)
        y = np.asarray(y)
        # Scrubbing a dimension slider keeps the same grid and only changes
        # the data values, so update the existing mesh in place instead of
        # tearing down and rebuilding the whole figure (axes, colorbar,
        # layout) on every step -- that rebuild is what made the sliders
        # feel janky.
        reuse = (
            self._mesh is not None
            and self._pcolor_xlabel == xlabel
            and self._pcolor_ylabel == ylabel
            and self._pcolor_cmap == cmap
            and self._pcolor_x is not None
            and self._pcolor_y is not None
            and self._pcolor_x.shape == x.shape
            and self._pcolor_y.shape == y.shape
            and np.array_equal(self._pcolor_x, x)
            and np.array_equal(self._pcolor_y, y)
        )
        if reuse:
            ax = self._ax
            mesh = self._mesh
            mesh.set_array(data.ravel())
            if vmin is None and vmax is None:
                mesh.autoscale()
            else:
                mesh.set_clim(vmin, vmax)
            ax.set_title(title)
        else:
            self.figure.clear()
            self._blit_bg = None
            ax = self.figure.add_subplot(111)
            mesh = ax.pcolormesh(x, y, data, cmap=cmap, shading="auto", vmin=vmin, vmax=vmax)
            mesh.set_mouseover(False)  # avoid a duplicate auto "[value]" line from the mesh itself
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            self.figure.colorbar(mesh, ax=ax, shrink=0.75)
            self._ax = ax
            self._mesh = mesh
            self._pcolor_xlabel = xlabel
            self._pcolor_ylabel = ylabel
            self._pcolor_cmap = cmap
            self._pcolor_x = x
            self._pcolor_y = y

        ax.format_coord = self._make_format_coord(ax, x, y, data)
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
