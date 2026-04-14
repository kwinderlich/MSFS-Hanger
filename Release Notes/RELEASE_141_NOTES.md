# MSFS Hangar Release 141

## Fixes in this build
- Restored browser search fallback behavior for Research, Aircraft Data, Airport Data, and Gallery image search.
- Updated the backend browser proxy to use a modern desktop browser user-agent for proxied web pages.
- Changed Aircraft Data and Airport Data browser layout back to a wide right-side browser pane in browser mode.
- Reworked Explore Globe into a safer stable preview that keeps the 2D map mounted and switches an overlay instead of tearing the map down.
- Added built-in aircraft livery scanning from `SimObjects/Airplanes/**/aircraft.cfg`.
- Internal aircraft liveries now read `ui_variation` from `[FLTSIM.X]` sections and resolve thumbnails from matching `texture.*` folders.
- Built-in liveries are marked as built-in and are not batch-activated like external livery packages.
