"""
System tray integration for iCloud Auto-Fill daemon.

Creates a message-only window to receive Shell_NotifyIcon callbacks.
Left-click toggles console visibility; right-click shows context menu with Exit.
Pure ctypes — zero external dependencies.
"""
import ctypes
from ctypes import wintypes

# ── ctypes.wintypes polyfills (removed in newer Python) ─────────────────
# LRESULT  = pointer-sized signed int (LONG_PTR on 64-bit)
# UINT_PTR = pointer-sized unsigned int (ULONG_PTR on 64-bit)
# GUID     = 16-byte UUID struct
if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT   = ctypes.c_int64
    UINT_PTR  = ctypes.c_uint64
else:
    LRESULT   = ctypes.c_int32
    UINT_PTR  = ctypes.c_uint32

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

# ── DLL handles ─────────────────────────────────────────────────────────
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32  = ctypes.windll.shell32

# ── Constants ────────────────────────────────────────────────────────────

# Shell_NotifyIcon
NIM_ADD          = 0x00000000
NIM_MODIFY       = 0x00000001
NIM_DELETE       = 0x00000002
NIM_SETVERSION   = 0x00000004
NOTIFYICON_VERSION_4 = 4

NIF_MESSAGE      = 0x00000001
NIF_ICON         = 0x00000002
NIF_TIP          = 0x00000004
NIF_SHOWTIP      = 0x00000080

# Window messages
WM_USER          = 0x0400
WM_NULL          = 0x0000
WM_CREATE        = 0x0001
WM_DESTROY       = 0x0002
WM_COMMAND       = 0x0111
WM_SYSCOMMAND    = 0x0112
WM_LBUTTONUP     = 0x0202
WM_RBUTTONUP     = 0x0205

# Window styles
CS_HREDRAW       = 0x0001
CS_VREDRAW       = 0x0002
WS_POPUP         = 0x80000000

# ShowWindow / System menu
SW_HIDE          = 0
SW_SHOW          = 5
SW_RESTORE       = 9
SC_CLOSE         = 0xF060
SC_MINIMIZE      = 0xF020
MF_BYCOMMAND     = 0x00000000

# Menu
MF_STRING        = 0x00000000
MF_SEPARATOR     = 0x00000800
TPM_RIGHTBUTTON  = 0x0002
TPM_LEFTALIGN    = 0x0000

# System icons (MAKEINTRESOURCE)
IDI_INFORMATION  = 32516

# Message queue
QS_ALLINPUT      = 0x04FF
PM_REMOVE        = 0x0001

# Custom tray callback message
WMAPP_NOTIFYCALLBACK = WM_USER + 1

# Menu item IDs
IDM_EXIT         = 1001
IDM_TOGGLE       = 1002

# ── Structs ──────────────────────────────────────────────────────────────

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd",    wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt",      POINT),
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        wintypes.UINT),
        ("style",         wintypes.UINT),
        ("lpfnWndProc",   ctypes.c_void_p),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     wintypes.HINSTANCE),
        ("hIcon",         wintypes.HICON),
        ("hCursor",       wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName",  wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HICON),
    ]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize",           wintypes.DWORD),
        ("hWnd",             wintypes.HWND),
        ("uID",              wintypes.UINT),
        ("uFlags",           wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon",            wintypes.HICON),
        ("szTip",            wintypes.WCHAR * 128),
        ("dwState",          wintypes.DWORD),
        ("dwStateMask",      wintypes.DWORD),
        ("szInfo",           wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle",      wintypes.WCHAR * 64),
        ("dwInfoFlags",      wintypes.DWORD),
        ("guidItem",         GUID),
        ("hBalloonIcon",     wintypes.HICON),
    ]

# ── Callback type ────────────────────────────────────────────────────────

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

# ── API bindings ─────────────────────────────────────────────────────────

kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

kernel32.GetConsoleWindow.restype = wintypes.HWND

user32.RegisterClassExW.restype = wintypes.ATOM
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]

user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]

user32.DestroyWindow.restype = wintypes.BOOL
user32.DestroyWindow.argtypes = [wintypes.HWND]

user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]

shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]

# LoadIconW — intentionally NO argtypes so integer resource IDs pass through as-is
user32.LoadIconW.restype = wintypes.HICON

