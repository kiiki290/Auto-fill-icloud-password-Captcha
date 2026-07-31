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
from datetime import datetime
import os
import time
import traceback

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

from auto_fill_icloud import find_code, type_code, _build_pid_map
from edge_watcher import EdgeLifecycleMonitor
from edge_uia import trigger_icloud_extension, restore_edge_keyboard, switch_edge_to_english
import tray

# Log file next to daemon.py (or next to exe when frozen)
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.log")


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _log(msg, *args):
    if args:
        msg = msg % args
    line = f"{_now()}  {msg}"
    print(line)
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# State machine constants
# ---------------------------------------------------------------------------
STATE_IDLE = 0
STATE_WAIT_EXTENSION = 1   # waiting for Edge to finish loading (renderer child HWND)
STATE_WAIT_CODE = 2        # polling for the verification dialog

# Adaptive wait: poll EnumChildWindows for Chrome_RenderWidgetHostHWND.
# That child appears once Edge has created the tab rendering surface —
# a reliable "browser is done loading" signal.  Safety net at 15 s max.
TICK_IDLE = 1.0              # main-loop sleep when Edge is not running (seconds)
TICK_ACTIVE = 0.5            # main-loop sleep during auto-fill sequence
WAIT_EXTENSION_MIN_TICKS = 1
WAIT_EXTENSION_MAX_TICKS = 30  # 30 × 0.5 s = 15 s
WAIT_CODE_MAX_TICKS = 6       # 6 × 0.5 s = 3 s

QS_ALLINPUT = 0x04FF          # MsgWaitForMultipleObjects wake mask


def _edge_has_renderer(ehwnd):
    """Return True when Edge has created its tab rendering surface.
    Chrome_RenderWidgetHostHWND is a child window that only appears
    after the first browser tab has been fully created."""
    if not ehwnd or not user32.IsWindow(ehwnd):
        return False
    found = False

    def cb(child, _):
        nonlocal found
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child, class_buf, 256)
        if 'Chrome_RenderWidgetHostHWND' in class_buf.value:
            found = True
            return False  # stop enumeration
        return True

    WEP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumChildWindows(ehwnd, WEP(cb), 0)
    return found


def _die(msg):
    """Show a message box AND write to log, then exit."""
    _log("FATAL: " + msg)
    user32.MessageBoxW(None, msg, "iCloud Auto-Fill — Error", 0x10)  # MB_ICONERROR
    sys.exit(1)


def main():
    try:
        _main()
    except Exception as e:
        tb = traceback.format_exc()
        _log(tb)
        user32.MessageBoxW(None, f"{e}\n\nFull traceback written to:\n{_LOG_PATH}",
                           "iCloud Auto-Fill — Crash", 0x10)
        sys.exit(1)


