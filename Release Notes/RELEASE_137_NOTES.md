# MSFS Hangar Release 137

- Added continuous desktop app-window state persistence using the backend window-state API so size/position/maximized state are saved while the app is running.
- Restored structured frontend logging to the backend (`/api/frontend-log`) for window errors, unhandled promise rejections, globe init/update failures, and global map errors.
- Tightened iniBuilds livery scanning so iniBuilds aircraft only use the iniBuilds-specific parser and require aircraft-family token matches before items are accepted.
- Reduced Explore Globe marker size/altitude and increased zoom-in range.
- Added additional globe logging to help diagnose crashes and initialization problems.
