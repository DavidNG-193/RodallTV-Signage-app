from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from rodall_signage.api.api_models import SyncReport, SyncResult
from rodall_signage.api.device_api_client import DeviceApiClient
from rodall_signage.models.local_playlist import LocalPlaylist
from rodall_signage.player.playback_coordinator import PlaybackCoordinator
from rodall_signage.sync.content_store import ContentStore
from rodall_signage.sync.manifest_models import ActiveManifest
from rodall_signage.sync.manifest_playlist_adapter import (
    ManifestPlaylistAdapter,
)
from rodall_signage.sync.manifest_store import ManifestStore


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _PreparedSync:
    manifest: ActiveManifest
    playlist: LocalPlaylist
    started_at: datetime
    downloaded_files_count: int


class _SynchronizationWorker(QObject):
    prepared = Signal(object)
    no_changes = Signal(str)
    failed = Signal(str)
    completed = Signal(str)

    def __init__(
        self,
        api_client: DeviceApiClient,
        manifest_store: ManifestStore,
        content_store: ContentStore,
        playlist_adapter: ManifestPlaylistAdapter,
    ) -> None:
        super().__init__()
        self._api_client = api_client
        self._manifest_store = manifest_store
        self._content_store = content_store
        self._playlist_adapter = playlist_adapter

    @Slot()
    def synchronize(self) -> None:
        started_at = datetime.now(timezone.utc)
        manifest: ActiveManifest | None = None
        playlist_id: str | None = None
        playlist_version = 0
        downloaded = 0

        try:
            self._ensure_not_interrupted()
            assignment = self._api_client.get_assignment()
            playlist_id = assignment.playlist_id
            playlist_version = assignment.playlist_version
            active = self._manifest_store.load()

            if not assignment.has_assignment:
                message = (
                    "El dispositivo no tiene playlist asignada; "
                    "se conserva el contenido local."
                )
                self._report(
                    SyncResult.NO_CHANGES,
                    None,
                    0,
                    message,
                    started_at,
                    0,
                    0,
                )
                self.no_changes.emit(message)
                return

            same_active_version = (
                active is not None
                and active.playlist_id == assignment.playlist_id
                and active.playlist_version == assignment.playlist_version
            )
            active_files_valid = (
                same_active_version
                and active is not None
                and all(
                    self._content_store.is_valid(item)
                    for item in active.items
                )
            )

            if active_files_valid and not assignment.requires_sync:
                message = "La playlist local ya está actualizada."
                self._report(
                    SyncResult.NO_CHANGES,
                    assignment.playlist_id,
                    assignment.playlist_version,
                    message,
                    started_at,
                    0,
                    0,
                )
                self.no_changes.emit(message)
                return

            manifest = self._manifest_store.parse(
                self._api_client.get_manifest()
            )
            self._validate_assignment(manifest, assignment)

            for item in manifest.items:
                self._ensure_not_interrupted()
                if self._content_store.is_valid(item):
                    continue

                with self._api_client.download(item.download_url) as response:
                    self._content_store.save_response_atomic(item, response)
                downloaded += 1

            invalid_items = [
                item.original_file_name
                for item in manifest.items
                if not self._content_store.is_valid(item)
            ]
            if invalid_items:
                raise ValueError(
                    "No se validaron todos los archivos: "
                    + ", ".join(invalid_items)
                )

            playlist = self._playlist_adapter.to_playlist(manifest)
            self._ensure_not_interrupted()
            self._manifest_store.save_atomic(manifest)
            self.prepared.emit(
                _PreparedSync(
                    manifest=manifest,
                    playlist=playlist,
                    started_at=started_at,
                    downloaded_files_count=downloaded,
                )
            )
        except InterruptedError:
            logger.info("Sincronización cancelada durante el cierre.")
            self.failed.emit("Sincronización cancelada durante el cierre.")
        except Exception as error:
            message = str(error) or type(error).__name__
            logger.exception("Falló la sincronización: %s", message)
            self._try_report_failure(
                playlist_id=(
                    manifest.playlist_id if manifest is not None else playlist_id
                ),
                playlist_version=(
                    manifest.playlist_version
                    if manifest is not None
                    else playlist_version
                ),
                message=message,
                started_at=started_at,
                downloaded=downloaded,
            )
            self.failed.emit(message)

    @Slot(object)
    def finalize(self, prepared: _PreparedSync) -> None:
        valid_names = {
            item.stored_file_name for item in prepared.manifest.items
        }
        deleted = self._content_store.delete_obsolete(valid_names)
        message = "Sincronización aplicada correctamente."

        try:
            self._report(
                SyncResult.SUCCESS,
                prepared.manifest.playlist_id,
                prepared.manifest.playlist_version,
                message,
                prepared.started_at,
                prepared.downloaded_files_count,
                deleted,
            )
            self.completed.emit(message)
        except Exception as error:
            report_message = (
                "El contenido fue activado, pero no se pudo reportar el "
                f"resultado: {error}"
            )
            logger.exception(report_message)
            self.failed.emit(report_message)

    @Slot(object, str)
    def reject_activation(
        self,
        prepared: _PreparedSync,
        message: str,
    ) -> None:
        self._try_report_failure(
            playlist_id=prepared.manifest.playlist_id,
            playlist_version=prepared.manifest.playlist_version,
            message=message,
            started_at=prepared.started_at,
            downloaded=prepared.downloaded_files_count,
        )
        self.failed.emit(message)

    def _report(
        self,
        result: SyncResult,
        playlist_id: str | None,
        version: int,
        message: str | None,
        started_at: datetime,
        downloaded: int,
        deleted: int,
    ) -> None:
        self._api_client.report_sync(
            SyncReport(
                result=result,
                playlist_id=playlist_id,
                synced_version=version,
                message=message,
                downloaded_files_count=downloaded,
                deleted_files_count=deleted,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        )

    def _try_report_failure(
        self,
        playlist_id: str | None,
        playlist_version: int,
        message: str,
        started_at: datetime,
        downloaded: int,
    ) -> None:
        try:
            self._report(
                SyncResult.FAILED,
                playlist_id,
                playlist_version,
                message[:1000],
                started_at,
                downloaded,
                0,
            )
        except Exception:
            logger.exception("No fue posible reportar el fallo al servidor.")

    @staticmethod
    def _validate_assignment(manifest, assignment) -> None:
        if manifest.playlist_id != assignment.playlist_id:
            raise ValueError(
                "El manifiesto no corresponde a la playlist asignada."
            )
        if manifest.playlist_version != assignment.playlist_version:
            raise ValueError(
                "La versión del manifiesto no coincide con la asignación."
            )

    @staticmethod
    def _ensure_not_interrupted() -> None:
        if QThread.currentThread().isInterruptionRequested():
            raise InterruptedError


class SynchronizationService(QObject):
    status_changed = Signal(str)
    sync_completed = Signal()
    sync_failed = Signal(str)

    _sync_requested = Signal()
    _finalize_requested = Signal(object)
    _activation_rejected = Signal(object, str)

    def __init__(
        self,
        api_client: DeviceApiClient,
        manifest_store: ManifestStore,
        content_store: ContentStore,
        playlist_adapter: ManifestPlaylistAdapter,
        playback: PlaybackCoordinator,
        interval_seconds: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manifest_store = manifest_store
        self._content_store = content_store
        self._playlist_adapter = playlist_adapter
        self._playback = playback
        self._in_progress = False
        self._stopping = False

        self._timer = QTimer(self)
        self._timer.setInterval(max(interval_seconds, 15) * 1000)
        self._timer.timeout.connect(self.synchronize)

        self._thread = QThread(self)
        self._thread.setObjectName("rodall-synchronization")
        self._worker = _SynchronizationWorker(
            api_client,
            manifest_store,
            content_store,
            playlist_adapter,
        )
        self._worker.moveToThread(self._thread)
        self._sync_requested.connect(self._worker.synchronize)
        self._finalize_requested.connect(self._worker.finalize)
        self._activation_rejected.connect(self._worker.reject_activation)
        self._worker.prepared.connect(self._activate_prepared)
        self._worker.no_changes.connect(self._on_no_changes)
        self._worker.failed.connect(self._on_failed)
        self._worker.completed.connect(self._on_completed)

    def load_offline(self) -> bool:
        if self._stopping:
            return False

        manifest = self._manifest_store.load()

        if manifest is None:
            self.status_changed.emit("No existe contenido local activo.")
            return False

        invalid = [
            item.original_file_name
            for item in manifest.items
            if not self._content_store.is_valid(item)
        ]
        if invalid:
            message = (
                "El contenido offline está incompleto; se conserva sin "
                "activarlo: " + ", ".join(invalid)
            )
            logger.warning(message)
            self.status_changed.emit(message)
            return False

        try:
            playlist = self._playlist_adapter.to_playlist(manifest)
            self._playback.set_playlist(playlist)
            self._playback.start()
        except Exception as error:
            message = f"No fue posible activar el contenido offline: {error}"
            logger.exception(message)
            self.status_changed.emit(message)
            return False

        self.status_changed.emit(
            f"Contenido local activo: {manifest.playlist_name}."
        )
        return True

    def start(self) -> None:
        self._stopping = False
        if not self._thread.isRunning():
            self._thread.start()
        if not self._timer.isActive():
            self._timer.start()
        self.synchronize()

    def stop(self) -> None:
        self._stopping = True
        self._timer.stop()
        self._in_progress = False

        if self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            if not self._thread.wait(35000):
                logger.error(
                    "El hilo de sincronización no terminó dentro del plazo."
                )

    @Slot()
    def synchronize(self) -> None:
        if self._stopping or self._in_progress:
            logger.debug("Se omitió un ciclo de sincronización concurrente.")
            return

        if not self._thread.isRunning():
            self._thread.start()

        self._in_progress = True
        self.status_changed.emit("Consultando actualizaciones...")
        self._sync_requested.emit()

    @Slot(object)
    def _activate_prepared(self, prepared: _PreparedSync) -> None:
        if self._stopping:
            return

        try:
            self._playback.set_playlist(prepared.playlist)
            self._playback.start()
        except Exception as error:
            message = f"No fue posible activar la nueva playlist: {error}"
            logger.exception(message)
            self._activation_rejected.emit(prepared, message)
            return

        self.status_changed.emit(
            f"Playlist {prepared.manifest.playlist_name} activada."
        )
        self._finalize_requested.emit(prepared)

    @Slot(str)
    def _on_no_changes(self, message: str) -> None:
        self._in_progress = False
        if self._stopping:
            return
        self.status_changed.emit(message)
        self.sync_completed.emit()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._in_progress = False
        if self._stopping:
            return
        self.status_changed.emit(
            "Sin conexión o sincronización fallida; se conserva "
            "el contenido local."
        )
        self.sync_failed.emit(message)

    @Slot(str)
    def _on_completed(self, message: str) -> None:
        self._in_progress = False
        if self._stopping:
            return
        self.status_changed.emit(message)
        self.sync_completed.emit()
