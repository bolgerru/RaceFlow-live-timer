"""Sailing Race Countdown Timer -- entry point."""

import sys
import os
import logging

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Ensure src/ is on the path for sibling imports when running from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from api_constants import get_api_base_url
from config import ConfigDialog
from event_bootstrap import run_event_bootstrap
from timer_window import TimerWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sailing Race Timer")

    base_url = get_api_base_url()
    session = requests.Session()

    event_id = run_event_bootstrap(app, session, base_url)
    if event_id is None:
        sys.exit(0)

    dialog = ConfigDialog()
    if dialog.exec() != ConfigDialog.DialogCode.Accepted:
        sys.exit(0)

    audio_mode = dialog.audio_mode

    window = TimerWindow(
        audio_mode=audio_mode,
        api_base_url=base_url,
        event_id=event_id,
        session=session,
    )
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
