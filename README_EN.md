# iCloud Passwords Auto-Fill

[中文](README.md) | English

Automatically detects and fills the 6-digit verification code for the iCloud Passwords browser extension.

## Background

When using iCloud Passwords with the Edge extension on Windows, a 6-digit verification code is required each time Edge is fully closed and reopened (the extension re-initializes). This tool automates that process in the background.

## How It Works

### 1. Edge Lifecycle Detection
**Window-based detection** (not process-based): enumerates visible windows with the `Chrome_WidgetWin_1` class name, matching "Edge" in the title. Avoids false positives from transient `msedge.exe` subprocesses that appear at Chromium startup.

### 2. Non-Blocking State Machine
`daemon.py` uses a state machine instead of blocking `sleep()`:
```
IDLE  ──Edge start──▶  WAIT_EXTENSION (2s)  ──timeout──▶  WAIT_CODE (3s)
  │▲                                                         │
  │└──────────── Edge close (any state) ──────────────────────┘
  │
  └── Edge running + dialog appears ──▶ spontaneous fill (IME switch + auto-type)
```
- 0.5–1 s per tick (1 s when idle to save CPU, 0.5 s when active for fast response)
- Continuously monitors for the verification dialog while idle — no need to restart Edge when the code expires
- `last_code` deduplication prevents re-filling the same code
- Dialog HWND caching skips `EnumWindows` on cache hit

### 3. Shortcut Trigger (IME Workaround)
- Shortcut: **`Alt+I`** (bind in `edge://extensions/shortcuts`)
- When a CJK IME is active, Windows TSF intercepts keyboard events at the kernel level, preventing shortcuts from reaching the browser
- Solution: send `WM_INPUTLANGCHANGEREQUEST` to **switch Edge's own input language** to English, keep it English through the entire auto-fill sequence, then restore
- This also prevents the IME from interrupting digit typing during auto-fill

### 4. Verification Code Extraction
`EnumWindows` → find `#32770` dialog owned by `iCloudPasswordsExtensionHelper.exe` → `EnumChildWindows` to locate `Static` controls → regex `\d{3}\s+\d{3}` extracts the 6-digit code. Pure Win32 window-text reading — no OCR needed.

### 5. Auto-Typing
`keybd_event` (legacy Win32 API) sends digit virtual-key codes one by one, bypassing UIPI (AppContainer blocks `SendInput`). 15 ms inter-digit delay to match Edge's PIN field auto-advance.

### 6. Keyboard Locking During Input
`BlockInput(True)` disables physical keyboard and mouse input during auto-type to prevent accidental interference. `BlockInput(False)` restores it afterward. Requires administrator privileges; skipped with a tip message if not elevated.

### 7. Performance Optimizations
- **PID snapshot**: `CreateToolhelp32Snapshot` builds a process map in one call, replacing per-window `OpenProcess`
- **Callback reordering**: `find_code()` checks class name and visibility first — 99%+ of windows are filtered at the cheap checks, avoiding unnecessary process handles
- **HWND caching**: both the Edge window and verification dialog HWNDs are cached; cache hits skip `EnumWindows` entirely
- **Dynamic polling interval**: 1 s when idle, 0.5 s when active

### 8. Logging
`print()` to terminal with timestamps. Zero file I/O.

## Requirements

- Python 3.11+
- Windows 11 (with iCloud for Windows + Edge extension installed)
- iCloud Passwords extension shortcut set to `Alt+I`
- Zero external dependencies (pure `ctypes` — no `pywin32`, `pywinauto`, etc.)

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Daemon mode (recommended): Edge startup detection → IME switch → extension trigger → auto-fill
#                            Also handles spontaneous dialogs while Edge is running
python daemon.py

# Manual mode: manually click the extension icon → auto-detect + fill
python auto_fill_icloud.py
```

## Building an Executable

```bash
pip install pyinstaller
pyinstaller --onedir --noconsole --uac-admin --name iCloudAutoFill daemon.py
```

Output is in `dist/iCloudAutoFill/` — run `iCloudAutoFill.exe`.

- `--onedir`: single-process ( `--onefile` produces two processes due to the bootloader extraction step)
- `--noconsole`: no console window, runs silently in the background
- `--uac-admin`: requests administrator privileges on launch (required for `BlockInput` keyboard locking)

## File Structure

```
├── auto_fill_icloud.py    # Core: window detection + code extraction + keybd_event typing + BlockInput
├── edge_uia.py            # Edge window lookup + IME switching + Alt+I shortcut
├── edge_watcher.py        # Edge window lifecycle monitoring (window-based detection)
├── daemon.py              # Daemon entry point (state machine dispatcher)
├── tools/                 # Diagnostic/debug scripts
├── requirements.txt
├── .gitignore
└── LICENSE
```

## Disclaimer

This tool is for personal learning, research, and automation assistance only. By using this tool you agree that:

- This tool is not affiliated with, endorsed by, or officially supported by Apple Inc. or Microsoft Corporation.
- This tool automates interaction with third-party software and may not comply with the terms of service of that software or service. Users are responsible for verifying and accepting the associated risks.
- The keyboard simulation and input-locking features of this tool may be flagged by security software.
- This tool only assists users in entering verification codes for their own accounts. It does not read, store, or export user passwords, Apple ID credentials, or other sensitive information.
- Users should ensure this tool is used only on their own devices and accounts. The author assumes no liability for account restrictions, service disruptions, data loss, or any other direct or indirect damages resulting from the use of this tool.
