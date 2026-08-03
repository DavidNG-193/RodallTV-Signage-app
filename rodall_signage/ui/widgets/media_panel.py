from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

class MediaPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mediaPanel")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_NativeWindow, True)

    def native_window_id(self) -> int:
        return int(self.winId())