MSFS Hangar Release 138

- Replaced the unstable WebGL globe preview with a safer canvas-based Explore Globe preview.
- Restored verbose frontend/backend console logging for debugging.
- Frontend breadcrumbs are now stored locally and flushed back to the backend on startup.
- Tightened iniBuilds livery matching to iniBuilds packages for the current aircraft family only.
- Sanitizes stored iniBuilds liveries on addon load so stale unrelated entries stop appearing.
