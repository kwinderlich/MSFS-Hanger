MSFS 2024 Airport Overlay Architecture

Goal
- Render MSFS 2024 airport layout data as optional overlay layers on top of the selected Explore Globe / Current Global Map base map.

Pipeline
1. Import or convert airport export data into GeoJSON-like normalized objects.
2. Build overlay sources by feature category:
   - runways
   - taxiways
   - aprons
   - parking stands / gates
   - airport boundary
   - labels
3. Add overlay layer groups in MapLibre with per-category visibility toggles.
4. Bind overlay visibility and styling to the selected airport.

Suggested normalized input fields
- airport ident / ICAO
- feature type
- geometry
- name / designation
- surface type
- heading / runway number
- optional lighting / approach data

Most useful sample files for testing
- one airport export with
  - runway polygons or centerlines
  - taxiway polygons or centerlines
  - parking / stand positions
  - airport boundary
  - labels or names
- one screenshot of how the same airport looks in the simulator



Next sample files to provide for MSFS 2024 airport overlays
- Airport identifier and package name
- Runway geometry export
- Taxiway / apron geometry export
- Parking or gate stand coordinates
- Hold-short / taxi-node data if available
- Boundary polygon if available
- The original exported files plus one screenshot from the sim

Planned overlay pipeline
1. Normalize exported airport geometry into GeoJSON feature collections.
2. Separate layers for runways, taxiways, aprons, parking, labels, and optional approach-light overlays.
3. Render these as MapLibre sources and layers on top of the selected base map.
4. Keep the airport overlay optional so the user can switch between normal map view and sim-data overlay view.
