"""Audio manager: hooter playback via pygame, speech via native OS TTS, threshold crossing logic."""

import array
import logging
import math
import os
import platform
import subprocess
import sys

import pygame
from PyQt6.QtCore import QTimer

log = logging.getLogger(__name__)

ANNOUNCEMENTS: dict[int, tuple[int, str | None, int]] = {
    180: (3, "Three minutes", 0),
    120: (2, "Two minutes", 0),
    60:  (1, "One minute", 0),
    30:  (0, "Thirty seconds", 3),
    20:  (0, "Twenty seconds", 2),
    10:  (0, "Ten", 1),
    9:   (0, "Nine", 0),
    8:   (0, "Eight", 0),
    7:   (0, "Seven", 0),
    6:   (0, "Six", 0),
    5:   (0, "Five", 0),
    4:   (0, "Four", 0),
    3:   (0, "Three", 0),
    2:   (0, "Two", 0),
    1:   (0, "One", 0),
    0:   (1, None, 1),
}

THRESHOLDS_ASCENDING = sorted(ANNOUNCEMENTS.keys())

FULL_HOOT_SPACING_MS = 1500
SHORT_HOOT_DURATION_MS = 280
SHORT_HOOT_SPACING_MS = 500


def _resource_path(relative: str) -> str:
    """Resolve path for both dev and PyInstaller bundled mode."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, relative)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _generate_fallback_beep() -> pygame.mixer.Sound:
    """Generate a 440 Hz sine wave beep as a fallback when hooter.mp3 is missing."""
    sample_rate = 44100
    n_samples = int(sample_rate * 1.0)
    samples = array.array("h")
    for i in range(n_samples):
        val = int(32767 * 0.6 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
        samples.append(val)
        samples.append(val)
    return pygame.mixer.Sound(buffer=samples)


class _NativeSpeech:
    """
    Platform-native TTS.  Avoids pyttsx3 COM threading issues entirely.
      Windows: persistent PowerShell process with SAPI.SpVoice COM object.
      macOS:   built-in `say` command (one subprocess per utterance).
    """

    def __init__(self):
        self._system = platform.system()
        self._ps_proc: subprocess.Popen | None = None
        self._say_proc: subprocess.Popen | None = None
        self._available = False
        self._init()

    def _init(self):
        if self._system == "Windows":
            self._init_windows()
        elif self._system == "Darwin":
            self._available = True
            log.info("macOS speech ready (using 'say')")

    def _init_windows(self):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            self._ps_proc = subprocess.Popen(
                [
                    "powershell", "-NoProfile", "-NoLogo",
                    "-ExecutionPolicy", "Bypass", "-Command", "-",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=si,
            )
            self._ps_proc.stdin.write(
                b"$voice = New-Object -ComObject SAPI.SpVoice\r\n"
                b"$voice.Rate = 2\r\n"
            )
            self._ps_proc.stdin.flush()
            self._available = True
            log.info("Windows SAPI speech initialized via PowerShell")
        except Exception as exc:
            log.warning("Windows SAPI init failed: %s", exc)
            self._available = False

    @property
    def ready(self) -> bool:
        if self._system == "Windows":
            return self._available and self._ps_proc is not None and self._ps_proc.poll() is None
        return self._available

    def speak(self, text: str):
        if not self.ready:
            return
        if self._system == "Windows":
            self._speak_windows(text)
        elif self._system == "Darwin":
            self._speak_macos(text)

    def _speak_windows(self, text: str):
        try:
            safe = text.replace("'", "''")
            # Flag 3 = SVSFlagsAsync (1) | SVSFPurgeBeforeSpeak (2)
            # Cancels any in-progress speech, then speaks asynchronously
            cmd = f"[void]$voice.Speak('{safe}', 3)\r\n"
            self._ps_proc.stdin.write(cmd.encode())
            self._ps_proc.stdin.flush()
        except Exception as exc:
            log.debug("Windows speech write failed: %s", exc)

    def _speak_macos(self, text: str):
        self.cancel()
        try:
            self._say_proc = subprocess.Popen(
                ["say", "-r", "200", "--", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            log.debug("macOS say failed: %s", exc)

    def cancel(self):
        if self._system == "Windows" and self._ps_proc and self._ps_proc.poll() is None:
            try:
                # Purge + async with empty string = cancel current speech
                self._ps_proc.stdin.write(b"[void]$voice.Speak('', 3)\r\n")
                self._ps_proc.stdin.flush()
            except Exception:
                pass
        elif self._system == "Darwin" and self._say_proc:
            try:
                self._say_proc.kill()
                self._say_proc.wait()
            except Exception:
                pass
            self._say_proc = None

    def shutdown(self):
        self.cancel()
        if self._ps_proc:
            try:
                self._ps_proc.stdin.write(b"exit\r\n")
                self._ps_proc.stdin.flush()
                self._ps_proc.wait(timeout=3)
            except Exception:
                try:
                    self._ps_proc.kill()
                except Exception:
                    pass


class AudioManager:
    """Manages hooter sounds and speech announcements."""

    def __init__(self):
        self._muted = False
        self._mode = "Speech + Hoots"
        self._hooter_sound: pygame.mixer.Sound | None = None
        self._speech: _NativeSpeech | None = None
        self._played_set: set[int] = set()
        self._last_seconds: float | None = None
        self._channels: list[pygame.mixer.Channel] = []

        self._init_pygame()
        self._init_speech()

    def _init_pygame(self):
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            pygame.mixer.set_num_channels(8)
            self._channels = [pygame.mixer.Channel(i) for i in range(8)]
            log.info("pygame mixer initialized")
        except Exception as exc:
            log.error("pygame mixer init failed: %s", exc)
            return

        hooter_path = _resource_path(os.path.join("public", "audio", "hooter.mp3"))
        log.info("Loading hooter from: %s", hooter_path)
        try:
            self._hooter_sound = pygame.mixer.Sound(hooter_path)
            log.info("Hooter sound loaded (length=%.1fs)", self._hooter_sound.get_length())
        except Exception as exc:
            log.warning("Could not load hooter.mp3 (%s), generating fallback beep", exc)
            try:
                self._hooter_sound = _generate_fallback_beep()
            except Exception as exc2:
                log.error("Fallback beep generation failed: %s", exc2)

    def _init_speech(self):
        try:
            self._speech = _NativeSpeech()
            if self._speech.ready:
                log.info("Speech engine ready")
            else:
                log.warning("Speech engine not available -- speech disabled")
        except Exception as exc:
            log.error("Speech init failed: %s", exc)
            self._speech = None

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str):
        self._mode = value

    @property
    def muted(self) -> bool:
        return self._muted

    def toggle_mute(self):
        self._muted = not self._muted

    def set_muted(self, muted: bool):
        self._muted = muted

    def reset_thresholds(self):
        """Clear the played set (call when switching to a new race)."""
        self._played_set.clear()
        self._last_seconds = None

    def prepare_for_new_race(self, remaining_s: float | None):
        """
        Reset thresholds for a new race, with rolling-start detection.
        If the previous race's GO hoot (0s) was played and the new race starts
        at ~180s, the GO already served as the 3-minute signal -- skip the 180s
        announcement to avoid a duplicate.
        """
        go_just_played = 0 in self._played_set
        self._played_set.clear()
        self._last_seconds = None

        if (
            go_just_played
            and remaining_s is not None
            and 178.0 <= remaining_s <= 182.0
        ):
            self._played_set.add(180)
            log.info("Rolling start detected: skipping 180s announcement")

    def _find_free_channel(self) -> pygame.mixer.Channel | None:
        for ch in self._channels:
            if not ch.get_busy():
                return ch
        return self._channels[0] if self._channels else None

    def _play_hoot_on_channel(self):
        if self._hooter_sound is None or self._muted:
            return
        ch = self._find_free_channel()
        if ch:
            ch.play(self._hooter_sound)

    def _play_short_hoot_on_channel(self):
        if self._hooter_sound is None or self._muted:
            return
        ch = self._find_free_channel()
        if ch:
            ch.play(self._hooter_sound, maxtime=SHORT_HOOT_DURATION_MS)

    def play_full_hoots(self, count: int):
        if count <= 0:
            return
        self._play_hoot_on_channel()
        for i in range(1, count):
            QTimer.singleShot(FULL_HOOT_SPACING_MS * i, self._play_hoot_on_channel)

    def play_short_hoots(self, count: int):
        if count <= 0:
            return
        self._play_short_hoot_on_channel()
        for i in range(1, count):
            QTimer.singleShot(SHORT_HOOT_SPACING_MS * i, self._play_short_hoot_on_channel)

    def speak(self, text: str):
        if self._muted:
            return
        if self._speech is None or not self._speech.ready:
            log.debug("Speech unavailable, skipping: %s", text)
            return
        log.info("Speaking: %s", text)
        self._speech.speak(text)

    def cancel_speech(self):
        if self._speech:
            self._speech.cancel()

    def play_announcement(self, seconds: int):
        if self._muted:
            return

        entry = ANNOUNCEMENTS.get(seconds)
        if entry is None:
            return

        log.info("Playing announcement for %ds threshold", seconds)
        hoot_count, speech_text, short_hoot_count = entry

        if self._mode == "Hoots Only":
            self._play_hoots_only(seconds, hoot_count, short_hoot_count)
        else:
            self._play_speech_and_hoots(seconds, hoot_count, speech_text)

    def _play_speech_and_hoots(self, seconds: int, hoot_count: int, speech_text: str | None):
        if seconds == 0:
            self.play_full_hoots(1)
            return

        if hoot_count > 0 and speech_text:
            self.play_full_hoots(hoot_count)
            speech_delay = (hoot_count - 1) * FULL_HOOT_SPACING_MS + 800
            QTimer.singleShot(speech_delay, lambda: self.speak(speech_text))
        elif hoot_count > 0:
            self.play_full_hoots(hoot_count)
        elif speech_text:
            if seconds <= 10:
                self.cancel_speech()
            self.speak(speech_text)

    def _play_hoots_only(self, seconds: int, hoot_count: int, short_hoot_count: int):
        if seconds == 0:
            self.play_full_hoots(1)
        elif hoot_count > 0:
            self.play_full_hoots(hoot_count)
        elif short_hoot_count > 0:
            self.play_short_hoots(short_hoot_count)

    def check_thresholds(self, seconds_remaining: float):
        if seconds_remaining is None:
            return

        if self._last_seconds is not None and seconds_remaining > self._last_seconds + 5:
            self.reset_thresholds()

        self._last_seconds = seconds_remaining

        for threshold in THRESHOLDS_ASCENDING:
            if threshold in self._played_set:
                continue
            # Fire at the START of the displayed second.  The display uses
            # int() truncation, so "N" first appears when remaining_s drops
            # below N+1.  This applies uniformly to all thresholds including
            # the GO hoot (threshold 0), so the GO fires the instant "0"
            # appears on the countdown display.
            crossed = seconds_remaining < threshold + 1.0
            if crossed:
                self._played_set.add(threshold)
                self.play_announcement(threshold)
                break

    def shutdown(self):
        if self._speech:
            self._speech.shutdown()
        try:
            pygame.mixer.quit()
        except Exception:
            pass
