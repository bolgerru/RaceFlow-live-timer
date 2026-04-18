"""API client: schedule polling, time synchronization with the server."""

import time
import logging

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from events_api import event_params

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 1.0
REQUEST_TIMEOUT_S = 5
# Discard sync measurements with RTT above this (too asymmetric to be accurate)
MAX_USABLE_RTT_MS = 1000


class ApiClient(QThread):
    """Background thread that polls the race schedule and keeps time in sync."""

    schedule_updated = pyqtSignal(list)
    connection_status = pyqtSignal(bool)
    sync_status = pyqtSignal(str)  # "syncing" | "synced" | "fallback"

    def __init__(
        self,
        server_url: str,
        event_id: str,
        session: requests.Session | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._server_url = server_url.rstrip("/")
        self._event_id = str(event_id)
        self._session = session if session is not None else requests.Session()
        self._running = True
        self._offset_ms: float = 0.0
        self._best_rtt_ms: float = float("inf")
        self._sync_established = False

    def synchronized_now_ms(self) -> float:
        return time.time() * 1000 + self._offset_ms

    @property
    def is_synced(self) -> bool:
        return self._sync_established

    def run(self):
        while self._running:
            self._do_time_sync()
            self._poll_schedule()

            deadline = time.time() + POLL_INTERVAL_S
            while self._running and time.time() < deadline:
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(3000)

    def _poll_schedule(self):
        try:
            resp = self._session.get(
                f"{self._server_url}/api/schedule",
                params=event_params(self._event_id),
                timeout=REQUEST_TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                self.schedule_updated.emit(data)
                self.connection_status.emit(True)
            else:
                log.warning("Schedule response is not a list: %s", type(data))
                self.connection_status.emit(False)
        except Exception as exc:
            log.debug("Schedule poll failed: %s", exc)
            self.connection_status.emit(False)

    def _do_time_sync(self):
        is_initial = not self._sync_established
        if is_initial:
            self.sync_status.emit("syncing")

        try:
            t_start = time.time() * 1000
            resp = self._session.post(
                f"{self._server_url}/api/time-sync/init",
                params=event_params(self._event_id),
                json={"clientTime": t_start},
                timeout=REQUEST_TIMEOUT_S,
            )
            t_end = time.time() * 1000
            resp.raise_for_status()
            data = resp.json()

            server_time = data["serverTime"]
            rtt = t_end - t_start
            new_offset = (server_time + rtt / 2) - t_end

            if rtt > MAX_USABLE_RTT_MS:
                log.debug("Discarding sync: RTT %.0fms too high", rtt)
                if is_initial:
                    # On first sync, accept anything rather than having no offset
                    self._offset_ms = new_offset
                    self._best_rtt_ms = rtt
                    self._sync_established = True
                    self.sync_status.emit("synced")
                return

            # Only update offset if this measurement is at least as good as
            # the best we've seen.  Lower RTT = less network asymmetry =
            # more accurate offset.
            if rtt <= self._best_rtt_ms:
                self._offset_ms = new_offset
                self._best_rtt_ms = rtt
                log.debug("Sync updated: offset=%.1fms rtt=%.0fms (new best)", self._offset_ms, rtt)
            else:
                log.debug("Sync kept: offset=%.1fms (rtt %.0fms > best %.0fms)", self._offset_ms, rtt, self._best_rtt_ms)

            if not self._sync_established:
                self._sync_established = True
                log.info("Initial sync: offset=%.1fms rtt=%.0fms", self._offset_ms, rtt)
            self.sync_status.emit("synced")

        except Exception as exc:
            log.debug("Time sync failed: %s", exc)
            if is_initial:
                self.sync_status.emit("fallback")
