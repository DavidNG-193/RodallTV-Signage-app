from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rodall_signage.models import DailyReference


class ReferencesPanel(QFrame):
    _REPEAT_COUNT = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("referencesPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._references: list[DailyReference] = []
        self._cycle_height = 0
        self._first_item: QFrame | None = None
        self._second_copy_first_item: QFrame | None = None

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("REFERENCIAS DEL DÍA")
        title.setObjectName("cardTitle")
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._count_label = QLabel("0 activas")
        self._count_label.setObjectName("referencesCount")
        self._count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(title, 1)
        header_layout.addWidget(self._count_label, 0)

        self._empty_label = QLabel("No hay referencias para mostrar.")
        self._empty_label.setObjectName("emptyState")
        self._empty_label.setWordWrap(True)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_widget.setObjectName("referencesViewport")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(9)
        self._scroll.setWidget(self._list_widget)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(34)
        self._scroll_timer.timeout.connect(self._advance_references)

        self._root_layout.addLayout(header_layout)
        self._root_layout.addWidget(self._empty_label)
        self._root_layout.addWidget(self._scroll, 1)
        self.set_references([])

    def set_references(self, references: list[DailyReference]) -> None:
        self._scroll_timer.stop()
        self._scroll.verticalScrollBar().setValue(0)
        self._first_item = None
        self._second_copy_first_item = None

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        self._references = sorted(references, key=lambda item: item.sequence)
        dispatched = sum(
            "DESPACH" in reference.status.upper()
            for reference in self._references
        )
        self._count_label.setText(
            f"{len(self._references)}  ·  {dispatched} despachadas"
        )
        self._empty_label.setVisible(not self._references)
        self._scroll.setVisible(bool(self._references))

        if not self._references:
            self._cycle_height = 0
            return

        for copy_index in range(self._REPEAT_COUNT):
            for reference_index, reference in enumerate(self._references):
                item = self._build_reference_item(reference)
                self._list_layout.addWidget(item)
                if copy_index == 0 and reference_index == 0:
                    self._first_item = item
                if copy_index == 1 and reference_index == 0:
                    self._second_copy_first_item = item

        self._list_layout.addStretch(1)
        self._list_layout.activate()
        QTimer.singleShot(0, self._start_scrolling)

    def set_content_margins(self, padding: int) -> None:
        self._root_layout.setContentsMargins(
            padding,
            padding,
            padding,
            padding,
        )

    def _build_reference_item(self, reference: DailyReference) -> QFrame:
        frame = QFrame()
        frame.setObjectName("referenceItem")
        frame.setMinimumHeight(64)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(9)

        code = QLabel(reference.code)
        code.setObjectName("referenceCodeBadge")
        code.setAlignment(Qt.AlignCenter)
        code.setFixedWidth(76)

        identity_layout = QVBoxLayout()
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(0)

        display_description = (
            reference.description
            if len(reference.description) <= 18
            else f"{reference.description[:17]}…"
        )
        description = QLabel(display_description)
        description.setObjectName("referenceTitle")
        description.setToolTip(reference.description)
        description.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        location = QLabel(reference.location or "Sin ubicación")
        location.setObjectName("referenceLocation")
        identity_layout.addWidget(description)
        identity_layout.addWidget(location)

        badges_layout = QVBoxLayout()
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(3)

        operation = QLabel(
            ("▲  " if reference.operation_type.casefold().startswith("export") else "▼  ")
            + reference.operation_type
        )
        operation.setObjectName(
            "operationExport"
            if reference.operation_type.casefold().startswith("export")
            else "operationImport"
        )
        operation.setAlignment(Qt.AlignCenter)
        operation.setFixedWidth(102)

        status = QLabel(reference.status)
        normalized_status = reference.status.upper()
        status.setObjectName(
            "statusDelivered"
            if "DESPACH" in normalized_status
            else "statusPending"
            if "PEND" in normalized_status
            else "statusProgress"
        )
        status.setAlignment(Qt.AlignCenter)
        status.setFixedWidth(92)

        badges_layout.addWidget(operation)
        badges_layout.addWidget(status)

        layout.addWidget(code, 0)
        layout.addLayout(identity_layout, 1)
        layout.addLayout(badges_layout, 0)
        return frame

    def _start_scrolling(self) -> None:
        self._list_layout.activate()
        self._list_widget.adjustSize()

        if self._first_item is not None and self._second_copy_first_item is not None:
            self._cycle_height = (
                self._second_copy_first_item.geometry().y()
                - self._first_item.geometry().y()
            )

        if self._cycle_height > 0 and self.isVisible():
            self._scroll_timer.start()

    def _advance_references(self) -> None:
        if self._cycle_height <= 0:
            return

        scroll_bar = self._scroll.verticalScrollBar()
        next_value = scroll_bar.value() + 1
        scroll_bar.setValue(
            0 if next_value >= self._cycle_height else next_value
        )
