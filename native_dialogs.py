from __future__ import annotations

from pathlib import Path


def pick_or_create_folder(initial_dir: str = '', title: str = 'Choose Folder') -> str:
    start = str(Path(initial_dir).expanduser()) if initial_dir else str(Path.home())
    # Prefer tkinter when available because it is standard-library and works without extra dependencies.
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        chosen = filedialog.askdirectory(initialdir=start, title=title, mustexist=False)
        try:
            root.destroy()
        except Exception:
            pass
        return str(chosen or '')
    except Exception:
        pass

    # Quiet fallback: return the starting folder so callers can still proceed in headless/test environments.
    return start
