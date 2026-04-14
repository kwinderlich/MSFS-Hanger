# MSFS Hangar Release 129 baseline rebuild

This package was rebuilt from the current `kwinderlich/MSFS-Hanger` GitHub `main` branch and then patched only for baseline/stability and storage auditing.

## Included baseline tweaks
- Added `run_hangar_desktop.bat` as an alias that calls the existing app-window desktop launcher.
- Launcher startup output now prints verified Settings and Library DB details including exists/missing, file size, and modified time.
- App logging now records the same verified Settings and DB details in the log file.
- Startup snapshot JSON now includes verified settings/database file metadata.
- Legacy `/api/app/info` now includes file existence and file-info details, in addition to the richer `/api/application/info` endpoint already present.
- Added `STORAGE_AUDIT_NOTES.md` with quick Windows checks and the intended runtime paths.

## Runtime data design
This baseline keeps runtime data outside the zip folder. On Windows the default live data folder is:

`%LOCALAPPDATA%\MSFSHangar`

That prevents new test builds from overwriting the live library database or settings snapshot.
