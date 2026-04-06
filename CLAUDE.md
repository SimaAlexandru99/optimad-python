# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Optimad is a Windows-only desktop automation app (Python + tkinter/ttkbootstrap) that captures screenshots at configurable intervals and temporarily modifies the Windows system date to simulate activity across multiple days. Requires **administrator privileges** to run.

## Running the Application

```bash
# Setup venv (first time or after Python version changes)
python setup.py

# Activate venv
.venv\Scripts\activate

# Run (standard)
.venv\Scripts\python.exe main.py

# Run with admin rights (required for date modification)
run_admin.bat
```

> Note: The `.venv` must be created with the system Python. If you see errors like "did not find executable at C:\PythonXXX\python.exe", the venv was built with a now-missing Python version — delete `.venv` and re-run `python setup.py`.

## Architecture

The app is structured around three layers:

**`main.py` — `ScreenshotApp` class**

- Owns the entire tkinter/ttkbootstrap UI (tabs: Settings, About)
- Orchestrates the main process loop in a background thread (`process_thread`)
- Handles scheduling logic: checks every 10s if daily run is due
- Persists state to `schedule_config.json` and `themeconfig.json`
- Calls into `SystemUtils` for date changes and `ScreenshotManager` for captures
- Admin check happens at startup: prompts to re-launch via `ShellExecuteW("runas")` if not elevated

**`utils/helpers.py` — three utility classes**

- `Logger`: writes timestamped entries to `logs/jurnal_erori.txt`; optionally mirrors to a tkinter Text widget
- `SystemUtils`: wraps Windows system date manipulation (tries 4 methods in order: `date` cmd, `cmd /c date`, PowerShell `Set-Date`, WMIC) and window focusing via `pywinauto`
- `ScreenshotManager`: captures via `pyautogui`, organizes files into `YYYY-MM-DD/HH-MM-SS.png` directories, verifies saved files with Pillow, checks for 500 MB free disk space

**`utils/constants.py`**

- Single source of truth for all magic values: timeouts, limits, app names, themes, font specs, error message templates, file paths

## Key Behaviors to Know

- **Date restoration**: The process loop modifies the system date per screenshot, then restores it in a `finally` block. A secondary restoration attempt runs if the first fails.
- **Threading**: The screenshot process runs on `process_thread`. Stop is signalled via `stop_event` (threading.Event), checked between screenshots.
- **Scheduling**: Daily mode polls every 10 seconds in the main thread, comparing `last_run` (stored in `schedule_config.json`) against today's date.
- **Interval calculation**: `interval_minutes = (hours * 60) / screenshots` — minimum enforced is 1 minute.
- **Config files**: `themeconfig.json` stores `{mode, theme}`; `schedule_config.json` stores all form field values plus `last_run` and `is_scheduled_daily`.

## Supported Focused Apps

`desktop`, `zoom`, `teams`, `chrome` — defined in `constants.SUPPORTED_APPS`. Window focusing uses `pywinauto` UIA backend with 3 retry attempts.
