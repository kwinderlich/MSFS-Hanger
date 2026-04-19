from __future__ import annotations

from pathlib import Path

def pick_or_create_folder(initial_dir: str = '', title: str = 'Choose Folder') -> str:
    """Best-effort native folder picker with safe fallback.
    Returns empty string if user cancels or GUI is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        selected = filedialog.askdirectory(initialdir=initial_dir or str(Path.home()), title=title or 'Choose Folder')
        try:
            root.destroy()
        except Exception:
            pass
        return selected or ''
    except Exception:
        return ''
