"""
Daemon: detect Edge startup, trigger iCloud verification, auto-fill.

Monitors for Edge main window to appear. When Edge starts, waits for
extension init, sends Alt+I, then auto-fills the verification code.

Uses a non-blocking state machine — every tick is 0.5s, so Edge
close is detected immediately rather than after a multi-second sleep.

Usage: python daemon.py
"""
import sys
import io
if sys.stdout is not None and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ctypes
import time
from datetime import datetime

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

from auto_fill_icloud import find_code, type_code, _build_pid_map
from edge_watcher import EdgeLifecycleMonitor
from edge_uia import trigger_icloud_extension, restore_edge_keyboard, switch_edge_to_english


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _log(msg, *args):
    if args:
        msg = msg % args
    print(f"{_now()}  {msg}")


# ---------------------------------------------------------------------------
# State machine constants
# ---------------------------------------------------------------------------
STATE_IDLE = 0
STATE_WAIT_EXTENSION = 1   # waiting 2 s for extension to initialise
STATE_WAIT_CODE = 2        # polling for the verification dialog

TICK_IDLE = 1.0              # main-loop sleep when Edge is not running (seconds)
TICK_ACTIVE = 0.5            # main-loop sleep during auto-fill sequence
WAIT_EXTENSION_TICKS = 4   # 4 × 0.5 s = 2 s
WAIT_CODE_MAX_TICKS = 6    # 6 × 0.5 s = 3 s


def main():
    # ── single-instance guard ─────────────────────────────────────
    # With --uac-admin the exe spawns an elevated copy; the unelevated
    # original must exit immediately, otherwise two processes run.
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return  # let the UAC-elevated copy take over

    mutex = kernel32.CreateMutexW(None, False, "iCloudAutoFill_Daemon")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return  # another elevated instance already running

    _log("=" * 50)
    _log("iCloud Verification Auto-Fill Daemon  (started)")
    _log("=" * 50)
    _log("Waiting for Edge to start…  (Ctrl+C to stop)")

    monitor = EdgeLifecycleMonitor()
    pid_map = _build_pid_map()     # one-off process snapshot

    state = STATE_IDLE
    tick = 0
    tick_interval = TICK_IDLE
    pending_edge = (None, None)    # (ehwnd, hkl) to restore after auto-fill
    cached_dialog = None           # iCloud dialog HWND, skips EnumWindows on repeat
    last_code = None               # prevent re-filling the same code (spontaneous mode)
    input_locked = False           # track BlockInput state across ticks

    try:
        while True:
            edge_running = monitor.poll()

            # ── global reset: Edge closed ──────────────────────────
            if monitor.edge_just_stopped():
                _log("Edge closed.")
                if input_locked:
                    user32.BlockInput(False)
                    input_locked = False
                restore_edge_keyboard(*pending_edge)
                cached_dialog = None
                last_code = None
                state = STATE_IDLE
                tick = 0

            # ── IDLE ────────────────────────────────────────────────
            if state == STATE_IDLE:
                if monitor.edge_just_started():
                    _log("Edge detected.  Waiting 2s for extension init…")
                    last_code = None
                    state = STATE_WAIT_EXTENSION
                    tick = 0

                elif edge_running:
                    # ── spontaneous dialog monitoring ──────────────
                    # Edge is already running (not just started) —
                    # watch for verification dialogs that pop up later
                    # (e.g. when the 2-hour code expires)
                    code, hwnd = find_code(pid_map, cached_dialog)
                    if hwnd:
                        cached_dialog = hwnd
                    if code and code != last_code:
                        _log("Spontaneous dialog — Code: %s", code)
                        # lock input for the typing window
                        blocked = user32.BlockInput(True)
                        ehwnd = monitor.last_hwnd
                        try:
                            if ehwnd and user32.IsWindow(ehwnd):
                                prev_hkl = switch_edge_to_english(ehwnd)
                                try:
                                    type_code(code, lock=False)
                                finally:
                                    restore_edge_keyboard(ehwnd, prev_hkl)
                            else:
                                type_code(code, lock=False)
                        finally:
                            if blocked:
                                user32.BlockInput(False)
                        _log("Auto-fill done.")
                        last_code = code
                    elif not code:
                        last_code = None
                        cached_dialog = None

            # ── WAIT_EXTENSION ──────────────────────────────────────
            elif state == STATE_WAIT_EXTENSION:
                tick += 1
                if tick >= WAIT_EXTENSION_TICKS:
                    _log("Triggering Alt+I…")
                    # pass cached Edge HWND to avoid redundant EnumWindows
                    pending_edge = trigger_icloud_extension(monitor.last_hwnd)

                    # lock input immediately after shortcut
                    if not input_locked:
                        input_locked = user32.BlockInput(True)

                    code, hwnd = find_code(pid_map, cached_dialog)
                    if hwnd:
                        cached_dialog = hwnd
                    if code:
                        _log("Code: %s", code)
                        try:
                            type_code(code, lock=False)
                        finally:
                            restore_edge_keyboard(*pending_edge)
                        if input_locked:
                            user32.BlockInput(False)
                            input_locked = False
                        _log("Auto-fill done.")
                        state = STATE_IDLE
                        tick = 0
                    else:
                        state = STATE_WAIT_CODE
                        tick = 0

            # ── WAIT_CODE ───────────────────────────────────────────
            elif state == STATE_WAIT_CODE:
                tick += 1
                code, hwnd = find_code(pid_map, cached_dialog)
                if hwnd:
                    cached_dialog = hwnd
                if code:
                    _log("Code: %s", code)
                    try:
                        type_code(code, lock=False)
                    finally:
                        restore_edge_keyboard(*pending_edge)
                    if input_locked:
                        user32.BlockInput(False)
                        input_locked = False
                    _log("Auto-fill done.")
                    state = STATE_IDLE
                    tick = 0
                elif tick >= WAIT_CODE_MAX_TICKS:
                    if input_locked:
                        user32.BlockInput(False)
                        input_locked = False
                    restore_edge_keyboard(*pending_edge)
                    _log("No verification dialog (already verified?)")
                    state = STATE_IDLE
                    tick = 0

            # ── dynamic tick: slow when idle, fast when active ──────
            tick_interval = TICK_IDLE if state == STATE_IDLE else TICK_ACTIVE
            time.sleep(tick_interval)

    except KeyboardInterrupt:
        if input_locked:
            user32.BlockInput(False)
        restore_edge_keyboard(*pending_edge)
        _log("Daemon stopped.")


if __name__ == '__main__':
    main()
