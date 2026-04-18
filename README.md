# Sailing Race Countdown Timer

A cross-platform desktop application (Windows / macOS) that displays a synchronized countdown timer for sailing races and plays audio hooter alerts at precise intervals. Built with PyQt6 and pygame to avoid browser audio autoplay restrictions.

## Requirements

- Python 3.10+ (for **Python 3.14 on Windows**, use the dependencies in `requirements.txt` as written: they use **pygame-ce**, which provides wheels where the classic `pygame` package may not.)

## Setup

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Run

```bash
python src/main.py
```

On launch the app loads events from the server (`GET /api/events`) and asks you to pick an event every time (the last choice is pre-selected in the list when still valid), then a config dialog lets you choose the audio mode:

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

1. **Events**: `GET /api/events` on your configured base URL (JSON shape `{ "events": [...] }`). After you choose an event, the app calls `POST /api/events/select` with `{ "eventId": "..." }` so the server can set session cookies. The selected id is stored in `config.json` as `selectedEventId`.
2. **Timer APIs** (scoped to the selected event via `?eventId=...` on each request so cross-origin setups work when cookies are not shared): polls `GET /api/schedule` on a short interval and synchronizes time with `POST /api/time-sync/init` on the same loop.
3. Finds the next race with a future start time and displays a live countdown.
4. Plays hooter sounds and optional speech announcements at designated intervals (3 min, 2 min, 1 min, 30s, 20s, 10s countdown, GO).

Set **`RACE_FLOW_API_BASE`** (optional) to your deployed API origin; it defaults to `https://teamracing.xyz`.

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
  api_constants.py        - Default API base URL (env override)
  events_api.py           - GET /api/events, POST select, shared query helpers
  event_bootstrap.py      - Cold start: load events, event picker
  event_selector_dialog.py - Event picker UI
  config.py               - Startup config dialog + JSON persistence
  timer_window.py         - Main PyQt6 timer window
  api_client.py           - Server API polling and time sync
  audio_manager.py        - Hooter and speech playback
  race_logic.py           - Race selection and knockout series logic
requirements.txt          - Python dependencies
build.py                  - PyInstaller build script
```

## Notes

- The app only reads schedule/time data from the server; it does not submit race results. It does call `POST /api/events/select` so the server can associate the session with an event (same as the main web app).
- If the server is unreachable the app retries every second and shows a red indicator.
- If time sync fails it falls back to local time with a warning indicator.
- If `hooter.mp3` cannot be loaded a generated beep tone is used as a fallback.
