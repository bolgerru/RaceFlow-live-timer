"""Modal UI to choose a sailing event before the timer starts."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)


def format_event_label(event: dict) -> str:
    sec = event.get("section", "")
    name = event.get("name", "")
    text = f"[{sec}] {name}"
    sd = event.get("startDate")
    ed = event.get("endDate")
    if sd and ed and sd != ed:
        text += f"  ({sd} – {ed})"
    elif sd:
        text += f"  ({sd})"
    return text


class EventSelectorDialog(QDialog):
    """Pick one event from the API-ordered list (live → upcoming → past as returned)."""

    def __init__(self, events: list[dict], preferred_event_id: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sailing Timer - Select Event")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            """
            QDialog { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
            QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
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
                padding: 10px 28px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #74c7ec; }
            """
        )

        self._events = events
        self._selected_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Choose event")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(
            "Events are listed in server order (typically live, then upcoming, then past)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel("Event:"))
        self._combo = QComboBox()
        self._combo.setFont(QFont("Segoe UI", 12))
        preferred = str(preferred_event_id) if preferred_event_id is not None else None
        for i, ev in enumerate(events):
            self._combo.addItem(format_event_label(ev), ev["id"])
            if preferred is not None and str(ev["id"]) == preferred:
                self._combo.setCurrentIndex(i)
        row.addWidget(self._combo, stretch=1)
        layout.addLayout(row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("Continue")
        ok.clicked.connect(self._on_ok)
        btn_row.addWidget(ok)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_ok(self):
        self._selected_id = str(self._combo.currentData())
        self.accept()

    @property
    def selected_event_id(self) -> str | None:
        return self._selected_id