user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
]

user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]

user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]

user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
user32.MsgWaitForMultipleObjects.argtypes = [
    wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD,
]

user32.CreatePopupMenu.restype = wintypes.HMENU

user32.AppendMenuW.restype = wintypes.BOOL
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, UINT_PTR, wintypes.LPCWSTR]

user32.DestroyMenu.restype = wintypes.BOOL
user32.DestroyMenu.argtypes = [wintypes.HMENU]

user32.TrackPopupMenu.restype = wintypes.BOOL
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
]

user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]

user32.GetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

user32.PostMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

user32.PostQuitMessage.restype = None
user32.PostQuitMessage.argtypes = [ctypes.c_int]

user32.GetSystemMenu.restype = wintypes.HMENU
user32.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]

user32.EnableMenuItem.restype = wintypes.BOOL
user32.EnableMenuItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]

user32.RemoveMenu.restype = wintypes.BOOL
user32.RemoveMenu.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]

user32.DrawMenuBar.restype = wintypes.BOOL
user32.DrawMenuBar.argtypes = [wintypes.HWND]

# ── Module-level state ───────────────────────────────────────────────────

_hwnd           = None   # message-only window handle
_hIcon          = None   # tray icon handle (stock icon — no cleanup needed)
_proc_ref       = None   # keep-alive for WNDPROC callback
_console_hwnd   = None   # cached console window handle
_console_visible = True  # tracked state
_exit_requested = False  # set by Exit menu item

# ── Internal helpers ─────────────────────────────────────────────────────

def _hide_console():
    global _console_visible
    if _console_hwnd and user32.IsWindow(_console_hwnd):
        user32.ShowWindow(_console_hwnd, SW_HIDE)
    _console_visible = False


def _show_console():
    global _console_visible
    if _console_hwnd and user32.IsWindow(_console_hwnd):
        user32.ShowWindow(_console_hwnd, SW_RESTORE)
        # Re-apply system-menu fix — the console subsystem may have
        # regenerated the menu while the window was hidden.
        hmenu = user32.GetSystemMenu(_console_hwnd, False)
        if hmenu:
            user32.RemoveMenu(hmenu, SC_CLOSE, MF_BYCOMMAND)
            user32.DrawMenuBar(_console_hwnd)
        user32.SetForegroundWindow(_console_hwnd)
    _console_visible = True


def poll_minimize():
    """Call each tick — if console is visible but minimized, hide to tray.

    This is a workaround for console windows not supporting WndProc
    subclassing: we can't intercept SC_MINIMIZE, but we can detect it
    after the fact via IsIconic() and hide immediately."""
    global _console_visible
    if not _console_visible:
        return
    if not _console_hwnd or not user32.IsWindow(_console_hwnd):
        return
    if user32.IsIconic(_console_hwnd):
        _hide_console()


def _toggle_console():
    if _console_visible:
        _hide_console()
    else:
        _show_console()


def _show_context_menu(hwnd):
    """Pop up right-click context menu at the cursor position."""
    menu = user32.CreatePopupMenu()
    if not menu:
        return

    label = "Hide Console" if _console_visible else "Show Console"
    user32.AppendMenuW(menu, MF_STRING, IDM_TOGGLE, label)
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING, IDM_EXIT, "Exit")

    # Must set foreground before TrackPopupMenu for proper dismissal
    user32.SetForegroundWindow(hwnd)

    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))

    user32.TrackPopupMenu(
        menu, TPM_RIGHTBUTTON | TPM_LEFTALIGN, pt.x, pt.y, 0, hwnd, None
    )

    # Required after TrackPopupMenu for proper menu dismissal
    user32.PostMessageW(hwnd, WM_NULL, 0, 0)

    user32.DestroyMenu(menu)


def _add_tray_icon(hwnd):
    """Register the tray icon via Shell_NotifyIcon(NIM_ADD)."""
    global _hIcon

    _hIcon = user32.LoadIconW(0, IDI_INFORMATION)

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
    nid.uCallbackMessage = WMAPP_NOTIFYCALLBACK
    nid.hIcon = _hIcon
    nid.szTip = "iCloud Auto-Fill"
    if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        return False

    # Set version 4 for modern tooltip / NIF_SHOWTIP behaviour
    nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
    shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
    return True


