# Sailing Race Countdown Timer

A cross-platform desktop application (Windows / macOS) that displays a synchronized countdown timer for sailing races and plays audio hooter alerts at precise intervals. Built with PyQt6 and pygame to avoid browser audio autoplay restrictions.

## Requirements

- Python 3.10+

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python src/main.py
```

On launch a config dialog lets you choose the audio mode:

- **Speech + Hoots** (default) -- hooter sounds plus spoken announcements
- **Hoots Only** -- hooter sounds only, no speech

The main timer window then opens maximized. Press **F11** to toggle true fullscreen.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| F11 | Toggle fullscreen |
| Esc | Exit fullscreen |

## Build standalone executable

```bash
python build.py
```

The packaged app is output to `dist/SailingTimer/`.

## How it works

1. Polls `https://teamracing.xyz/api/schedule` every second for the race schedule.
2. Synchronizes the local clock with the server via `POST /api/time-sync/init` (re-syncs every 30 seconds).
3. Finds the next race with a future start time and displays a live countdown.
4. Plays hooter sounds and optional speech announcements at designated intervals (3 min, 2 min, 1 min, 30s, 20s, 10s countdown, GO).

## Status indicators

- **Top-left dot**: green = connected to server, red = disconnected (auto-retries)
- **Top-right**: "Syncing Time" shown during time synchronization
- **Bottom-left**: click the speaker icon to mute/unmute
- **Bottom-right**: click the audio mode label to toggle between Speech+Hoots and Hoots Only

## Project structure

```
public/audio/hooter.mp3   - Hooter sound file
src/
  main.py                 - Entry point
  config.py               - Startup config dialog
  timer_window.py         - Main PyQt6 timer window
  api_client.py           - Server API polling and time sync
  audio_manager.py        - Hooter and speech playback
  race_logic.py           - Race selection and knockout series logic
requirements.txt          - Python dependencies
build.py                  - PyInstaller build script
```

## Notes

- The app is display-only and never writes data back to the server.
- If the server is unreachable the app retries every second and shows a red indicator.
- If time sync fails it falls back to local time with a warning indicator.
- If `hooter.mp3` cannot be loaded a generated beep tone is used as a fallback.
