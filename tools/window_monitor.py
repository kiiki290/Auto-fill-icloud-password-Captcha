"""
Simple iCloud Window Monitor - poll for windows instead of message loop.
Run this, then click the iCloud Passwords extension icon in Edge.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stdout.flush()

import ctypes
from ctypes import wintypes
import time
import subprocess

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_process_name(pid):
    """Get process name from PID."""
    try:
        hProcess = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if hProcess:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_uint32(260)
            kernel32.QueryFullProcessImageNameW(hProcess, 0, buf, ctypes.byref(size))
            path = buf.value
            name = path.split('\\')[-1] if '\\' in path else path
            kernel32.CloseHandle(hProcess)
            return name
    except:
        pass
    return "<error>"

def get_all_windows_for_pid(target_pid):
    """Get all windows (including children) for a given PID."""
    windows = []

    def enum_callback(hwnd, lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == target_pid:
            # Get info
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value

            is_visible = user32.IsWindowVisible(hwnd)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            windows.append({
                'hwnd': hwnd,
                'title': title,
                'class': class_name,
                'visible': is_visible,
                'size': f"{w}x{h}",
                'pos': (rect.left, rect.top),
            })

            # Also check child windows
            def enum_children(child_hwnd, lparam2):
                child_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(child_hwnd, ctypes.byref(child_pid))
                clen = user32.GetWindowTextLengthW(child_hwnd)
                ctitle = ""
                if clen > 0:
                    cbuf = ctypes.create_unicode_buffer(clen + 1)
                    user32.GetWindowTextW(child_hwnd, cbuf, clen + 1)
                    ctitle = cbuf.value
                cc_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(child_hwnd, cc_buf, 256)
                windows.append({
                    'hwnd': child_hwnd,
                    'title': ctitle,
                    'class': cc_buf.value,
                    'visible': bool(user32.IsWindowVisible(child_hwnd)),
                    'size': "",
                    'pos': (0, 0),
                    'child': True,
                })
                return True

            ChildEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumChildWindows(hwnd, ChildEnumProc(enum_children), 0)

        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return windows

def find_icloud_pids():
    """Find all iCloud process PIDs."""
    pids = {}
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq iCloud*', '/FO', 'CSV', '/NH'],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            parts = line.replace('"', '').split(',')
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    pids[pid] = parts[0]
                except:
                    pass
    return pids

def main():
    print("=" * 60)
    print("iCloud Window Monitor - Polling Mode")
    print("Will scan for iCloud windows every 1 second")
    print("Click the iCloud Passwords extension icon NOW!")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Initial state: find all iCloud PIDs and their windows
    initial_pids = find_icloud_pids()
    print(f"\nInitial iCloud processes: {initial_pids}")

    known_windows = set()  # track HWNDs we've already reported

    # Also check non-iCloud named windows that might show the code
    # (the popup might come from a different process)
    try:
        while True:
            # Refresh PID list
            current_pids = find_icloud_pids()

            # Check for new PIDs
            new_pids = set(current_pids.keys()) - set(initial_pids.keys())
            if new_pids:
                for pid in new_pids:
                    print(f"\n[NEW PROCESS] {current_pids[pid]} (PID: {pid})")

            # Check windows for all iCloud PIDs
            all_pids = set(current_pids.keys())
            for pid in all_pids:
                windows = get_all_windows_for_pid(pid)
                for w in windows:
                    hwnd_int = w['hwnd']
                    if hwnd_int not in known_windows and w['visible']:
                        known_windows.add(hwnd_int)
                        child_tag = " [CHILD]" if w.get('child') else ""
                        print(f"\n[NEW WINDOW{child_tag}] {current_pids.get(pid, '?')} (PID: {pid})")
                        print(f"  HWND={hwnd_int:#010x}")
                        print(f"  Title='{w['title']}'")
                        print(f"  Class='{w['class']}'")
                        print(f"  Size={w['size']} Pos={w['pos']}")

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopped.")

if __name__ == '__main__':
    main()
