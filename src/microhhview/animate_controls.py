from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from .dim_controls import DimSlider

MIN_FPS = 1
MAX_FPS = 30
DEFAULT_FPS = 8


class AnimateControls(QWidget):
    """Play/pause/restart transport that steps a DimSlider on a timer, used
    to animate the "time" dimension. Disabled when there's no time slider
    to drive."""

    playingChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slider: DimSlider | None = None
        self._autoscale = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

        self.restart_button = QPushButton("Restart")
        self.restart_button.clicked.connect(self._on_restart)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._on_play_clicked)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._on_pause_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(self.restart_button)
        buttons.addWidget(self.play_button)
        buttons.addWidget(self.pause_button)

        self.speed_label = QLabel()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(MIN_FPS, MAX_FPS)
        self.speed_slider.setValue(DEFAULT_FPS)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(buttons)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.speed_slider)

        self._update_speed_label()
        self.setEnabled(False)

    def set_time_slider(self, slider: DimSlider | None) -> None:
        if slider is not self._slider:
            self.stop()
        self._slider = slider
        self.setEnabled(slider is not None)
        self._update_play_enabled()

    def set_autoscale(self, enabled: bool) -> None:
        """Playback and "auto scale (per frame)" don't mix: autoscaling
        forces a full redraw (axes + colorbar) every frame, which is what
        made animation slow in the first place. Block Play while it's on."""
        self._autoscale = enabled
        if enabled:
            self.stop()
        self._update_play_enabled()

    def _update_play_enabled(self) -> None:
        self.play_button.setEnabled(self._slider is not None and not self._autoscale)
        self.play_button.setToolTip(
            "Uncheck \"Auto scale (per frame)\" in Colors to animate" if self._autoscale else ""
        )

    def stop(self) -> None:
        self._set_playing(False)

    def _set_playing(self, playing: bool) -> None:
        was_active = self._timer.isActive()
        if playing:
            self._timer.start(self._interval_ms())
        else:
            self._timer.stop()
        if self._timer.isActive() != was_active:
            self.playingChanged.emit(self._timer.isActive())

    def _on_play_clicked(self) -> None:
        if self._slider is not None:
            self._set_playing(True)

    def _on_pause_clicked(self) -> None:
        self._set_playing(False)

    def _on_restart(self) -> None:
        if self._slider is not None:
            self._slider.spin.setValue(0)

    def _on_speed_changed(self, _fps: int) -> None:
        self._update_speed_label()
        if self._timer.isActive():
            self._timer.setInterval(self._interval_ms())

    def _interval_ms(self) -> int:
        return int(1000 / self.speed_slider.value())

    def _update_speed_label(self) -> None:
        self.speed_label.setText(f"Speed ({self.speed_slider.value()} fps)")

    def _advance(self) -> None:
        if self._slider is None:
            self.stop()
            return
        next_index = (self._slider.index() + 1) % (self._slider.slider.maximum() + 1)
        self._slider.spin.setValue(next_index)
