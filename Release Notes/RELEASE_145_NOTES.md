# MSFS Hangar Release 145

## Built-in livery / variant scanning
- Reworked built-in livery scanning to stay strictly inside the current aircraft package.
- Built-in variants are scanned only from `SimObjects/Airplanes/<variant-folder>/aircraft.cfg`.
- For each `[FLTSIM.X]` entry:
  - card header prefers `ui_variation` when it already contains the model family
  - otherwise header uses `[GENERAL] icao_model`
  - package name uses the aircraft variant folder name under `SimObjects/Airplanes`
  - thumbnail resolves from `texture.<token>/thumbnail.*`
- External designated-liveries-folder matching now also checks the external package `manifest.json` title / package name against the current aircraft.

## Explore Globe
- Explore Globe now uses the actual MapLibre GL JS library.
- Added globe projection map view with Road, Satellite, and Topography layers.
- Airport markers are rendered as flat 2D map markers with larger click targets.
- ICAO / FAA labels can display next to markers.
- Clicking an airport marker selects that airport and zooms toward it.

## MapLibre setup
- This release loads MapLibre from CDN links in `frontend/index.html`.
- No extra Python package installation is required for MapLibre in this build.
- A later offline-friendly build can vendor `maplibre-gl.js` and `maplibre-gl.css` locally.
