from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

class ApplicationStatusBar(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("applicationStatusBar")
        self.setText("Preparando aplicación...")
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

    def set_bar_height(self, height: int) -> None:
        self.setFixedHeight(height)