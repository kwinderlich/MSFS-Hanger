# MSFS Hangar Release 143

## Fixes

- Fixed the livery scan endpoint crash caused by `_addon_allows_external_liveries` not being defined.
- Limited external livery scanning to publishers that actually use shared external livery folders: iniBuilds, PMDG, iFly, TFDi/tfdidesign.
- Kept built-in livery scanning inside the current aircraft package under `SimObjects/Airplanes/**`.
- Prevented double-adding built-in liveries during the scan process.

## Explore Globe / Global Map

- Reworked Explore Globe to use the same stable Leaflet world map engine as the current Global Map instead of the fragile custom preview.
- The map now stays mounted when switching between Current Global Map and Explore Globe, so the world background should not disappear.
- Added a Terrain layer alongside Satellite and Road.
- Explore Globe now supports the same zoom-to-airport workflow, map markers, ICAO labels, and layer switching as the stable world map.

## Notes

- `run_hangar_desktop.bat` continues to default to Qt desktop mode.
