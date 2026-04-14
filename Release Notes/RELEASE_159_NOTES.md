MSFS Hangar Release 159

Explorer Globe fixes:
- Globe now restores/chooses a selected airport on open, using the saved selection when available and otherwise the nearest available airport.
- Region selector now targets an altitude-style zoom closer to 1250 NM (world reset remains ~2959.78 NM).
- Marker clicks were reworked to use queryRenderedFeatures against the airport marker layers, restoring airport selection and moderate zoom-in behavior.
- Marker hover popup still shows ICAO/FAA code and full airport name.
- Measure tool was rewired to use a direct two-click map handler:
  - click point A
  - click point B
  - dashed line
  - midpoint distance label
- Measure points now render as dark dots with a light outline for clarity.
- Center button in the selected-airport row now preserves current zoom while re-centering the globe.
- Center Current overlay button removed from the map.
- Distance-from-ground readout moved up under the left navigation controls.
- Added an idle refresh pass so airport marker layers are more likely to appear immediately when the globe first opens.
