"""
UIA Diagnostic: Find the iCloud extension input field in Edge.
Run this, click the iCloud Passwords extension icon, wait for popup.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import comtypes.client
from comtypes.gen.UIAutomationClient import (
    IUIAutomation, CUIAutomation8,
    TreeScope_Children, TreeScope_Descendants, TreeScope_Subtree,
    UIA_ValueValuePropertyId, UIA_NamePropertyId,
    UIA_ControlTypePropertyId, UIA_ClassNamePropertyId,
    UIA_IsKeyboardFocusablePropertyId, UIA_AutomationIdPropertyId,
    UIA_HasKeyboardFocusPropertyId, UIA_BoundingRectanglePropertyId,
    UIA_ValuePatternId, UIA_LegacyIAccessiblePatternId,
)
import time

uia = comtypes.client.CreateObject(CUIAutomation8, interface=IUIAutomation)
root = uia.GetRootElement()
condition = uia.CreateTrueCondition()

print("=== Scanning all top-level windows for Edge and Edit fields ===\n")
print("(Make sure the iCloud extension popup is open in Edge)\n")

top_windows = root.FindAll(TreeScope_Children, condition)
edge_found = 0

for i in range(top_windows.Length):
    elem = top_windows.GetElement(i)
    try:
        name = elem.CurrentName or ""
        class_name = elem.CurrentClassName or ""
        pid = elem.CurrentProcessId

        # Look for Edge
        is_edge = False
        if 'edge' in name.lower():
            is_edge = True
        elif 'Chrome_WidgetWin' in class_name:
            # Could be Edge or Chrome - check process name
            is_edge = True  # We'll scan all Chromium windows

        if not is_edge:
            continue

        edge_found += 1
        print(f"[Edge Window {edge_found}] Name='{name}' Class='{class_name}' PID={pid}")
        print(f"  Searching descendants for Edit fields...")

        # Search ALL descendants for Edit controls
        descendants = elem.FindAll(TreeScope_Descendants, condition)
        edit_count = 0
        for j in range(descendants.Length):
            d = descendants.GetElement(j)
            try:
                ct = d.CurrentControlType
                # ControlType.Edit = 50004, ControlType.Document = 50030
                if ct not in [50004, 50020, 50030]:
                    continue

                dn = d.CurrentName or ""
                dc = d.CurrentClassName or ""
                da = d.CurrentAutomationId or ""
                dv = ""

                # Try to get value
                try:
                    dv = str(d.GetCurrentPropertyValue(UIA_ValueValuePropertyId) or "")
                except:
                    pass

                # Focus state
                is_focused = False
                is_focusable = False
                try:
                    is_focused = bool(d.GetCurrentPropertyValue(UIA_HasKeyboardFocusPropertyId))
                except:
                    pass
                try:
                    is_focusable = bool(d.GetCurrentPropertyValue(UIA_IsKeyboardFocusablePropertyId))
                except:
                    pass

                # Bounding rect
                rect = None
                try:
                    r = d.GetCurrentPropertyValue(UIA_BoundingRectanglePropertyId)
                    rect = [float(c) for c in r]
                except:
                    pass

                edit_count += 1
                print(f"\n  [{edit_count}] CtrlType={ct} Name='{dn}'")
                print(f"      Class='{dc}' AutoId='{da}'")
                print(f"      Value='{dv}'")
                print(f"      Focused={is_focused} Focusable={is_focusable}")
                if rect:
                    print(f"      Rect={rect}")

            except:
                pass

        print(f"\n  Total Edit/Document/Text fields: {edit_count}")
        print()
    except Exception as e:
        print(f"  Error: {e}")

if edge_found == 0:
    print("No Edge/Chrome windows found!")
    print("\nAll top-level windows:")
    for i in range(min(top_windows.Length, 30)):
        elem = top_windows.GetElement(i)
        try:
            print(f"  [{i}] Name='{elem.CurrentName}' Class='{elem.CurrentClassName}' PID={elem.CurrentProcessId}")
        except:
            pass
