"""
Edge extension trigger: send Alt+I keyboard shortcut to open the
iCloud Passwords extension popup.

When Chinese (or other CJK) IME is active, Windows TSF intercepts
keyboard events before they reach the browser.  We work around this
by switching *Edge's* input language (via WM_INPUTLANGCHANGEREQUEST)
rather than our own thread — this also keeps the IME quiet during
the subsequent auto-fill typing.
"""
import sys
import io
if sys.stdout is not None and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── Virtual-key codes ────────────────────────────────────────────────
KEYEVENTF_KEYUP = 0x0002
VK_MENU    = 0x12   # Alt
VK_I       = 0x49   # I
VK_ESCAPE  = 0x1B   # Esc

# ── Keyboard layout ──────────────────────────────────────────────────
KLF_ACTIVATE              = 0x00000001
KLID_EN_US                = "00000409"   # US English
WM_INPUTLANGCHANGEREQUEST = 0x0050

_keybd_event = ctypes.windll.user32.keybd_event
_keybd_event.restype = None
_keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_ulonglong]


# ── helpers ──────────────────────────────────────────────────────────

def _find_edge_hwnd():
    """Return the HWND of the first visible Edge main window, or None."""
    result = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if 'Chrome_WidgetWin' in class_buf.value:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                title = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title, length + 1)
                if 'Edge' in title.value:
                    result.append(hwnd)
                    return False
        return True

    WEP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WEP(cb), 0)
    return result[0] if result else None


def switch_edge_to_english(ehwnd):
    """Switch *Edge's* input language to US English.

    Returns Edge's previous HKL so it can be restored later."""
    edge_tid = user32.GetWindowThreadProcessId(ehwnd, None)
    prev = user32.GetKeyboardLayout(edge_tid)
    hkl_en = user32.LoadKeyboardLayoutW(KLID_EN_US, KLF_ACTIVATE)
    user32.SendMessageW(ehwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl_en)
    return prev


def restore_edge_keyboard(ehwnd, hkl):
    """Restore Edge's input language to a previously saved HKL."""
    if ehwnd and hkl:
        if user32.IsWindow(ehwnd):
            user32.SendMessageW(ehwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        else:
            print("    [edge_uia] Edge window gone — keyboard restore skipped")


def _press_shortcut():
    """Send Alt+I via keybd_event."""
    _keybd_event(VK_MENU, 0, 0, 0)
    _keybd_event(VK_I, 0, 0, 0)
    time.sleep(0.02)
    _keybd_event(VK_I, 0, KEYEVENTF_KEYUP, 0)
    _keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)


# ── public API ───────────────────────────────────────────────────────

def trigger_icloud_extension(ehwnd=None):
    """Bring Edge to foreground, switch Edge's input language to English,
    send Alt+I.  Returns (ehwnd, prev_hkl) so the caller can restore
    Edge's keyboard layout after auto-fill completes.

    If *ehwnd* is given it is used directly; otherwise Edge's main window
    is located via EnumWindows (slower)."""

    # 1.  Cancel any in-progress IME composition
    _keybd_event(VK_ESCAPE, 0, 0, 0)
    _keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)

    # 2.  Find Edge HWND & bring to foreground (use cached if provided)
    if ehwnd is None:
        ehwnd = _find_edge_hwnd()

    if ehwnd:
        our_tid = kernel32.GetCurrentThreadId()
        edge_tid = user32.GetWindowThreadProcessId(ehwnd, None)
        if edge_tid != our_tid:
            user32.AttachThreadInput(our_tid, edge_tid, True)
        user32.SetForegroundWindow(ehwnd)
        time.sleep(0.1)
        if edge_tid != our_tid:
            user32.AttachThreadInput(our_tid, edge_tid, False)
        print(f"    [edge_uia] Edge HWND={ehwnd:#x}, foreground OK")
    else:
        print(f"    [edge_uia] WARNING: No Edge window found!")
        return None, None

    # 3.  Switch Edge's input language to English
    prev_hkl = switch_edge_to_english(ehwnd)

    # 4.  Send the shortcut
    _press_shortcut()
    print("    [edge_uia] Sent Alt+I")

    return ehwnd, prev_hkl
