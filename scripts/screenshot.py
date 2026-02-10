#!/usr/bin/env python
"""
Screenshot utility for Claude Code context.
Usage:
    python scripts/screenshot.py              # Full screen
    python scripts/screenshot.py --active     # Active window only (Windows)
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Output directory
SCRATCHPAD = Path(r"C:\Users\fbrun\AppData\Local\Temp\claude\C--Users-fbrun-Documents-GitHub-AgenticContextBuilder\4285e6e4-fc0b-4c08-b8b0-bba015958e1a\scratchpad")
SCRATCHPAD.mkdir(parents=True, exist_ok=True)

def capture_full_screen():
    """Capture the entire screen."""
    import pyautogui
    screenshot = pyautogui.screenshot()
    return screenshot

def capture_active_window():
    """Capture only the active window (Windows only)."""
    try:
        import pyautogui
        import ctypes
        from ctypes import wintypes

        # Get the foreground window handle
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()

        # Get window rectangle
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        # Capture that region
        x, y = rect.left, rect.top
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        return screenshot
    except Exception as e:
        print(f"Active window capture failed ({e}), falling back to full screen")
        return capture_full_screen()

def main():
    active_only = "--active" in sys.argv or "-a" in sys.argv

    if active_only:
        print("Capturing active window...")
        img = capture_active_window()
    else:
        print("Capturing full screen...")
        img = capture_full_screen()

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = SCRATCHPAD / filename

    # Save
    img.save(str(filepath))
    print(f"Screenshot saved: {filepath}")
    return str(filepath)

if __name__ == "__main__":
    main()
