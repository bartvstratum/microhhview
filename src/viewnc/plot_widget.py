from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def plot_line(self, x, y, *, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(x, y)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
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
        cmap: str = "viridis",
    ) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        mesh = ax.pcolormesh(x, y, data, cmap=cmap, shading="auto")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        self.figure.colorbar(mesh, ax=ax)
        self.canvas.draw_idle()
