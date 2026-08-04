from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

from rodall_signage.models import MediaItem, MediaKind
from rodall_signage.models.local_playlist import LocalPlaylist
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.mpv_models import MpvEvent
from rodall_signage.player.playback_models import (
    PlaybackSnapshot,
    PlaybackState,
)


logger = logging.getLogger(__name__)


class PlaybackCoordinator(QObject):
    snapshot_changed = Signal(PlaybackSnapshot)
    current_item_changed = Signal(MediaItem)
    error_occurred = Signal(str)

    def __init__(
        self,
        player: MpvController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._player = player
        self._playlist: LocalPlaylist | None = None
        self._current_index = -1
        self._state = PlaybackState.IDLE
        self._is_running = False
        self._consecutive_failures = 0
        # Un ``end-file`` del elemento anterior puede llegar después de
        # enviar ``loadfile`` para el siguiente. Solo aceptamos el fin del
        # elemento actual una vez que mpv haya confirmado ``file-loaded``.
        self._current_item_loaded = False

        self._image_timer = QTimer(self)
        self._image_timer.setSingleShot(True)
        self._image_timer.timeout.connect(self.play_next)

        self._player.playback_event.connect(self._on_mpv_event)
        self._player.error_occurred.connect(self._on_player_error)

    @property
    def playlist(self) -> LocalPlaylist | None:
        return self._playlist

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_playlist(self, playlist: LocalPlaylist) -> None:
        playlist.validate()
        self.stop()

        self._playlist = playlist
        self._current_index = -1
        self._consecutive_failures = 0
        self._current_item_loaded = False

        logger.info(
            "Playlist asignada. id=%s version=%s",
            playlist.id,
            playlist.version,
        )

        self._publish_snapshot(
            PlaybackState.IDLE,
            "Playlist lista.",
        )

    def start(self) -> None:
        if self._playlist is None:
            self._report_error("No existe una playlist local cargada.")
            return

        if not self._player.is_ready:
            self._report_error("mpv todavía no está listo.")
            return

        if self._is_running:
            logger.warning("La playlist ya está ejecutándose.")
            return

        self._is_running = True
        self._current_index = -1
        self._consecutive_failures = 0
        self._current_item_loaded = False
        logger.info("Iniciando playlist local.")
        self.play_next()

    def stop(self) -> None:
        self._is_running = False
        self._image_timer.stop()
        self._current_index = -1
        self._current_item_loaded = False

        self._publish_snapshot(
            PlaybackState.STOPPED,
            "Reproducción detenida.",
        )

    def play_next(self) -> None:
        if not self._is_running or self._playlist is None:
            return

        if not self._playlist.items:
            self._report_error("La playlist está vacía.")
            return

        self._image_timer.stop()
        self._current_index = (
            self._current_index + 1
        ) % len(self._playlist.items)

        item = self._playlist.items[self._current_index]

        if not item.path.is_file():
            self._handle_item_failure(
                item,
                f"No existe el archivo: {item.path}",
            )
            return

        self._publish_snapshot(
            PlaybackState.LOADING,
            f"Cargando {item.path.name}",
            item,
        )

        logger.info(
            "Cargando elemento. index=%s id=%s path=%s kind=%s",
            self._current_index,
            item.id,
            item.path,
            item.kind,
        )

        self._current_item_loaded = False
        self._player.load(item.path)
        self.current_item_changed.emit(item)

        if item.kind == MediaKind.IMAGE:
            duration = item.duration_seconds or 10
            self._image_timer.start(duration * 1000)
            self._publish_snapshot(
                PlaybackState.WAITING_IMAGE,
                f"Mostrando imagen durante {duration} segundos.",
                item,
            )
        else:
            self._publish_snapshot(
                PlaybackState.PLAYING,
                "Reproduciendo video.",
                item,
            )

        self._consecutive_failures = 0

    def _on_mpv_event(self, event: MpvEvent) -> None:
        if not self._is_running:
            return

        raw = event.raw or {}

        if event.name == "file-loaded":
            self._current_item_loaded = True
            self._consecutive_failures = 0
            current = self._current_item()
            logger.info(
                "mpv confirmó el elemento actual. id=%s path=%s",
                current.id if current is not None else "desconocido",
                current.path if current is not None else "desconocido",
            )
            return

        if (
            event.name == "property-change"
            and raw.get("name") == "eof-reached"
            and raw.get("data") is True
        ):
            if not self._current_item_loaded:
                logger.debug(
                    "Ignorando eof-reached atrasado durante la transición."
                )
                return

            logger.info(
                "mpv alcanzó el final del elemento actual mediante "
                "eof-reached."
            )
            self._advance_after_natural_end()
            return

        if event.name == "end-file":
            reason = str(raw.get("reason", ""))

            if reason == "error":
                self._handle_item_failure(
                    self._current_item(),
                    "mpv reportó un error al reproducir el archivo.",
                )
                return

            if not self._current_item_loaded:
                logger.info(
                    "Ignorando end-file atrasado durante la transición. "
                    "reason=%s current_id=%s",
                    reason,
                    (
                        self._current_item().id
                        if self._current_item() is not None
                        else "desconocido"
                    ),
                )
                return

            if reason != "eof":
                logger.debug(
                    "Ignorando end-file que no corresponde a fin natural. "
                    "reason=%s",
                    reason,
                )
                return

            self._advance_after_natural_end()

    def _on_player_error(self, message: str) -> None:
        if self._is_running:
            self._handle_item_failure(
                self._current_item(),
                message,
            )

    def _advance_after_natural_end(self) -> None:
        current = self._current_item()

        # Las imágenes avanzan exclusivamente mediante su temporizador para
        # respetar durationSeconds, aunque mpv publique eof-reached.
        if current is None or current.kind == MediaKind.IMAGE:
            return

        self._current_item_loaded = False
        self.play_next()

    def _handle_item_failure(
        self,
        item: MediaItem | None,
        message: str,
    ) -> None:
        self._current_item_loaded = False
        self._consecutive_failures += 1

        item_name = item.path.name if item is not None else "desconocido"
        full_message = f"Error en {item_name}: {message}"

        logger.error(full_message)
        self.error_occurred.emit(full_message)
        self._publish_snapshot(
            PlaybackState.ERROR,
            full_message,
            item,
        )

        if (
            self._playlist is not None
            and self._consecutive_failures >= len(self._playlist.items)
        ):
            self._is_running = False
            self._report_error(
                "Ningún elemento de la playlist pudo reproducirse."
            )
            return

        QTimer.singleShot(500, self.play_next)

    def _current_item(self) -> MediaItem | None:
        if self._playlist is None:
            return None

        if not 0 <= self._current_index < len(self._playlist.items):
            return None

        return self._playlist.items[self._current_index]

    def _publish_snapshot(
        self,
        state: PlaybackState,
        message: str,
        item: MediaItem | None = None,
    ) -> None:
        self._state = state

        self.snapshot_changed.emit(
            PlaybackSnapshot(
                state=state,
                playlist_id=(
                    self._playlist.id
                    if self._playlist is not None
                    else None
                ),
                playlist_version=(
                    self._playlist.version
                    if self._playlist is not None
                    else None
                ),
                current_index=(
                    self._current_index
                    if self._current_index >= 0
                    else None
                ),
                total_items=(
                    len(self._playlist.items)
                    if self._playlist is not None
                    else 0
                ),
                current_item=item or self._current_item(),
                message=message,
            )
        )

    def _report_error(self, message: str) -> None:
        logger.error(message)
        self.error_occurred.emit(message)
        self._publish_snapshot(
            PlaybackState.ERROR,
            message,
        )