def _main():
    # ── single-instance guard ─────────────────────────────────────
    mutex = kernel32.CreateMutexW(None, False, "iCloudAutoFill_Daemon")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        _die("Another instance is already running.\n\n"
             "Check the system tray for the iCloud Auto-Fill icon,\n"
             "or check daemon.log for details.")

    # Hide console before any output to avoid a visible flash.
    # When built with PyInstaller --hide-console hide-early, the bootloader
    # already handles this and this call is a no-op.  It matters for direct
    # `python daemon.py` runs where no bootloader exists.
    # tray.init() also calls _hide_console(), but doing it here prevents
    # even a one-frame flash before the message loop starts.
    chwnd = kernel32.GetConsoleWindow()
    if chwnd:
        user32.ShowWindow(chwnd, 0)  # SW_HIDE

    _log("=" * 50)
    _log("iCloud Verification Auto-Fill Daemon  (started)")
    _log("=" * 50)
    _log("Waiting for Edge to start…  (Ctrl+C to stop)")

    if not tray.init():
        _die("Failed to initialize system tray.\n\n"
             "See daemon.log for details.")

    monitor = EdgeLifecycleMonitor()
    pid_map = _build_pid_map()     # one-off process snapshot

    state = STATE_IDLE
    tick = 0
    tick_interval = TICK_IDLE
    pending_edge = (None, None)    # (ehwnd, hkl) to restore after auto-fill
    cached_dialog = None           # iCloud dialog HWND, skips EnumWindows on repeat
    last_code = None               # prevent re-filling the same code (spontaneous mode)
    input_locked = False           # track BlockInput state across ticks
    edge_detected_at = 0.0         # timestamp when Edge first detected (for startup time log)

    try:
        while True:
            edge_running = monitor.poll()

            # ── global reset: Edge closed ──────────────────────────
            if monitor.edge_just_stopped():
                _log("Edge closed.")
                tray.update_tooltip("iCloud Auto-Fill — Waiting for Edge…")
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
                    edge_detected_at = time.time()
                    _log("Edge detected. Waiting for renderer…")
                    tray.update_tooltip("iCloud Auto-Fill — Edge detected, initializing…")
                    last_code = None
                    state = STATE_WAIT_EXTENSION
                    tick = 0

                elif edge_running:
                    # ── spontaneous dialog monitoring ──────────────
                    # Edge is already running (not just started) —
                    # watch for verification dialogs that pop up later
                    code, hwnd = find_code(pid_map, cached_dialog)
                    if hwnd:
                        cached_dialog = hwnd
                    if code and code != last_code:
                        _log("Spontaneous dialog — Code: %s", code)
                        tray.update_tooltip("iCloud Auto-Fill — Code detected, auto-filling…")
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
                                time.sleep(0)
                                user32.BlockInput(False)
                        _log("Auto-fill done.")
                        tray.update_tooltip("iCloud Auto-Fill — Auto-fill completed")
                        last_code = code
                    elif not code:
                        last_code = None
                        cached_dialog = None

            # ── WAIT_EXTENSION ──────────────────────────────────────
            elif state == STATE_WAIT_EXTENSION:
                tick += 1
                ehwnd = monitor.last_hwnd
                ready = _edge_has_renderer(ehwnd)

                if ready and tick >= WAIT_EXTENSION_MIN_TICKS:
                    elapsed = time.time() - edge_detected_at
                    _log("Edge ready after %.1fs, triggering Alt+I…", elapsed)
                    tray.update_tooltip("iCloud Auto-Fill — Sending Alt+I…")
                    # pass cached Edge HWND to avoid redundant EnumWindows
                    pending_edge = trigger_icloud_extension(ehwnd)

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
                            time.sleep(0)
                            user32.BlockInput(False)
                            input_locked = False
                        _log("Auto-fill done.")
                        tray.update_tooltip("iCloud Auto-Fill — Auto-fill completed")
                        state = STATE_IDLE
                        tick = 0
                    else:
                        state = STATE_WAIT_CODE
                        tick = 0

                elif tick >= WAIT_EXTENSION_MAX_TICKS:
                    _log("Edge window not responding after %ds, triggering anyway…",
                         WAIT_EXTENSION_MAX_TICKS // 2)
                    tray.update_tooltip("iCloud Auto-Fill — Sending Alt+I…")
                    pending_edge = trigger_icloud_extension(ehwnd)

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
                            time.sleep(0)
                            user32.BlockInput(False)
                            input_locked = False
                        _log("Auto-fill done.")
                        tray.update_tooltip("iCloud Auto-Fill — Auto-fill completed")
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
                        time.sleep(0)
                        user32.BlockInput(False)
                        input_locked = False
                    _log("Auto-fill done.")
                    tray.update_tooltip("iCloud Auto-Fill — Auto-fill completed")
                    state = STATE_IDLE
                    tick = 0
                elif tick >= WAIT_CODE_MAX_TICKS:
                    if input_locked:
                        user32.BlockInput(False)
                        input_locked = False
                    restore_edge_keyboard(*pending_edge)
                    _log("No verification dialog (already verified?)")
                    tray.update_tooltip("iCloud Auto-Fill — Waiting for Edge…")
                    state = STATE_IDLE
                    tick = 0

            # ── dynamic tick: slow when idle, fast when active ──────
            tick_interval = TICK_IDLE if state == STATE_IDLE else TICK_ACTIVE
            tick_ms = int(tick_interval * 1000)

            # Process pending Windows messages (non-blocking drain)
            tray.drain_messages()
            if tray.is_exit_requested():
                break

            # If the user clicked the console's minimize button, hide to tray
            tray.poll_minimize()

            # Wait for next tick OR a Windows message (whichever comes first)
            user32.MsgWaitForMultipleObjects(0, None, False, tick_ms, QS_ALLINPUT)

    except KeyboardInterrupt:
        pass
    finally:
        if input_locked:
            user32.BlockInput(False)
        restore_edge_keyboard(*pending_edge)
        tray.shutdown()
        _log("Daemon stopped.")


if __name__ == '__main__':
    main()
