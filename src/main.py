"""Sailing Race Countdown Timer -- entry point."""

import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Ensure src/ is on the path for sibling imports when running from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from config import ConfigDialog
from timer_window import TimerWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sailing Race Timer")

    dialog = ConfigDialog()
    if dialog.exec() != ConfigDialog.DialogCode.Accepted:
        sys.exit(0)

    audio_mode = dialog.audio_mode

    window = TimerWindow(audio_mode=audio_mode)
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
