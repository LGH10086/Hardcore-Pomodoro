from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget


class OverlayWindow(QWidget):
    WINDOW_TITLE = "Hardcore Pomodoro Overlay"

    def __init__(self, screen_index: int = 0) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self._motto_label = QLabel("Stay focused, stay foolish.")
        self._motto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._motto_label.setStyleSheet(
            """
            font-size: 52px;
            font-weight: 700;
            color: #f8fafc;
            padding: 28px;
            border-radius: 18px;
            background: rgba(15, 23, 42, 140);
            border: 1px solid rgba(125, 211, 252, 160);
            """
        )

        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self._motto_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self._motto_opacity = QGraphicsOpacityEffect(self._motto_label)
        self._motto_label.setGraphicsEffect(self._motto_opacity)
        self._motto_breathing = QPropertyAnimation(self._motto_opacity, b"opacity", self)
        self._motto_breathing.setDuration(2200)
        self._motto_breathing.setStartValue(0.7)
        self._motto_breathing.setEndValue(1.0)
        self._motto_breathing.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._motto_breathing.setLoopCount(-1)
        self._motto_breathing.start()

        self._background_pixmap: QPixmap | None = None
        self._has_custom_image = False
        self._set_geometry_to_screen(screen_index)

    def _set_geometry_to_screen(self, screen_index: int) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        idx = min(screen_index, len(screens) - 1)
        self.setGeometry(screens[idx].geometry())

    def update_content(self, motto: str, background_image_path: str) -> None:
        self._motto_label.setText(motto or "Stay focused, stay foolish.")
        image_path = Path(background_image_path)
        if image_path.exists() and image_path.is_file():
            loaded = QPixmap(str(image_path))
            if not loaded.isNull():
                self._background_pixmap = loaded
                self._has_custom_image = True
                self.update()
                return

        self._background_pixmap = None
        self._has_custom_image = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()

        if self._has_custom_image and self._background_pixmap is not None:
            scaled = self._background_pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            offset_x = (rect.width() - scaled.width()) // 2
            offset_y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(offset_x, offset_y, scaled)
            painter.fillRect(rect, QColor(3, 8, 24, 126))
        else:
            gradient = QRadialGradient(
                rect.center(),
                max(rect.width(), rect.height()) * 0.75,
                rect.center(),
            )
            gradient.setColorAt(0, QColor(15, 23, 42, 185))
            gradient.setColorAt(1, QColor(2, 6, 23, 245))
            painter.fillRect(rect, gradient)

        super().paintEvent(event)
