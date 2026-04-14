# MSFS Hangar Release 149

## Highlights
- Reworked built-in livery card presentation for airliner vs non-airliner aircraft.
- Added broader thumbnail access for built-in livery images under add-on package paths.
- Rebuilt Explore Globe around MapLibre globe projection with brighter style defaults, reset/zoom controls, compass, and distance readout.
- Kept the original 2D Global Map mounted while the globe view is active to reduce blank-map returns when switching back.
- Added initial airport overlay architecture scaffold for future MSFS 2024 runway/taxiway/parking rendering.

## Built-in liveries
- Built-in scanning stays inside the current aircraft package under `SimObjects/Airplanes`.
- Airliners use the variant name (`ui_variation`) as the card header.
- Non-airliners use the model (`icao_model`) as the card header and keep the variant/registration below.
- Built-in cards show `Airline ATC Code` when available and move `Package` to the last row.
- Internal livery image serving now also allows paths beneath known add-on package roots.

## Explore Globe
- Added MapLibre globe styles: Bright, Liberty, Positron, Voyager, Dark Matter, Satellite, and 3D Terrain (experimental where supported by the remote style).
- Added Reset Globe button, zoom buttons, compass indicator, and a user-unit distance readout.
- Clicking an airport marker now flies toward a closer airport-detail view instead of only centering the marker.
- Globe markers remain visible at all times; ICAO labels follow the label toggle.

## Airport overlay architecture
- Added `msfs_airport_overlay.py` as an architecture scaffold for future MSFS 2024 airport overlay rendering from facility/scenery data.
- Added `/api/airport-overlay/{addon_id}` placeholder endpoint.
