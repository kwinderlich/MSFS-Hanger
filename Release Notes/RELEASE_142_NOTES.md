# MSFS Hangar Release 142

- `run_hangar_desktop.bat` now launches Qt desktop mode by default because the app-window mode was causing broken embedded-browser behavior in the detail tabs.
- Fixed Gallery tab crash in Qt mode caused by an undefined `defaultQ` variable.
- Tightened built-in livery scanning so it stays inside the current aircraft package under `SimObjects/Airplanes/**`.
- Built-in liveries now use `[GENERAL] icao_model` as the card title, keep the registration/texture token as the variant value, and use the variant folder name as the package name.
- External designated-liveries-folder scanning is now limited to publishers that actually use it (`iniBuilds`, `PMDG`, `iFly`, `TFDi`).
- Explore Globe preview now preserves the safer implementation but adds a simple world-map backdrop, bigger click targets, click-to-focus zoom, higher max zoom, and optional ICAO labels from the map toggle.
