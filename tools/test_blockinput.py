"""Minimal BlockInput test — lock keyboard & mouse for 5 seconds."""
import ctypes
from ctypes import wintypes
import time

_BlockInput = ctypes.windll.user32.BlockInput
_BlockInput.restype = wintypes.BOOL
_BlockInput.argtypes = [wintypes.BOOL]

print("Locking keyboard & mouse for 5 seconds...")
ok = _BlockInput(True)
if ok:
    print("  BlockInput(True) succeeded. Try moving mouse / typing.")
else:
    print("  BlockInput(True) FAILED — not running as admin?")

time.sleep(5)

if ok:
    _BlockInput(False)
    print("  Unlocked.")
else:
    print("  No unlock needed (was never locked).")
