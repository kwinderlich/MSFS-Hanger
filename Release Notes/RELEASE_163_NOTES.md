MSFS Hangar Release 163

- Hardened Global Map / Explorer Globe airport location resolution.
- Frontend now falls back to /api/map/global-markers for unresolved airports/scenery instead of failing the whole map.
- Resolution failures now degrade gracefully instead of clearing the map immediately.
- This release also keeps the Babel deoptimisation message as a warning only; it is not the root cause of the map-resolution failure.
