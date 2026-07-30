"""
Edge window lifecycle monitoring. Pure ctypes, no external dependencies.

Detects Edge by visible Chrome_WidgetWin_1 windows (avoids false positives
from background msedge.exe processes that appear before the main window).

Provides:
  EdgeLifecycleMonitor -- edge-triggered start/stop detection for daemon loops.
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32


def _find_edge():
    """Internal: returns (is_running: bool, hwnd: int | None).
    Single EnumWindows pass used by the lifecycle monitor
    to avoid redundant enumeration."""
    found = False
    found_hwnd = None

    def enum_callback(hwnd, _lparam):
        nonlocal found, found_hwnd
        if not user32.IsWindowVisible(hwnd):
            return True
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if 'Chrome_WidgetWin' not in class_buf.value:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if 'Edge' in buf.value:
                found = True
                found_hwnd = hwnd
                return False  # stop enumeration
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return found, found_hwnd


class EdgeLifecycleMonitor:
    """Edge-triggered Edge window lifecycle detector.

    Call poll() each loop iteration. edge_just_started() and
    edge_just_stopped() return True ONLY on the transition cycle.
    """

    def __init__(self):
        self._was_running = False
        self._just_started = False
        self._just_stopped = False
        self._edge_running = None
        self._last_hwnd = None

    def poll(self) -> bool:
        """Check Edge state. Returns True if Edge's main window is visible."""
        self._edge_running, hwnd = _find_edge()
        if self._edge_running and hwnd:
            self._last_hwnd = hwnd
        self._just_started = self._edge_running and not self._was_running
        self._just_stopped = not self._edge_running and self._was_running
        self._was_running = self._edge_running
        return self._edge_running

    def edge_just_started(self) -> bool:
        """True only on the poll() call where Edge transitions off -> on."""
        return self._just_started

    def edge_just_stopped(self) -> bool:
        """True only on the poll() call where Edge transitions on -> off."""
        return self._just_stopped

    @property
    def is_running(self) -> bool:
        """Current Edge running state (from last poll)."""
        return self._edge_running if self._edge_running is not None else False

    @property
    def last_hwnd(self):
        """Cached Edge main-window HWND from the most recent poll where
        Edge was running. None if Edge has never been seen or was closed."""
        return self._last_hwnd
