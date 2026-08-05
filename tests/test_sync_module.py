from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from rodall_signage.api.api_models import (
    AssignmentStatus,
    HeartbeatResult,
    SyncReport,
    SyncResult,
)
from rodall_signage.api.device_api_client import DeviceApiClient
from rodall_signage.services.heartbeat_service import HeartbeatService
from rodall_signage.sync.content_store import ContentStore
from rodall_signage.sync.manifest_models import ActiveManifest, ManifestItem
from rodall_signage.sync.manifest_playlist_adapter import (
    ManifestPlaylistAdapter,
)
from rodall_signage.sync.manifest_store import ManifestStore
from rodall_signage.sync.synchronization_service import (
    SynchronizationService,
    _SynchronizationWorker,
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self._content), chunk_size):
            yield self._content[offset : offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class FakeJsonResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/heartbeat"):
            return FakeJsonResponse(
                {
                    "serverTimeUtc": "2026-08-04T00:00:00Z",
                    "pendingPowerCommand": {"commandId": "command-1"},
                }
            )
        return FakeJsonResponse({"accepted": True})

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeJsonResponse(
            {
                "hasAssignment": True,
                "playlistId": "playlist-1",
                "playlistVersion": None,
                "requiresSync": True,
            }
        )


class FakeApiClient:
    def __init__(
        self,
        assignment: AssignmentStatus,
        manifest_payload: dict,
        downloads: dict[str, bytes],
    ) -> None:
        self.assignment = assignment
        self.manifest_payload = manifest_payload
        self.downloads = downloads
        self.download_calls: list[str] = []
        self.reports = []

    def get_assignment(self) -> AssignmentStatus:
        return self.assignment

    def get_manifest(self) -> dict:
        return self.manifest_payload

    def download(self, url: str) -> FakeResponse:
        self.download_calls.append(url)
        return FakeResponse(self.downloads[url])

    def report_sync(self, report) -> None:
        self.reports.append(report)

    def heartbeat(self) -> HeartbeatResult:
        return HeartbeatResult(server_time="2026-08-04T00:00:00Z")


class FakePlayback:
    def __init__(self) -> None:
        self.playlist = None
        self.started = False

    def set_playlist(self, playlist) -> None:
        self.playlist = playlist

    def start(self) -> None:
        self.started = True


def manifest_item(
    content: bytes,
    *,
    stored_name: str = "media.bin",
    expected_hash: str | None = None,
) -> ManifestItem:
    return ManifestItem(
        playlist_item_id="playlist-item-1",
        media_id="media-1",
        position=0,
        original_file_name="media.png",
        stored_file_name=stored_name,
        media_type="Image",
        mime_type="image/png",
        file_size_bytes=len(content),
        hash_sha256=expected_hash or hashlib.sha256(content).hexdigest(),
        custom_duration_seconds=5,
        download_url="/download/media-1",
    )


def active_manifest(item: ManifestItem, version: int = 1) -> ActiveManifest:
    return ActiveManifest(
        playlist_id="playlist-1",
        playlist_name="Playlist de prueba",
        playlist_version=version,
        items=(item,),
    )


def manifest_payload(manifest: ActiveManifest) -> dict:
    item = manifest.items[0]
    return {
        "hasAssignment": True,
        "playlistId": manifest.playlist_id,
        "playlistName": manifest.playlist_name,
        "playlistVersion": manifest.playlist_version,
        "requiresSync": True,
        "items": [
            {
                "playlistItemId": item.playlist_item_id,
                "mediaId": item.media_id,
                "position": item.position,
                "originalFileName": item.original_file_name,
                "storedFileName": item.stored_file_name,
                "mediaType": item.media_type,
                "mimeType": item.mime_type,
                "fileSizeBytes": item.file_size_bytes,
                "hashSha256": item.hash_sha256,
                "customDurationSeconds": item.custom_duration_seconds,
                "downloadUrl": item.download_url,
            }
        ],
    }


class SyncModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        root = Path(__file__).parents[1] / "runtime" / "cache" / "sync-tests"
        root.mkdir(parents=True, exist_ok=True)
        self._clear_directory(root)
        self.root = root
        self.content_store = ContentStore(root / "content")
        self.manifest_store = ManifestStore(root / "active_manifest.json")
        self.adapter = ManifestPlaylistAdapter(self.content_store)

    def tearDown(self) -> None:
        self._clear_directory(self.root)

    @staticmethod
    def _clear_directory(root: Path) -> None:
        for path in root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def test_success_downloads_validates_activates_and_reports(self) -> None:
        content = b"valid image content"
        item = manifest_item(content)
        manifest = active_manifest(item)
        api = FakeApiClient(
            AssignmentStatus(True, "playlist-1", 1, True),
            manifest_payload(manifest),
            {item.download_url: content},
        )
        worker = _SynchronizationWorker(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
        )
        prepared = []
        worker.prepared.connect(prepared.append)
        obsolete = self.root / "content" / "obsolete.bin"
        obsolete.write_bytes(b"obsolete")

        worker.synchronize()

        self.assertEqual(len(prepared), 1)
        self.assertTrue(self.content_store.is_valid(item))
        self.assertEqual(self.manifest_store.load(), manifest)

        worker.finalize(prepared[0])

        self.assertEqual(api.reports[-1].result, SyncResult.SUCCESS)
        self.assertEqual(api.reports[-1].downloaded_files_count, 1)
        self.assertEqual(api.reports[-1].deleted_files_count, 1)
        self.assertFalse(obsolete.exists())

    def test_no_changes_does_not_download(self) -> None:
        content = b"already cached"
        item = manifest_item(content)
        manifest = active_manifest(item)
        self.content_store.path_for(item).write_bytes(content)
        self.manifest_store.save_atomic(manifest)
        api = FakeApiClient(
            AssignmentStatus(True, "playlist-1", 1, False),
            manifest_payload(manifest),
            {},
        )
        worker = _SynchronizationWorker(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
        )

        worker.synchronize()

        self.assertEqual(api.download_calls, [])
        self.assertEqual(api.reports[-1].result, SyncResult.NO_CHANGES)

    def test_no_assignment_preserves_active_content(self) -> None:
        content = b"assigned before"
        item = manifest_item(content)
        manifest = active_manifest(item)
        self.content_store.path_for(item).write_bytes(content)
        self.manifest_store.save_atomic(manifest)
        api = FakeApiClient(
            AssignmentStatus(False, None, 0, True),
            {},
            {},
        )
        worker = _SynchronizationWorker(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
        )

        worker.synchronize()

        self.assertEqual(self.manifest_store.load(), manifest)
        self.assertTrue(self.content_store.is_valid(item))
        self.assertEqual(api.reports[-1].result, SyncResult.NO_CHANGES)

    def test_bad_hash_preserves_previous_manifest_and_removes_part(self) -> None:
        old_content = b"old valid content"
        old_item = manifest_item(old_content, stored_name="old.bin")
        old_manifest = active_manifest(old_item, version=1)
        self.content_store.path_for(old_item).write_bytes(old_content)
        self.manifest_store.save_atomic(old_manifest)

        new_content = b"new corrupt content"
        new_item = manifest_item(
            new_content,
            stored_name="new.bin",
            expected_hash="0" * 64,
        )
        new_manifest = active_manifest(new_item, version=2)
        api = FakeApiClient(
            AssignmentStatus(True, "playlist-1", 2, True),
            manifest_payload(new_manifest),
            {new_item.download_url: new_content},
        )
        worker = _SynchronizationWorker(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
        )

        worker.synchronize()

        self.assertEqual(self.manifest_store.load(), old_manifest)
        self.assertTrue(self.content_store.is_valid(old_item))
        self.assertFalse(
            self.content_store.path_for(new_item)
            .with_suffix(".bin.part")
            .exists()
        )
        self.assertEqual(api.reports[-1].result, SyncResult.FAILED)

    def test_offline_load_activates_only_valid_content(self) -> None:
        content = b"offline content"
        item = manifest_item(content)
        manifest = active_manifest(item)
        self.content_store.path_for(item).write_bytes(content)
        self.manifest_store.save_atomic(manifest)
        playback = FakePlayback()
        api = FakeApiClient(
            AssignmentStatus(True, "playlist-1", 1, False),
            manifest_payload(manifest),
            {},
        )
        service = SynchronizationService(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
            playback,
            interval_seconds=60,
        )

        self.assertTrue(service.load_offline())
        self.assertTrue(playback.started)
        self.assertEqual(playback.playlist.id, "playlist-1")
        service.stop()

    def test_rejects_path_traversal_in_stored_name(self) -> None:
        item = manifest_item(b"content", stored_name="../escape.bin")

        with self.assertRaises(ValueError):
            self.content_store.path_for(item)

    def test_synchronization_and_heartbeat_run_in_worker_threads(self) -> None:
        content = b"threaded content"
        item = manifest_item(content)
        manifest = active_manifest(item)
        self.content_store.path_for(item).write_bytes(content)
        self.manifest_store.save_atomic(manifest)
        api = FakeApiClient(
            AssignmentStatus(True, "playlist-1", 1, False),
            manifest_payload(manifest),
            {},
        )
        playback = FakePlayback()
        sync = SynchronizationService(
            api,
            self.manifest_store,
            self.content_store,
            self.adapter,
            playback,
            interval_seconds=60,
        )
        heartbeat = HeartbeatService(api, interval_seconds=30)
        loop = QEventLoop()
        results = {"sync": False, "heartbeat": False}

        def mark_sync() -> None:
            results["sync"] = True
            if all(results.values()):
                loop.quit()

        def mark_heartbeat(_result) -> None:
            results["heartbeat"] = True
            if all(results.values()):
                loop.quit()

        sync.sync_completed.connect(mark_sync)
        heartbeat.heartbeat_ok.connect(mark_heartbeat)
        QTimer.singleShot(3000, loop.quit)
        sync.start()
        heartbeat.start()
        loop.exec()
        heartbeat.stop()
        sync.stop()

        self.assertEqual(results, {"sync": True, "heartbeat": True})

    def test_api_client_matches_backend_transport_contract(self) -> None:
        settings = SimpleNamespace(
            api_base_url="http://backend:5026",
            device_id="device-1",
            device_token="secret-token",
        )
        client = DeviceApiClient(settings)
        session = FakeSession()
        client._thread_local.session = session

        heartbeat = client.heartbeat()
        assignment = client.get_assignment()
        started = datetime(2026, 8, 4, tzinfo=timezone.utc)
        client.report_sync(
            SyncReport(
                result=SyncResult.NO_CHANGES,
                playlist_id="playlist-1",
                synced_version=1,
                message=None,
                downloaded_files_count=0,
                deleted_files_count=0,
                started_at=started,
                finished_at=started,
            )
        )

        self.assertEqual(heartbeat.server_time, "2026-08-04T00:00:00Z")
        self.assertEqual(
            heartbeat.pending_power_command,
            {"commandId": "command-1"},
        )
        self.assertEqual(assignment.playlist_version, 0)
        report_call = session.calls[-1]
        self.assertEqual(report_call[2]["json"]["result"], "NoChanges")
        self.assertIn("startedAt", report_call[2]["json"])
        self.assertIn("finishedAt", report_call[2]["json"])
        self.assertEqual(
            report_call[2]["headers"]["X-Device-Token"],
            "secret-token",
        )


if __name__ == "__main__":
    unittest.main()
