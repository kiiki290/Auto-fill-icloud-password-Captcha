"""
Diagnostic: find the iCloud Passwords extension button in Edge.

First clicks the Extensions Hub button (puzzle piece), then scans
for iCloud-related elements in the dropdown menu.

Usage: python uia_ext_finder.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import time
from pywinauto.application import Application

ICLOUD_KEYWORDS = ["icloud", "passwords", "apple", "密码", "mfbcdcn"]


def main():
    print("=" * 60)
    print("iCloud Extension Button Finder")
    print("=" * 60)
    print()

    print("Connecting to Edge via UI Automation...")
    try:
        app = Application(backend="uia").connect(title_re=".*Edge.*")
    except Exception as e:
        print(f"ERROR: Cannot connect to Edge: {e}")
        return

    window = app.window()
    print(f"Connected to: '{window.element_info.name}'")

    # Step 1: Find the Extensions Hub button ("扩展")
    print("\n1. Looking for Extensions Hub button...")
    hub_btn = None
    for btn in window.descendants(control_type="Button"):
        try:
            name = btn.element_info.name or ""
            aid = btn.element_info.automation_id or ""
        except:
            continue
        if "扩展" in name or "extensions" in name.lower():
            hub_btn = btn
            print(f"   Found: Name='{name}' AutomationId='{aid}'")
            break

    if not hub_btn:
        print("   Extensions Hub button NOT found!")
        return

    # Step 2: Click it to open the dropdown
    print("2. Clicking Extensions Hub...")
    try:
        hub_btn.invoke()
    except:
        try:
            hub_btn.click_input()
        except:
            print("   Failed to click!")
            return

    time.sleep(1.0)  # Wait for dropdown animation

    # Step 3: Scan ALL elements for iCloud-related items
    print("3. Scanning for iCloud elements in dropdown...")
    print()

    icloud_found = []
    all_elements = window.descendants()
    for elem in all_elements:
        try:
            ename = elem.element_info.name or ""
            eaid = elem.element_info.automation_id or ""
            eclass = elem.element_info.class_name or ""
            ectrl = elem.element_info.control_type or ""
        except:
            continue

        name_lower = ename.lower()
        aid_lower = eaid.lower()
        if any(kw in name_lower or kw in aid_lower for kw in ICLOUD_KEYWORDS):
            try:
                erect = elem.element_info.rectangle
            except:
                erect = None
            try:
                parent = elem.element_info.parent
                pname = parent.name or ""
                pctrl = parent.control_type or ""
            except:
                pname, pctrl = "", ""
            icloud_found.append({
                'name': ename, 'aid': eaid, 'class': eclass,
                'ctrl': ectrl, 'rect': erect,
                'parent_name': pname, 'parent_ctrl': pctrl,
                'elem': elem,
            })

    if icloud_found:
        print(f"Found {len(icloud_found)} iCloud-related elements:\n")
        for idx, item in enumerate(icloud_found):
            print(f"  [{idx+1}] Name='{item['name']}'")
            print(f"      AutomationId='{item['aid']}'")
            print(f"      ClassName='{item['class']}'")
            print(f"      ControlType='{item['ctrl']}'")
            if item['rect']:
                r = item['rect']
                print(f"      Rect=({r.left}, {r.top}, {r.right}, {r.bottom})")
            print(f"      Parent: Name='{item['parent_name']}' Type='{item['parent_ctrl']}'")
            print()

        print("=" * 60)
        print(f">>> Use the above info for edge_uia.py")
        print("=" * 60)

        # Try clicking the first found element
        print("\n4. Testing click on first match...")
        try:
            first = icloud_found[0]['elem']
            first.invoke()
            print("   Invoke succeeded!")
        except Exception as e:
            print(f"   Invoke failed: {e}")
            try:
                first.click_input()
                print("   click_input succeeded!")
            except Exception as e2:
                print(f"   click_input also failed: {e2}")
    else:
        print("No iCloud-related elements found!")
        print()
        print("The extension might not be in the dropdown.")
        print("Try running this with the extensions hub ALREADY open.")
        print("Or try pinning iCloud Passwords to toolbar:")
        print("  Edge → Extensions → iCloud Passwords → Show in toolbar")


if __name__ == '__main__':
    main()
