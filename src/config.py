"""Config dialog: audio mode selection and JSON persistence."""

import json
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)
from PyQt6.QtGui import QFont

AUDIO_MODES = ["Speech + Hoots", "Hoots Only"]
DEFAULT_MODE = AUDIO_MODES[0]


def _config_path() -> str:
    if getattr(sys, "_MEIPASS", None):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


def load_config() -> dict:
    path = _config_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data: dict):
    """Merge into existing config on disk so partial updates do not erase other keys."""
    path = _config_path()
    cfg = load_config()
    cfg.update(data)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class ConfigDialog(QDialog):
    """Startup dialog for selecting audio mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sailing Timer - Setup")
        self.setFixedSize(380, 200)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
            QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #313244;
                color: #cdd6f4;
                selection-background-color: #585b70;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 10px 32px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #74c7ec; }
        """)

        self._audio_mode = DEFAULT_MODE
        self._build_ui()
        self._load_saved()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 24, 30, 24)

        title = QLabel("Sailing Race Timer")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        mode_row = QHBoxLayout()
        mode_label = QLabel("Audio Mode:")
        mode_label.setFont(QFont("Segoe UI", 12))
        self._combo = QComboBox()
        self._combo.addItems(AUDIO_MODES)
        self._combo.setFont(QFont("Segoe UI", 12))
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self._combo, stretch=1)
        layout.addLayout(mode_row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(start_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _load_saved(self):
        cfg = load_config()
        saved_mode = cfg.get("audio_mode", DEFAULT_MODE)
        idx = self._combo.findText(saved_mode)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

    def _on_start(self):
        self._audio_mode = self._combo.currentText()
        save_config({"audio_mode": self._audio_mode})
        self.accept()

    @property
    def audio_mode(self) -> str:
        return self._audio_mode
