"""
Diagnostic: read iCloud Passwords extension button UIA properties.
Run in BOTH states (needs-verification vs verified) and compare.
"""
import sys
import io
if sys.stdout is not None and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ctypes
from ctypes import wintypes
import comtypes.client
from comtypes.gen.UIAutomationClient import (
    IUIAutomation, CUIAutomation8,
    TreeScope_Descendants,
)

user32 = ctypes.windll.user32

# Find Edge HWND
ehwnd = None
def cb(hwnd, _):
    global ehwnd
    cb2 = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cb2, 256)
    if 'Chrome_WidgetWin' in cb2.value:
        l = user32.GetWindowTextLengthW(hwnd)
        if l > 0:
            tb = ctypes.create_unicode_buffer(l + 1)
            user32.GetWindowTextW(hwnd, tb, l + 1)
            if 'Edge' in tb.value:
                ehwnd = hwnd
                return False
    return True
WEP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WEP(cb), 0)

if not ehwnd:
    print("Edge not found!")
    exit()

uia = comtypes.client.CreateObject(CUIAutomation8, interface=IUIAutomation)
elem = uia.ElementFromHandle(ehwnd)
desc = elem.FindAll(TreeScope_Descendants, uia.CreateTrueCondition())

print("=" * 60)
print("iCloud Passwords Extension Button — UIA Property Dump")
print("=" * 60)
print()

found = False
for i in range(desc.Length):
    d = desc.GetElement(i)
    try:
        cn = d.CurrentClassName or ""
        name = d.CurrentName or ""
    except:
        continue

    if cn == "ToolbarActionView" and "icloud" in name.lower():
        found = True
        print(f"Found at index [{i}]")
        print()

        # Dump all standard UIA properties
        props = [
            ("Name", d.CurrentName),
            ("AutomationId", d.CurrentAutomationId),
            ("ClassName", d.CurrentClassName),
            ("ControlType", d.CurrentControlType),
            ("LocalizedControlType", d.CurrentLocalizedControlType),
            ("IsEnabled", d.CurrentIsEnabled),
            ("HasKeyboardFocus", d.CurrentHasKeyboardFocus),
            ("IsKeyboardFocusable", d.CurrentIsKeyboardFocusable),
            ("IsContentElement", d.CurrentIsContentElement),
            ("IsControlElement", d.CurrentIsControlElement),
            ("IsOffscreen", d.CurrentIsOffscreen),
            ("FrameworkId", d.CurrentFrameworkId),
            ("ProviderDescription", d.CurrentProviderDescription),
            ("ProcessId", d.CurrentProcessId),
            ("ItemStatus", d.CurrentItemStatus),
            ("AccessKey", d.CurrentAccessKey),
            ("HelpText", d.CurrentHelpText),
            ("FullDescription", ""),
        ]

        for label, value in props:
            try:
                print(f"  {label:<30} = {value!r}")
            except:
                print(f"  {label:<30} = <error>")

        # Try FullDescription
        try:
            from comtypes.gen.UIAutomationClient import UIA_FullDescriptionPropertyId
            fd = d.GetCurrentPropertyValue(UIA_FullDescriptionPropertyId)
            print(f"  {'FullDescription':<30} = {fd!r}")
        except:
            pass

        # Try LegacyIAccessible properties
        print()
        print("  --- LegacyIAccessible ---")
        try:
            from comtypes.gen.UIAutomationClient import UIA_LegacyIAccessiblePatternId
            legacy = d.GetCurrentPattern(UIA_LegacyIAccessiblePatternId)
            if legacy:
                try:
                    print(f"  {'DefaultAction':<30} = {legacy.CurrentDefaultAction!r}")
                except:
                    pass
                try:
                    print(f"  {'Description':<30} = {legacy.CurrentDescription!r}")
                except:
                    pass
                try:
                    print(f"  {'Help':<30} = {legacy.CurrentHelp!r}")
                except:
                    pass
                try:
                    print(f"  {'Name':<30} = {legacy.CurrentName!r}")
                except:
                    pass
                try:
                    print(f"  {'Role':<30} = {legacy.CurrentRole}")
                except:
                    pass
                try:
                    print(f"  {'State':<30} = {legacy.CurrentState}")
                except:
                    pass
                try:
                    print(f"  {'Value':<30} = {legacy.CurrentValue!r}")
                except:
                    pass
                try:
                    print(f"  {'KeyboardShortcut':<30} = {legacy.CurrentKeyboardShortcut!r}")
                except:
                    pass
        except Exception as e:
            print(f"  LegacyIAccessible error: {e}")

        print()
        print("=" * 60)
        print("Copy this output and save it. Then verify/unverify")
        print("and run again to compare.")
        print("=" * 60)
        break

if not found:
    print("iCloud button not found in UIA tree!")
