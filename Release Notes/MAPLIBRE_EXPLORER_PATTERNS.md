MapLibre Explorer Patterns

Useful patterns carried forward from the uploaded MapLibre examples:

1. Globe with atmosphere
- Start Explore Globe using projection: globe
- Apply a sky / atmosphere blend on initial world view
- Reset Globe should always return to this full-world globe state

2. Navigation control
- Use MapLibre NavigationControl with zoom buttons and compass
- Keep additional app-specific controls for Reset Globe, Center Current, and airport zoom actions

3. Fly-to airport
- Marker clicks should select the airport, update the current-airport panel, and fly to a near-ground view
- Airport list actions should refocus / zoom using the same flyTo behavior

4. Terrain toggle
- Terrain should be optional and user-controlled
- Use raster-dem + hillshade + terrain exaggeration for terrain-enabled views

5. Measure mode
- Measure mode on the globe should show a simple line and distance between clicked positions
- Keep it separate from the 2D VFR route planner

6. Labels
- Airport ICAO / FAA labels need a glyphs entry in the style
- Use larger text, stronger halo, and overlap allowed for better readability

7. Overlay architecture for MSFS airports
- Airport overlays should be their own source/layer group so they can be turned on or off independent of the base map
- Planned overlay layer groups:
  - runway centerlines / surfaces
  - taxiways
  - parking / gates
  - apron polygons
  - airport boundary
  - labels (runways, taxiways, parking stands)

Recommended next data sample for overlay testing:
- one MSFS 2024 airport export containing runway geometry, taxiway geometry, parking positions, airport boundary, and labels/names if available
