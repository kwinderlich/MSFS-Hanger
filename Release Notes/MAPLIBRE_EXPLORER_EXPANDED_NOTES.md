# MapLibre Explorer Expanded Notes

This file extends the user-provided MapLibre examples with app-specific patterns for MSFS Hangar.

## Core patterns
- Globe with atmosphere for first entry and Reset Globe.
- Fly-to camera transitions for region jumps, airport selection, and focus changes.
- NavigationControl kept visible as the default map overlay.
- Terrain toggle using a raster-dem source and `setTerrain`.
- Buildings toggle using a vector building layer with fill-extrusion.
- Two-point measure tool based on a GeoJSON source with point, line, and label features.
- Airport markers rendered as circle layers so they can be color-coded by airport subtype.
- ICAO / FAA labels rendered as a symbol layer with stronger halo and overlap allowed.

## Suggested base styles
- OpenFreeMap Bright
- OpenFreeMap Liberty
- CARTO Positron
- CARTO Voyager
- CARTO Dark Matter
- Satellite raster style
- Topographic raster style

## Regional fly-to presets
- World
- North America
- South America
- Europe
- Africa
- Asia
- Oceania
- Caribbean

## Airport overlay roadmap
Backend should normalize airport data into:
- runways.geojson
- taxi_paths.geojson
- taxi_points.geojson
- parking.geojson
- starts.geojson
- jetways.geojson
- airport_meta.json

Frontend should add each as a dedicated source/layer set with visibility toggles.
