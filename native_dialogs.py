from __future__ import annotations


def pick_or_create_folder(initial_dir: str = '', title: str = 'Choose folder') -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(initialdir=initial_dir or '', title=title)
        try:
            root.destroy()
        except Exception:
            pass
        return selected or ''
    except Exception:
        return ''
