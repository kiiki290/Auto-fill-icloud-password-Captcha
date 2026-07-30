# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automatically detects and fills the 6-digit verification code for the iCloud Passwords browser extension on Edge (Windows). Uses pure `ctypes` Win32 API calls — zero external Python dependencies required at runtime.

## Commands

```bash
# Daemon mode (recommended): background state machine, monitors Edge lifecycle
python daemon.py

# Manual mode: poll for dialog after manually clicking the extension icon
python auto_fill_icloud.py

# Diagnostic tools (all under tools/)
python tools/window_monitor.py       # Monitor iCloud process windows in real-time
python tools/uia_diagnostic.py       # Scan Edge UIA tree for Edit fields (needs comtypes)
python tools/uia_ext_finder.py       # Find iCloud extension button via UIA (needs pywinauto)
python tools/check_button_state.py   # Dump UIA properties of extension button (needs comtypes)
python tools/read_leveldb.py         # Read Edge extension LevelDB for debug state
python tools/test_blockinput.py      # Test BlockInput admin-permission
```

**Build executable:**
```bash
pip install pyinstaller
pyinstaller --onedir --uac-admin --hide-console hide-early --name iCloudAutoFill daemon.py
```
- `console=True` (implicit) — keeps console subsystem so `GetConsoleWindow()` returns a valid HWND
- `--hide-console hide-early` — bootloader hides console before Python starts, zero flash
- `--uac-admin` — admin privileges for `BlockInput` keyboard locking

## Architecture

### Core modules (pure `ctypes`, zero external deps)

| Module | Role |
|---|---|
| `daemon.py` | Entry point. Non-blocking state machine: `IDLE → WAIT_EXTENSION → WAIT_CODE → IDLE`. Single-instance mutex guard. Monitors Edge lifecycle and triggers auto-fill on startup or spontaneous dialog. |
| `edge_watcher.py` | Edge lifecycle detection via `EnumWindows` on `Chrome_WidgetWin_1` windows (window-based, not process-based — avoids false positives from transient subprocesses). `EdgeLifecycleMonitor` provides edge-triggered `edge_just_started()` / `edge_just_stopped()`. |
| `edge_uia.py` | Edge window foregrounding, IME language switching, and `Alt+I` shortcut sending. Switches Edge's input language to US English via `WM_INPUTLANGCHANGEREQUEST` to bypass CJK IME TSF interception. Returns `(ehwnd, prev_hkl)` for caller to restore. |
| `auto_fill_icloud.py` | Core auto-fill logic: `find_code()` (dialog enumeration + code extraction), `type_code()` / `type_digit()` (keybd_event typing), `_build_pid_map()` (process snapshot). Also usable standalone. |
| `tray.py` | System tray integration: message-only window, `Shell_NotifyIcon`, console hide/show toggle via `IsIconic()` polling, right-click context menu (Hide/Show Console, Exit). X button disabled via `GetSystemMenu`+`RemoveMenu(SC_CLOSE)`. Pure ctypes. Public API: `init()`, `shutdown()`, `update_tooltip()`, `drain_messages()`, `is_exit_requested()`, `poll_minimize()`. |

### Data flow

```
EdgeLifecycleMonitor.poll()
    │
    ▼
daemon.py state machine
    │
    ├── trigger_icloud_extension()     # edge_uia.py — Alt+I shortcut
    │   ├── switch_edge_to_english()   # WM_INPUTLANGCHANGEREQUEST → US English
    │   └── _press_shortcut()          # keybd_event Alt+I
    │
    ├── find_code(pid_map, cache)      # auto_fill_icloud.py — EnumWindows → #32770 dialog
    │   ├── _read_code_from_dialog()   # EnumChildWindows → Static controls → regex \d{3}\s+\d{3}
    │   └── get_process_name()         # PID → exe via snapshot or per-process fallback
    │
    └── type_code(code)                # keybd_event per digit (bypasses UIPI)
        └── BlockInput(True/False)     # Lock physical keyboard during typing

── tray message path ──
tray icon click → WMAPP_NOTIFYCALLBACK → window proc
    ├── left click: toggle console (ShowWindow SW_HIDE/SW_SHOW)
    └── right click: context menu → Exit → sets _exit_requested
daemon.py checks is_exit_requested() → breaks main loop → shutdown()
```

### Key design decisions

- **`keybd_event` over `SendInput`**: The iCloud helper runs at AppContainer integrity level, which blocks `SendInput`. The legacy `keybd_event` API bypasses UIPI.
- **`WM_INPUTLANGCHANGEREQUEST` over thread `ActivateKeyboardLayout`**: Switches Edge's own input language rather than our thread's, which also prevents the IME from popping up during digit typing.
- **PID snapshot over per-window `OpenProcess`**: `CreateToolhelp32Snapshot` builds the process table once; avoids repeated `OpenProcess` + `QueryFullProcessImageNameW` per window.
- **HWND caching**: Both Edge main window HWND and verification dialog HWND are cached across ticks — cache hits skip `EnumWindows` entirely.
- **Message-aware polling over `time.sleep()`**: Replaces blocking `time.sleep()` with `MsgWaitForMultipleObjects` + `PeekMessageW` drain so the main loop can respond to tray icon clicks between state-machine ticks without a separate thread.
- **Console close/minimize workaround**: Windows CSRSS unconditionally terminates console processes on close (X) — `WM_CLOSE` subclassing is ignored. Workaround: disable X via `RemoveMenu(SC_CLOSE)`, poll `IsIconic()` each tick to detect minimize and hide to tray.

### Prerequisites (not in code)

- iCloud for Windows installed
- iCloud Passwords Edge extension installed
- Extension keyboard shortcut bound to `Alt+I` in `edge://extensions/shortcuts`
- Admin privileges for `BlockInput` (keyboard locking during auto-type)

### Diagnostic tools (require extra deps: `comtypes`, `pywinauto`)

The `tools/` directory contains UIA-based diagnostic scripts used during development to inspect Edge's accessibility tree and iCloud extension state. These depend on `comtypes` and/or `pywinauto` and are not needed for normal operation — the core modules deliberately avoid these dependencies.
