"""Cold start: load events, show event picker every launch, POST /api/events/select."""

from __future__ import annotations

import logging

import requests
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QVBoxLayout

from config import load_config, save_config
from event_selector_dialog import EventSelectorDialog
from events_api import fetch_events, select_event

log = logging.getLogger(__name__)


def run_event_bootstrap(app: QApplication, session: requests.Session, base_url: str) -> str | None:
    """
    Returns selected event id, or None if the user cancelled or an unrecoverable error occurred.
    Persists selectedEventId after a successful choice (used to pre-select the combo next time).
    """
    loading = QDialog()
    loading.setWindowTitle("Sailing Timer")
    loading.setModal(True)
    lay = QVBoxLayout(loading)
    lay.addWidget(QLabel("Loading events..."))
    loading.resize(320, 90)
    loading.show()
    app.processEvents()

    events, err = fetch_events(session, base_url)
    loading.close()

    if err:
        QMessageBox.critical(None, "Events", err)
        return None

    if not events:
        QMessageBox.information(
            None,
            "Events",
            "No events are available. Check back when an event is published.",
        )
        return None

    cfg = load_config()
    saved_raw = cfg.get("selectedEventId")

    dlg = EventSelectorDialog(events, preferred_event_id=str(saved_raw) if saved_raw is not None else None)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    eid = dlg.selected_event_id
    if not eid:
        return None
    sel_err = select_event(session, base_url, eid)
    if sel_err:
        QMessageBox.critical(None, "Events", sel_err)
        return None
    save_config({"selectedEventId": eid})
    log.info("Selected event id=%s", eid)
    return eid
