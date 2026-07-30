"""
Auto-fill iCloud Passwords verification code.
Detect dialog -> extract code -> type via keybd_event (bypasses UIPI).
SendInput is blocked because iCloud helper runs at higher integrity level (AppContainer).
"""
import sys
import io
if sys.stdout is not None and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ctypes
from ctypes import wintypes
import time
import re

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── Process snapshot (PID → name cache) ─────────────────────────────
TH32CS_SNAPPROCESS = 0x00000002


def _build_pid_map():
    """One-shot snapshot of all running processes → {pid: exe_name}.
    Much cheaper than per-window OpenProcess + QueryFullProcessImageNameW."""
    pid_map = {}
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return pid_map  # empty, fallback to per-process lookup

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_uint32),
            ("cntUsage", ctypes.c_uint32),
            ("th32ProcessID", ctypes.c_uint32),
            ("th32DefaultHeapID", ctypes.c_ulonglong),
            ("th32ModuleID", ctypes.c_uint32),
            ("cntThreads", ctypes.c_uint32),
            ("th32ParentProcessID", ctypes.c_uint32),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_uint32),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            pid_map[pe.th32ProcessID] = pe.szExeFile
            if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                break

    kernel32.CloseHandle(snap)
    return pid_map


def get_process_name(pid, pid_map=None):
    """Return executable name for *pid*.  Uses *pid_map* if provided;
    falls back to per-process OpenProcess when PID is not in cache
    (e.g. process started after the snapshot was taken)."""
    if pid_map is not None:
        name = pid_map.get(pid)
        if name:
            return name
        # PID not in snapshot — was started after we built the map,
        # fall through to per-process lookup below
    try:
        hProcess = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if hProcess:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_uint32(260)
            kernel32.QueryFullProcessImageNameW(hProcess, 0, buf, ctypes.byref(size))
            kernel32.CloseHandle(hProcess)
            return buf.value.split('\\')[-1] if '\\' in buf.value else buf.value
    except:
        pass
    return ""


def _read_code_from_dialog(hwnd):
    """Read 6-digit code from child Static controls of a #32770 dialog.
    Returns the code string or None."""

    result = {}

    def enum_children(child_hwnd, lparam2):
        cclass_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child_hwnd, cclass_buf, 256)
        if cclass_buf.value == 'Static':
            clen = user32.GetWindowTextLengthW(child_hwnd)
            if clen > 0:
                cbuf = ctypes.create_unicode_buffer(clen + 1)
                user32.GetWindowTextW(child_hwnd, cbuf, clen + 1)
                text = cbuf.value
                match = re.match(r'^(\d{3})\s+(\d{3})$', text)
                if match:
                    result['code'] = match.group(1) + match.group(2)
                    return False
        return True

    ChildEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumChildWindows(hwnd, ChildEnumProc(enum_children), 0)
    return result.get('code')


def find_code(pid_map=None, cached_hwnd=None):
    """Find the iCloud verification dialog and extract the 6-digit code.

    If *cached_hwnd* is given and the window is still alive, skips the
    full EnumWindows and reads the child Static controls directly.

    *pid_map* is an optional {pid: exe_name} dict from _build_pid_map().
    When absent each matching window triggers a per-process OpenProcess.

    Returns (code: str | None, dialog_hwnd: int | None)."""

    # ── fast path: cached HWND still valid ───────────────────────
    if cached_hwnd and user32.IsWindow(cached_hwnd):
        code = _read_code_from_dialog(cached_hwnd)
        if code:
            return code, cached_hwnd
        # dialog may have been replaced; fall through to full scan

    # ── slow path: enumerate top-level windows ───────────────────
    result = {}

    def enum_callback(hwnd, lparam):
        # cheap checks FIRST (class name, visibility) — avoid
        # expensive OpenProcess for windows that can't be the dialog
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if class_buf.value != '#32770':
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        # expensive: process-name check last (only ~1 window survives
        # the cheap filters above)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if get_process_name(pid.value, pid_map) != 'iCloudPasswordsExtensionHelper.exe':
            return True

        code = _read_code_from_dialog(hwnd)
        if code:
            result['code'] = code
            result['hwnd'] = hwnd
            return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return result.get('code'), result.get('hwnd')


# Virtual key codes for digits 0-9
VK_DIGITS = {
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}
KEYEVENTF_KEYUP = 0x0002

# keybd_event bypasses UIPI (SendInput is blocked by AppContainer integrity level)
_keybd_event = ctypes.windll.user32.keybd_event
_keybd_event.restype = None
_keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_ulonglong]

# BlockInput — blocks physical keyboard/mouse during auto-type
# Requires admin (UAC elevation); returns 0 if not elevated.
_BlockInput = ctypes.windll.user32.BlockInput
_BlockInput.restype = wintypes.BOOL
_BlockInput.argtypes = [wintypes.BOOL]


def type_digit(digit: str):
    """Send ONE digit via keybd_event (legacy API, bypasses UIPI)."""
    vk = VK_DIGITS[digit]
    _keybd_event(vk, 0, 0, 0)                       # Key down
    _keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)          # Key up


def type_code(code: str, lock: bool = True):
    """Type the 6-digit code. Blocks physical keyboard during input
    unless *lock* is False (caller handles locking)."""
    if lock:
        blocked = _BlockInput(True)
    else:
        blocked = False
    try:
        for i, digit in enumerate(code):
            type_digit(digit)
            time.sleep(0.015)  # Wait for Edge to auto-advance to next PIN field
            print(f"    [{i+1}/6] typed '{digit}'")
    finally:
        if blocked:
            _BlockInput(False)

    if lock and not blocked:
        print("    (tip: run as admin to lock keyboard during typing)")


def main():
    print("=" * 60)
    print("iCloud Verification Code Auto-Fill")
    print("=" * 60)
    print()
    print("Waiting for verification dialog...")
    print("(Click the iCloud Passwords extension icon in Edge)")
    print("Press Ctrl+C to stop.")
    print()

    pid_map = _build_pid_map()
    last_code = None
    cached_hwnd = None

    try:
        while True:
            code, hwnd = find_code(pid_map, cached_hwnd)

            if hwnd:
                cached_hwnd = hwnd

            if code and code != last_code:
                print(f"\n>>> Code detected: {code}")
                print(f"    Typing digit by digit...")
                type_code(code)
                print(f"    Done!")
                last_code = code

            elif not code:
                if last_code is not None:
                    print(f"\n>>> Dialog closed.")
                last_code = None
                cached_hwnd = None

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nStopped.")

if __name__ == '__main__':
    main()
