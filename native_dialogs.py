from __future__ import annotations

from pathlib import Path


def pick_or_create_folder(initial_dir: str = '', title: str = 'Choose MSFS Hangar App Folder') -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass

        selected = filedialog.askdirectory(
            initialdir=initial_dir or str(Path.home()),
            title=title,
            mustexist=True,
            parent=root,
        )
        if not selected:
            root.destroy()
            return ''

        while True:
            action = messagebox.askyesnocancel(
                'Use or Create Folder',
                'Use the selected folder as-is?\n\n'
                'Yes = Use this folder\n'
                'No = Create a new folder inside this folder and use that\n'
                'Cancel = Cancel selection',
                parent=root,
            )
            if action is None:
                root.destroy()
                return ''
            if action is True:
                root.destroy()
                return str(Path(selected).expanduser())

            folder_name = simpledialog.askstring(
                'Create New Folder',
                'Enter the name of the new folder to create inside the selected folder:',
                parent=root,
            )
            if folder_name is None:
                continue
            folder_name = folder_name.strip().strip('\\/ ')
            if not folder_name:
                messagebox.showerror('Create New Folder', 'Please enter a folder name.', parent=root)
                continue
            target = Path(selected) / folder_name
            try:
                target.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                messagebox.showerror('Create New Folder', f'The folder already exists:\n{target}', parent=root)
                continue
            except Exception as exc:
                messagebox.showerror('Create New Folder', f'Could not create folder:\n{target}\n\n{exc}', parent=root)
                continue
            root.destroy()
            return str(target.expanduser())
    except Exception:
        return ''
