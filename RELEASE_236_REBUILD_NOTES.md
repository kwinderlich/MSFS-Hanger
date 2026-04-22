# MSFS Hangar Release 236 Rebuild

This package is a reconstructed baseline of the current public `kwinderlich/MSFS-Hanger` repository snapshot.

## What is included
- The current Hangar Python application files from the public repo snapshot.
- The current `frontend/index.html` from the public repo snapshot.
- Compatibility launcher/support files added so the package is self-contained:
  - `bootstrap.py`
  - `bootstrap_cfg.py`
  - `native_dialogs.py`
  - `flight_tracker.py` (baseline stub)
  - `virtual_pilot.py` (baseline config stub)
  - `run_hangar_desktop.bat`
  - `run_hangar_lan.bat`
  - `run_hangar_qt_desktop.bat`

## Intent
This is the clean starting point before the Pomax vendoring work in Release 237.

## Honest note
The public repo snapshot references some support modules that were not present in the fetched root file list, so compatibility shims were added to make the rebuild self-contained rather than shipping a broken baseline.
