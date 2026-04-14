# MapLibre Explorer Notes

This note expands the uploaded MapLibre examples and captures how MSFS Hangar should use them.

## Useful MapLibre patterns

- Globe projection with raster or vector styles.
- `flyTo` for airport focus transitions.
- `NavigationControl` with compass and zoom controls.
- 3D terrain using `raster-dem` or a compatible terrain style.
- Measurement overlays for route and distance tools.
- Symbol and circle layers for airport markers and ICAO labels.
- `fill`, `line`, and `fill-extrusion` layers for future airport overlays.

## Globe implementation direction

- Start Explore Globe at full-world zoom on a round globe.
- Keep markers visible at all zoom levels.
- Clicking a marker should fly toward a local airport-detail zoom around 200 meters AGL equivalent.
- Preserve current airport selection and allow the airport list to focus / zoom on the globe.
- Support brighter styles plus Dark Matter, Positron, Voyager, Satellite, and Topography.

## Future airport overlay layers

Use separate GeoJSON or vector layers for:
- airport boundary
- runways
- taxiways
- parking stands / ramp spots
- helipads / seaplane bases
- approach lighting or guidance markers
- labels for stands, runways, taxiway names

## Suggested layer stack

1. base map style
2. terrain / DEM
3. airport boundary polygon
4. runway polygons
5. taxiway centerlines / surfaces
6. parking stand polygons / points
7. airport markers
8. ICAO / FAA labels
9. focused-airport highlight

## MSFS 2024 overlay architecture

The backend should accept exported airport data and normalize it into GeoJSON collections such as:
- boundary.geojson
- runways.geojson
- taxiways.geojson
- parking.geojson
- labels.geojson

Then the frontend can render those as optional overlays on both the 2D Global Map and Explore Globe.
