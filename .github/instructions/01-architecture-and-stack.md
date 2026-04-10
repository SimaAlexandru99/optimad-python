# Domain Knowledge & Stack
- **Domain:** Windows Desktop Automation app (screenshots & system date modification).
- **CRITICAL:** Requires **administrator privileges** to modify the system date (un_admin.bat).
- **Framework:** Python + 	kinter/	tkbootstrap for GUI.
- **Automation:** PyAutoGUI, pywinauto for system interaction. openpyxl for Excel.

## Commands & Venv
- **Setup:** python setup.py (Deletes and recreates .venv if Python version changes).
- **Run Standard:** .venv\Scripts\python.exe main.py
- **Run Admin (Required):** un_admin.bat
"@

 = @"
# UI & Styling Guidelines

## Styling & Components
- **Framework:** 	kinter + 	tkbootstrap.
- Do NOT use web-based frameworks or HTML/CSS logic. Keep it strictly native Python UI.
