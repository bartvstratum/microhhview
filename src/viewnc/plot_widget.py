from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.colors import Colormap
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget


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
    ) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        mesh = ax.pcolormesh(x, y, data, cmap=cmap, shading="auto")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        self.figure.colorbar(mesh, ax=ax, shrink=0.75)
        self._ax = ax
        self._clickable = True
        self.canvas.draw_idle()
