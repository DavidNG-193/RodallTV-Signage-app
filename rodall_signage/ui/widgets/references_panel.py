from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QTimer, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rodall_signage.models import ReferenceItem, ReferenceSnapshot


class ReferencesPanel(QFrame):
    # Varias copias garantizan recorrido suficiente incluso en pantallas altas
    # con pocas referencias; el reinicio ocurre al comenzar la segunda copia.
    _REPEAT_COUNT = 8
    _REFERENCE_WIDTH = 92
    _OPERATION_WIDTH = 106
    _ITEM_HORIZONTAL_MARGINS = 22
    _ROW_SPACING = 7
    _FRAME_INTERVAL_MS = 34
    _SCROLL_SPEED_PX_PER_SECOND = 1000 / 34

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("referencesPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._references: list[ReferenceItem] = []
        self._cache_state = "missing"
        self._cycle_height = 0
        self._scroll_position = 0.0
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
        self._availability_label = QLabel("")
        self._availability_label.setObjectName("referencesAvailability")
        self._availability_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header_layout.addWidget(title, 1)
        header_layout.addWidget(self._count_label, 0)

        self._empty_label = QLabel("No hay referencias disponibles.")
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
        self._scroll_timer.setInterval(self._FRAME_INTERVAL_MS)
        self._scroll_timer.setTimerType(Qt.PreciseTimer)
        self._scroll_timer.timeout.connect(self._advance_references)
        self._scroll_clock = QElapsedTimer()

        self._root_layout.addLayout(header_layout)
        self._root_layout.addWidget(self._availability_label)
        self._root_layout.addWidget(self._empty_label)
        self._root_layout.addWidget(self._scroll, 1)
        self.show_empty_state()

    def set_snapshot(self, snapshot: ReferenceSnapshot) -> None:
        self.set_references(snapshot.references)

    def set_references(
        self,
        references: tuple[ReferenceItem, ...] | list[ReferenceItem],
    ) -> None:
        self._scroll_timer.stop()
        self._scroll_clock.invalidate()
        self._scroll_position = 0.0
        self._scroll.verticalScrollBar().setValue(0)
        self._first_item = None
        self._second_copy_first_item = None

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        self._references = list(references)
        concluded = sum(
            self._is_concluded(reference) for reference in self._references
        )
        self._count_label.setText(
            f"{len(self._references)}  -  {concluded} concluidas"
        )
        self._empty_label.setVisible(not self._references)
        self._scroll.setVisible(bool(self._references))

        if not self._references:
            self._empty_label.setText("No hay referencias activas.")
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
        self._update_column_widths(self.width())
        QTimer.singleShot(0, self._start_scrolling)

    def set_cache_state(self, state: str) -> None:
        self._cache_state = state.casefold()
        if self._cache_state in {"expired", "stale"}:
            self._availability_label.setText("Sin actualización reciente")
        else:
            self._availability_label.clear()

        if self._cache_state in {"missing", "invalid"} and not self._references:
            self.show_empty_state()

    def show_empty_state(self) -> None:
        self._references = []
        self._count_label.setText("0 activas")
        self._empty_label.setText("No hay referencias disponibles.")
        self._empty_label.setVisible(True)
        self._scroll.setVisible(False)

    def set_content_margins(self, padding: int) -> None:
        self._root_layout.setContentsMargins(
            padding,
            padding,
            padding,
            padding,
        )
        self._update_column_widths(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_column_widths(event.size().width())

    def _update_column_widths(self, panel_width: int) -> None:
        margins = self._root_layout.contentsMargins()
        available = max(
            panel_width
            - margins.left()
            - margins.right()
            - self._ITEM_HORIZONTAL_MARGINS
            - self._ROW_SPACING,
            0,
        )
        reference_width = max(self._REFERENCE_WIDTH, round(available * 0.35))
        operation_width = max(self._OPERATION_WIDTH, round(available * 0.37))

        for code in self.findChildren(QLabel, "referenceCodeBadge"):
            code.setFixedWidth(reference_width)
        for operation in self.findChildren(QLabel, "operationImport"):
            operation.setFixedWidth(operation_width)
        for operation in self.findChildren(QLabel, "operationExport"):
            operation.setFixedWidth(operation_width)

    def _build_reference_item(self, reference: ReferenceItem) -> QFrame:
        frame = QFrame()
        frame.setObjectName("referenceItem")
        frame.setMinimumHeight(96)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(7)

        code = QLabel(reference.reference_number)
        code.setObjectName("referenceCodeBadge")
        code.setAlignment(Qt.AlignCenter)
        code.setToolTip(reference.reference_number)
        code.setFixedWidth(self._REFERENCE_WIDTH)
        code.setWordWrap(True)

        description = QLabel(reference.client)
        description.setObjectName("referenceTitle")
        description.setToolTip(reference.client)
        description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        description.setWordWrap(True)

        status = QLabel(reference.status)
        status.setObjectName(self._status_object_name(reference))
        status.setAlignment(Qt.AlignCenter)
        status.setToolTip(reference.status)
        status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        status.setWordWrap(True)

        top_row.addWidget(code, 0)
        top_row.addWidget(status, 1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(7)

        location_text = reference.customs_office or "Sin aduana"
        if reference.document:
            location_text = f"{location_text} · {reference.document}"
        location = QLabel(location_text)
        location.setToolTip(location_text)
        location.setObjectName("referenceLocation")
        location.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        location.setWordWrap(True)

        operation = QLabel(
            ("▲  " if reference.operation_code.upper() == "E" else "▼  ")
            + reference.operation
        )
        operation.setObjectName(
            "operationExport"
            if reference.operation_code.upper() == "E"
            else "operationImport"
        )
        operation.setAlignment(Qt.AlignCenter)
        operation.setToolTip(reference.operation)
        operation.setFixedWidth(self._OPERATION_WIDTH)
        operation.setWordWrap(True)

        bottom_row.addWidget(operation, 0)
        bottom_row.addWidget(location, 1)

        layout.addLayout(top_row)
        layout.addWidget(description)
        layout.addLayout(bottom_row)
        return frame

    def _start_scrolling(self) -> None:
        self._list_layout.activate()
        self._list_widget.adjustSize()

        if self._first_item is not None and self._second_copy_first_item is not None:
            self._cycle_height = (
                self._second_copy_first_item.geometry().y()
                - self._first_item.geometry().y()
            )

        if self._cycle_height > 0:
            self._scroll_position = float(
                self._scroll.verticalScrollBar().value()
            )
            self._scroll_clock.start()
            self._scroll_timer.start()

    def _advance_references(self) -> None:
        elapsed_ms = self._FRAME_INTERVAL_MS
        if self._scroll_clock.isValid():
            elapsed_ms = max(self._scroll_clock.restart(), 1)
        else:
            self._scroll_position = float(
                self._scroll.verticalScrollBar().value()
            )

        self._advance_references_by(elapsed_ms)

    def _advance_references_by(self, elapsed_ms: int) -> None:
        if self._cycle_height <= 0:
            return

        scroll_bar = self._scroll.verticalScrollBar()
        maximum = scroll_bar.maximum()

        if maximum <= 0:
            return

        loop_at = min(self._cycle_height, maximum)
        distance = self._SCROLL_SPEED_PX_PER_SECOND * elapsed_ms / 1000
        next_position = self._scroll_position + distance
        if next_position >= loop_at:
            next_position %= loop_at

        self._scroll_position = next_position
        scroll_bar.setValue(round(self._scroll_position))

    @staticmethod
    def _status_object_name(reference: ReferenceItem) -> str:
        normalized = f"{reference.status_code} {reference.status}".upper()

        positive_keywords = (
            "CUENTA DE GASTOS",
        )
        prepositive_keywords = (
            "DESPACH",
            "LIBER",
            "ENTREG",
            "COMPLET",
            "VALIDA",
            "FINALIZ",
            "PREVIO",
            "AUTORIZ",
            "CONCLUID",
            "REVISAD",
            "COVE",
            "OPERACION",
            "PROFORMA REVISAD",
        )
        negative_keywords = (
            "PEND",
            "RECHAZ",
            "ERROR",
            "CANCELADO",
            "CANCELADA",
            "BLOQUE",
            "FALTA",
            "VENC",
        )

        if any(keyword in normalized for keyword in positive_keywords):
            return "statusPositive"
        if any(keyword in normalized for keyword in prepositive_keywords):
            return "statusPrePositive"
        if any(keyword in normalized for keyword in negative_keywords):
            return "statusNegative"
        return "statusNeutral"

    @staticmethod
    def _is_concluded(reference: ReferenceItem) -> bool:
        return ReferencesPanel._status_object_name(reference) == "statusPositive"
