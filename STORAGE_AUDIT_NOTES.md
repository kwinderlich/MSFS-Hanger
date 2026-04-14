# MSFS Hangar storage audit baseline

This baseline keeps runtime data outside the zip folder so test builds do not overwrite the live library.

## Windows default paths
- Database: `%LOCALAPPDATA%\MSFSHangar\hangar.db`
- Settings snapshot: `%LOCALAPPDATA%\MSFSHangar\settings.json`
- Logs: `%LOCALAPPDATA%\MSFSHangar\logs`
- Browser profile/cache: `%LOCALAPPDATA%\MSFSHangar\browser_profile`
- Backups: `%LOCALAPPDATA%\MSFSHangar\backups`

## What this build adds
- Launcher startup lines now show the database path and settings path with verified exists/missing, file size, and modified time.
- `/api/application/info` reports verified storage locations and file metadata.
- `/api/application/test-storage` performs a round-trip write/read test and writes a marker file under the test folder.
- `run_hangar_desktop.bat` is included as a friendly alias for the app-window desktop launcher.

## Quick checks on Windows
```powershell
dir "$env:LOCALAPPDATA\MSFSHangar" /a
Get-Item "$env:LOCALAPPDATA\MSFSHangar\hangar.db" -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime
```

## In the app
Open **Settings → Application** to view the active storage paths, run the storage test, create a backup zip, and inspect legacy storage sources.
