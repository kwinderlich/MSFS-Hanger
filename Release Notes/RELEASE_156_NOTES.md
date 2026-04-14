# MSFS Hangar Release 156

## Explorer Globe
- disabled hidden legacy Leaflet map initialization when the globe view is active
- rebuilt globe markers, labels, terrain/buildings toggles, and measure tool on the MapLibre side
- marker click now selects the airport and flies to local detail
- region selector now works in globe mode
- added a range-aircraft selector for dashed range rings
- moved altitude readout under the built-in navigation control
- moved compass up on the lower right
- split Open Global Map away from filter shortcuts visually

## Architecture
- added `mapping.py` as the backend home for future mapping and overlay helpers