def _remove_tray_icon():
    """Remove the tray icon via Shell_NotifyIcon(NIM_DELETE)."""
    global _hwnd
    if _hwnd is None:
        return
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = _hwnd
    nid.uID = 1
    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

# ── Window procedure ─────────────────────────────────────────────────────

def _window_proc(hwnd, msg, wparam, lparam):
    global _exit_requested

    if msg == WMAPP_NOTIFYCALLBACK:
        # lParam low word = mouse event that triggered the notification
        mouse_event = lparam & 0xFFFF
        if mouse_event == WM_LBUTTONUP:
            _toggle_console()
        elif mouse_event == WM_RBUTTONUP:
            _show_context_menu(hwnd)
        return 0

    elif msg == WM_COMMAND:
        cmd_id = wparam & 0xFFFF
        if cmd_id == IDM_TOGGLE:
            _toggle_console()
            return 0
        elif cmd_id == IDM_EXIT:
            _exit_requested = True
            user32.DestroyWindow(hwnd)
            return 0

    elif msg == WM_DESTROY:
        _remove_tray_icon()
        user32.PostQuitMessage(0)
        return 0

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

# ── Public API ───────────────────────────────────────────────────────────

def init():
    """Initialise the system tray.

    Creates a message-only window, registers the tray icon, and hides the
    console window.  Must be called once before the main loop.

    Returns True on success.
    """
    global _hwnd, _proc_ref, _console_hwnd, _console_visible, _exit_requested

    _exit_requested = False
    _console_visible = True   # about to be hidden below

    # Cache console window handle
    _console_hwnd = kernel32.GetConsoleWindow()

    if _console_hwnd:
        # Gray out the X button — console close cannot be intercepted
        # (it goes through CSRSS → CTRL_CLOSE_EVENT, not WM_CLOSE).
        hmenu = user32.GetSystemMenu(_console_hwnd, False)
        if hmenu:
            user32.RemoveMenu(hmenu, SC_CLOSE, MF_BYCOMMAND)
            user32.DrawMenuBar(_console_hwnd)

    # Module instance handle
    hInstance = kernel32.GetModuleHandleW(None)

    # Register window class
    class_name = "iCloudAutoFill_TrayWindow"

    _proc_ref = WNDPROC(_window_proc)  # stored at module level to prevent GC

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = ctypes.cast(_proc_ref, ctypes.c_void_p)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hInstance
    wc.hIcon = 0
    wc.hCursor = 0
    wc.hbrBackground = 0
    wc.lpszMenuName = None
    wc.lpszClassName = class_name
    wc.hIconSm = 0

    if not user32.RegisterClassExW(ctypes.byref(wc)):
        return False

    # Create message-only window (HWND_MESSAGE = -3)
    HWND_MESSAGE = wintypes.HWND(-3)
    _hwnd = user32.CreateWindowExW(
        0, class_name, "", WS_POPUP,
        0, 0, 0, 0, HWND_MESSAGE, None, hInstance, None,
    )
    if not _hwnd:
        return False

    # Add tray icon
    if not _add_tray_icon(_hwnd):
        user32.DestroyWindow(_hwnd)
        _hwnd = None
        return False

    # Hide console — user can bring it back via tray click
    _hide_console()

    return True


def shutdown():
    """Clean up tray icon and window.  Call after the main loop exits."""
    global _hwnd, _proc_ref, _exit_requested

    # Restore console so it doesn't disappear into the void
    _show_console()

    if _hwnd:
        _remove_tray_icon()
        user32.DestroyWindow(_hwnd)
        _hwnd = None
    _proc_ref = None
    _exit_requested = True


def update_tooltip(text):
    """Update the tray icon tooltip.  *text* is truncated to 127 chars."""
    if _hwnd is None:
        return
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = _hwnd
    nid.uID = 1
    nid.uFlags = NIF_TIP
    nid.szTip = text[:127]
    shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))


def is_exit_requested():
    """True when the user has clicked 'Exit' in the tray context menu."""
    return _exit_requested


def drain_messages():
    """Process all pending Windows messages (non-blocking).

    Call at the top of each main-loop iteration."""
    msg = MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
