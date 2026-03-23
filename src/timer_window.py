"""Main timer window: countdown display, race info, status indicators."""

import logging

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsOpacityEffect,
)

from api_client import ApiClient
from audio_manager import AudioManager
from race_logic import find_current_race, find_next_race, get_race_display_info
from config import save_config

log = logging.getLogger(__name__)

SERVER_URL = "https://teamracing.xyz"


def _bold_font(family: str, size: int, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    f = QFont(family, size)
    f.setWeight(weight)
    return f


class _PulsingLabel(QLabel):
    """A QLabel with animated opacity for pulsing effects."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(1200)
        self._anim.setStartValue(0.3)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

    def start_pulse(self):
        self._anim.start()

    def stop_pulse(self):
        self._anim.stop()
        self._effect.setOpacity(1.0)


class _PillLabel(QLabel):
    """Small colored pill badge."""

    def __init__(self, text: str, text_color: str, bg_color: str, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            f"border-radius: 8px; padding: 3px 12px; font-weight: bold;"
        )


class TimerWindow(QMainWindow):
    """Full-screen countdown timer window."""

    def __init__(self, audio_mode: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sailing Race Timer")
        self.setStyleSheet("background-color: black;")

        self._is_fullscreen = False
        self._schedule: list[dict] = []
        self._current_race_info: dict | None = None
        self._last_race_number: int | None = None
        self._in_countdown = False

        # Core components
        self._audio = AudioManager()
        self._audio.mode = audio_mode

        self._api = ApiClient(SERVER_URL)
        self._api.schedule_updated.connect(self._on_schedule_updated)
        self._api.connection_status.connect(self._on_connection_status)
        self._api.sync_status.connect(self._on_sync_status)

        self._build_ui()
        self._update_fonts()

        # 100ms tick timer
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._tick)

        self._api.start()
        self._tick_timer.start()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar (connection dot left, sync label right)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(20, 14, 20, 0)

        self._conn_dot = QLabel("\u25CF")
        self._conn_dot.setStyleSheet("color: #ef4444; font-size: 18px;")
        self._conn_dot.setFixedWidth(30)
        top_bar.addWidget(self._conn_dot, alignment=Qt.AlignmentFlag.AlignLeft)

        top_bar.addStretch()

        self._sync_label = _PulsingLabel("Syncing Time")
        self._sync_label.setStyleSheet("color: #60a5fa; font-size: 13px;")
        self._sync_label.start_pulse()
        top_bar.addWidget(self._sync_label, alignment=Qt.AlignmentFlag.AlignRight)

        root.addLayout(top_bar)
        root.addStretch(1)

        # Center content -- no setAlignment on the layout itself; each widget
        # already aligns its own text.  The stretches above/below handle vertical
        # centering.  Setting alignment on the layout constrains it to minimum
        # size and breaks re-centering when the big countdown font changes.
        center = QVBoxLayout()
        center.setSpacing(6)

        self._stage_label = QLabel("")
        self._stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stage_label.setStyleSheet("color: #a855f7;")
        self._stage_label.hide()
        center.addWidget(self._stage_label)

        self._race_label = QLabel("Connecting...")
        self._race_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._race_label.setStyleSheet("color: white;")
        center.addWidget(self._race_label)

        # Tags row
        self._tags_widget = QWidget()
        self._tags_layout = QHBoxLayout(self._tags_widget)
        self._tags_layout.setContentsMargins(0, 0, 0, 0)
        self._tags_layout.setSpacing(8)
        self._tags_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self._tags_widget)

        self._countdown_label = QLabel("...")
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet("color: #60a5fa;")
        center.addWidget(self._countdown_label)

        self._subtitle_label = QLabel("Syncing Time")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setStyleSheet("color: #facc15;")
        center.addWidget(self._subtitle_label)

        # Teams row
        self._teams_widget = QWidget()
        teams_layout = QHBoxLayout(self._teams_widget)
        teams_layout.setContentsMargins(0, 20, 0, 0)
        teams_layout.setSpacing(0)

        self._team_a_col = QVBoxLayout()
        self._team_a_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_a_name = QLabel("")
        self._team_a_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_a_name.setStyleSheet("color: white;")
        self._team_a_boat = QLabel("")
        self._team_a_boat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_a_boat.setStyleSheet("color: #9ca3af;")
        self._team_a_col.addWidget(self._team_a_name)
        self._team_a_col.addWidget(self._team_a_boat)

        self._vs_label = QLabel("VS")
        self._vs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vs_label.setStyleSheet("color: #6b7280; font-weight: bold;")
        self._vs_label.setFixedWidth(100)

        self._team_b_col = QVBoxLayout()
        self._team_b_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_b_name = QLabel("")
        self._team_b_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_b_name.setStyleSheet("color: white;")
        self._team_b_boat = QLabel("")
        self._team_b_boat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_b_boat.setStyleSheet("color: #9ca3af;")
        self._team_b_col.addWidget(self._team_b_name)
        self._team_b_col.addWidget(self._team_b_boat)

        teams_layout.addStretch()
        teams_layout.addLayout(self._team_a_col)
        teams_layout.addWidget(self._vs_label)
        teams_layout.addLayout(self._team_b_col)
        teams_layout.addStretch()

        self._teams_widget.hide()
        center.addWidget(self._teams_widget)

        root.addLayout(center)
        root.addStretch(1)

        # Bottom bar (mute left, audio mode right)
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(20, 0, 20, 14)

        self._mute_btn = QPushButton("\U0001F50A")
        self._mute_btn.setFixedSize(44, 44)
        self._mute_btn.setStyleSheet(
            "QPushButton { background: transparent; color: white; border: none; font-size: 22px; }"
            "QPushButton:hover { color: #facc15; }"
        )
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom_bar.addWidget(self._mute_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        bottom_bar.addStretch()

        self._mode_label = QLabel(self._audio.mode)
        self._mode_label.setStyleSheet(
            "color: #9ca3af; font-size: 13px; padding: 4px 8px;"
        )
        self._mode_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mode_label.mousePressEvent = self._toggle_mode
        bottom_bar.addWidget(self._mode_label, alignment=Qt.AlignmentFlag.AlignRight)

        root.addLayout(bottom_bar)

    # ------------------------------------------------------------------ font scaling
    def _update_fonts(self):
        h = self.height() if self.height() > 0 else 900
        self._countdown_font_large = max(72, int(h * 0.35))
        self._countdown_font_small = max(36, int(h * 0.12))
        self._race_size = max(14, int(h * 0.028))
        self._stage_size = max(12, int(h * 0.022))
        self._subtitle_size = max(12, int(h * 0.022))
        self._team_name_size = max(13, int(h * 0.028))
        self._team_name_size_large = max(28, int(h * 0.065))
        self._team_boat_size = max(10, int(h * 0.018))
        self._team_boat_size_large = max(16, int(h * 0.035))
        self._vs_size = max(12, int(h * 0.022))
        self._vs_size_large = max(20, int(h * 0.04))
        tag_size = max(9, int(h * 0.015))

        self._countdown_label.setFont(_bold_font("Segoe UI", self._countdown_font_large))
        self._race_label.setFont(_bold_font("Segoe UI", self._race_size))
        self._stage_label.setFont(_bold_font("Segoe UI", self._stage_size))
        self._subtitle_label.setFont(QFont("Segoe UI", self._subtitle_size))
        self._set_team_fonts(large=False)
        self._tag_font_size = tag_size

    def _set_team_fonts(self, large: bool = False):
        if large:
            self._team_a_name.setFont(_bold_font("Segoe UI", self._team_name_size_large))
            self._team_b_name.setFont(_bold_font("Segoe UI", self._team_name_size_large))
            self._team_a_boat.setFont(QFont("Segoe UI", self._team_boat_size_large))
            self._team_b_boat.setFont(QFont("Segoe UI", self._team_boat_size_large))
            self._vs_label.setFont(_bold_font("Segoe UI", self._vs_size_large))
        else:
            self._team_a_name.setFont(_bold_font("Segoe UI", self._team_name_size))
            self._team_b_name.setFont(_bold_font("Segoe UI", self._team_name_size))
            self._team_a_boat.setFont(QFont("Segoe UI", self._team_boat_size))
            self._team_b_boat.setFont(QFont("Segoe UI", self._team_boat_size))
            self._vs_label.setFont(_bold_font("Segoe UI", self._vs_size))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_fonts()

    # ------------------------------------------------------------------ key events
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F11:
            if self._is_fullscreen:
                self.showMaximized()
            else:
                self.showFullScreen()
            self._is_fullscreen = not self._is_fullscreen
        elif event.key() == Qt.Key.Key_Escape and self._is_fullscreen:
            self.showMaximized()
            self._is_fullscreen = False
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ slots
    def _on_schedule_updated(self, schedule: list[dict]):
        self._schedule = schedule
        # Immediate UI update driven by tick

    def _on_connection_status(self, connected: bool):
        if connected:
            self._conn_dot.setStyleSheet("color: #22c55e; font-size: 18px;")
            self._conn_dot.setToolTip("Connected")
        else:
            self._conn_dot.setStyleSheet("color: #ef4444; font-size: 18px;")
            self._conn_dot.setToolTip("Disconnected")

    def _on_sync_status(self, status: str):
        if status == "syncing":
            self._sync_label.setText("Syncing Time")
            self._sync_label.setStyleSheet("color: #60a5fa; font-size: 13px;")
            self._sync_label.show()
            self._sync_label.start_pulse()
        elif status == "synced":
            self._sync_label.stop_pulse()
            self._sync_label.hide()
        elif status == "fallback":
            self._sync_label.stop_pulse()
            self._sync_label.setText("Local Time")
            self._sync_label.setStyleSheet("color: #f59e0b; font-size: 13px;")
            self._sync_label.show()

    def _toggle_mute(self):
        self._audio.toggle_mute()
        self._mute_btn.setText("\U0001F507" if self._audio.muted else "\U0001F50A")

    def _toggle_mode(self, _event=None):
        if self._audio.mode == "Speech + Hoots":
            self._audio.mode = "Hoots Only"
        else:
            self._audio.mode = "Speech + Hoots"
        self._mode_label.setText(self._audio.mode)
        save_config({"audio_mode": self._audio.mode})

    # ------------------------------------------------------------------ tick
    def _tick(self):
        now_ms = self._api.synchronized_now_ms()

        if not self._api.is_synced and not self._schedule:
            self._show_syncing()
            return

        current = find_current_race(self._schedule, now_ms)
        if current:
            self._show_countdown(current, now_ms)
            return

        next_race = find_next_race(self._schedule, now_ms)
        if next_race:
            self._show_coming_up(next_race)
            return

        self._show_no_races()

    # ------------------------------------------------------------------ display states
    def _show_syncing(self):
        self._in_countdown = False
        self._stage_label.hide()
        self._race_label.setText("")
        self._countdown_label.setFont(_bold_font("Segoe UI", self._countdown_font_small))
        self._countdown_label.setText("...")
        self._countdown_label.setStyleSheet("color: #60a5fa;")
        self._subtitle_label.setText("Syncing Time")
        self._subtitle_label.show()
        self._teams_widget.hide()
        self._clear_tags()

    def _show_countdown(self, race: dict, now_ms: float):
        info = get_race_display_info(race)
        race_num = info["race_number"]
        remaining_ms = info["start_time_ms"] - now_ms
        remaining_s = remaining_ms / 1000.0

        # Detect race change OR entry into countdown from another state
        # (e.g. "Coming Up" → countdown when the server sets a startTime).
        # This ensures prepare_for_new_race runs for rolling-start detection
        # even when the race number didn't change.
        if self._last_race_number != race_num or not self._in_countdown:
            self._last_race_number = race_num
            self._in_countdown = True
            self._audio.prepare_for_new_race(remaining_s)

        # Update countdown text
        if remaining_s <= 0:
            display = "GO!"
            self._countdown_label.setStyleSheet("color: #22c55e;")
        else:
            total_sec = int(remaining_s)
            if total_sec >= 60:
                minutes = total_sec // 60
                seconds = total_sec % 60
                display = f"{minutes}:{seconds:02d}"
            else:
                display = str(total_sec)
            self._countdown_label.setStyleSheet("color: #facc15;")

        self._countdown_label.setFont(_bold_font("Segoe UI", self._countdown_font_large))
        self._countdown_label.setText(display)
        self._subtitle_label.setText("Starts in")
        self._subtitle_label.show()

        self._race_label.setText(f"Race #{race_num}")
        self._set_team_fonts(large=False)
        self._update_race_info(info)
        self._audio.check_thresholds(remaining_s)

    def _show_coming_up(self, race: dict):
        info = get_race_display_info(race)
        race_num = info["race_number"]

        self._in_countdown = False
        if self._last_race_number != race_num:
            self._last_race_number = race_num

        self._countdown_label.setFont(_bold_font("Segoe UI", self._countdown_font_small))
        self._countdown_label.setText("Coming Up")
        self._countdown_label.setStyleSheet("color: #facc15;")
        self._subtitle_label.setText("Next Race")
        self._subtitle_label.show()
        self._race_label.setText(f"Next Race #{race_num}")
        self._set_team_fonts(large=True)
        self._update_race_info(info)

    def _show_no_races(self):
        self._in_countdown = False
        self._stage_label.hide()
        self._race_label.setText("")
        self._countdown_label.setFont(_bold_font("Segoe UI", self._countdown_font_small))
        self._countdown_label.setText("No Races")
        self._countdown_label.setStyleSheet("color: #6b7280;")
        self._subtitle_label.setText("No races scheduled or in progress")
        self._subtitle_label.show()
        self._teams_widget.hide()
        self._clear_tags()
        self._last_race_number = None

    def _update_race_info(self, info: dict):
        # Stage
        if info.get("stage_label"):
            self._stage_label.setText(info["stage_label"])
            self._stage_label.show()
        else:
            self._stage_label.hide()

        # Tags
        self._clear_tags()
        if info.get("league_pill"):
            pill = info["league_pill"]
            tag = _PillLabel(pill["text"], pill["text_color"], pill["bg_color"])
            tag.setFont(QFont("Segoe UI", self._tag_font_size, QFont.Weight.Bold))
            self._tags_layout.addWidget(tag)

        if info.get("round") is not None:
            tag = _PillLabel(f"Round {info['round']}", "#000000", "#22d3ee")
            tag.setFont(QFont("Segoe UI", self._tag_font_size, QFont.Weight.Bold))
            self._tags_layout.addWidget(tag)

        # Teams
        team_a = info.get("team_a", "")
        team_b = info.get("team_b", "")
        if team_a or team_b:
            self._team_a_name.setText(team_a)
            self._team_b_name.setText(team_b)
            boat_a = info.get("boat_a", "")
            boat_b = info.get("boat_b", "")
            self._team_a_boat.setText(f"({boat_a})" if boat_a else "")
            self._team_b_boat.setText(f"({boat_b})" if boat_b else "")
            self._teams_widget.show()
        else:
            self._teams_widget.hide()

    def _clear_tags(self):
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ------------------------------------------------------------------ cleanup
    def closeEvent(self, event):
        self._tick_timer.stop()
        self._api.stop()
        self._audio.shutdown()
        super().closeEvent(event)
