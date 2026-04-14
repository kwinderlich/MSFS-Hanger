# MSFS Hangar Release 135

## What changed

### Window position and size persistence
- Added desktop-shell window state persistence.
- MSFS Hangar now saves the last known desktop app-window position, size, and maximized state into user settings.
- On the next desktop launch, the Edge/Chrome app shell reopens using the saved size and position so the app can return to the same monitor and footprint when possible.

### Explore Globe (Phase 1 preview)
- Added a new **Explore Globe** option inside the existing **Global Map** screen.
- The original 2D **Current Global Map** remains available.
- The new globe preview lets you:
  - orbit the globe with the mouse
  - zoom in/out
  - click airport markers
  - focus the selected airport on the globe
  - open the selected airport detail from the globe workflow
- The airport list and focused-airport panel remain shared between the 2D map and globe modes.

## Notes
- The VFR Route Planner remains on the original 2D map for now.
- Globe mode in this release is intentionally an early preview so the UI direction can be tested before adding terrain, route arcs, or live-flight features.
