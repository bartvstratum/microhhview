from __future__ import annotations

import matplotlib.dates as mdates
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.colors import Colormap, PowerNorm
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
        self._meshes: list = []
        self._pcolor_xlabel: str | None = None
        self._pcolor_ylabel: str | None = None
        self._pcolor_cmap: str | Colormap | None = None
        self._pcolor_gamma: float | None = None
        self._pcolor_layers: list[tuple[np.ndarray, np.ndarray]] = []
        self._pcolor_data: list[np.ndarray] = []
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
        self._meshes = []
        self._pcolor_layers = []
        self._pcolor_data = []
        self._blit_bg = None
        self.canvas.draw_idle()

    def begin_fast_updates(self) -> None:
        """Cache a blit background for update_data_fast(), used while
        animating: a full canvas.draw() (rasterizing the meshes, colorbar,
        axes, ticks) is the actual bottleneck for playback -- blitting just
        the meshes onto a cached background is far cheaper. Only applies to
        the current pcolormesh layers, if there are any."""
        if self._meshes and self._ax is not None:
            self.canvas.draw()
            self._blit_bg = self.canvas.copy_from_bbox(self._ax.bbox)
        else:
            self._blit_bg = None

    def end_fast_updates(self) -> None:
        self._blit_bg = None

    def update_data_fast(self, data_list: list) -> bool:
        """Blit new mesh data (one array per overlay layer) over the cached
        background. Returns False (nothing drawn) if there's no cached
        background to blit onto, e.g. because the current plot isn't a
        pcolormesh -- caller should fall back to plot_pcolormesh() in that
        case."""
        if self._blit_bg is None or not self._meshes or len(data_list) != len(self._meshes):
            return False
        for mesh, data in zip(self._meshes, data_list):
            mesh.set_array(data.ravel())
        self.canvas.restore_region(self._blit_bg)
        for mesh in self._meshes:
            self._ax.draw_artist(mesh)
        self.canvas.blit(self._ax.bbox)
        self._pcolor_data = data_list
        if self._pcolor_layers:
            self._ax.format_coord = self._make_format_coord(self._ax, self._pcolor_layers, self._pcolor_data)
        return True

    def plot_line(self, x, y, *, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
        self.figure.clear()
        self._meshes = []
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
        layers,
        *,
        xlabel: str = "",
        ylabel: str = "",
        title: str = "",
        cmap: str | Colormap = "viridis",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float | None = None,
    ) -> None:
        """Draw one or more (x, y, data) layers on the same axes, in list
        order (first = bottom, last = top) -- a single-domain plot is just
        the one-layer case. Overlaid layers share one colormap/normalization
        and one colorbar, since they represent the same variable. `gamma`,
        if given, maps color through a PowerNorm instead of linearly --
        useful for fields with a long tail (most of the range packed into a
        few colors under a linear scale)."""
        layers = [(np.asarray(x), np.asarray(y), data) for x, y, data in layers]

        # Scrubbing a dimension slider keeps the same grid and only changes
        # the data values, so update the existing meshes in place instead of
        # tearing down and rebuilding the whole figure (axes, colorbar,
        # layout) on every step -- that rebuild is what made the sliders
        # feel janky.
        reuse = (
            len(self._meshes) == len(layers)
            and self._pcolor_xlabel == xlabel
            and self._pcolor_ylabel == ylabel
            and self._pcolor_cmap == cmap
            and self._pcolor_gamma == gamma
            and all(
                px.shape == x.shape
                and py.shape == y.shape
                and np.array_equal(px, x)
                and np.array_equal(py, y)
                for (px, py), (x, y, _) in zip(self._pcolor_layers, layers)
            )
        )

        if vmin is None and vmax is None:
            # Autoscale across all layers combined, not each mesh on its
            # own -- independent per-mesh autoscaling would give each
            # nested domain its own color scale and make the overlay
            # meaningless.
            shared_vmin = min(np.nanmin(data) for _, _, data in layers)
            shared_vmax = max(np.nanmax(data) for _, _, data in layers)
        else:
            shared_vmin, shared_vmax = vmin, vmax

        if reuse:
            ax = self._ax
            for mesh, (_, _, data) in zip(self._meshes, layers):
                mesh.set_array(data.ravel())
                mesh.set_clim(shared_vmin, shared_vmax)
            ax.set_title(title)
        else:
            self.figure.clear()
            self._blit_bg = None
            ax = self.figure.add_subplot(111)
            self._meshes = []
            # One shared norm instance across all layers, so they stay on
            # the same color scale (and so the colorbar reflects all of them).
            norm = PowerNorm(gamma=gamma, vmin=shared_vmin, vmax=shared_vmax) if gamma else None
            for i, (x, y, data) in enumerate(layers):
                if norm is not None:
                    mesh = ax.pcolormesh(x, y, data, cmap=cmap, shading="auto", norm=norm, zorder=i)
                else:
                    mesh = ax.pcolormesh(
                        x, y, data, cmap=cmap, shading="auto", vmin=shared_vmin, vmax=shared_vmax, zorder=i
                    )
                mesh.set_mouseover(False)  # avoid a duplicate auto "[value]" line from the mesh itself
                self._meshes.append(mesh)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            self.figure.colorbar(self._meshes[-1], ax=ax, shrink=0.75)
            self._ax = ax
            self._pcolor_xlabel = xlabel
            self._pcolor_ylabel = ylabel
            self._pcolor_cmap = cmap
            self._pcolor_gamma = gamma

        self._pcolor_layers = [(x, y) for x, y, _ in layers]
        self._pcolor_data = [data for _, _, data in layers]
        ax.format_coord = self._make_format_coord(ax, self._pcolor_layers, self._pcolor_data)
        self._clickable = True
        self.canvas.draw_idle()

    @staticmethod
    def _make_format_coord(ax, layers, data_list):
        """"(x, y, z) = (...)" status text, using the axis major formatter
        for x/y (so date axes still read as dates). Scans layers
        finest-first (last in the list, since that's drawn on top) so the
        reported value matches what's visually on top where domains
        overlap."""

        def format_coord(x, y):
            x_str = ax.format_xdata(x)
            y_str = ax.format_ydata(y)
            for (xc, yc), data in zip(reversed(layers), reversed(data_list)):
                if xc.min() <= x <= xc.max() and yc.min() <= y <= yc.max():
                    xi = nearest_index(xc, x)
                    yi = nearest_index(yc, y)
                    if 0 <= yi < data.shape[0] and 0 <= xi < data.shape[1]:
                        return f"(x, y, z) = ({x_str}, {y_str}, {data[yi, xi]:.4g})"
            return f"(x, y) = ({x_str}, {y_str})"

        return format_coord
