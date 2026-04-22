# MSFS Hangar Release 239

This release focuses on the integrated Pomax Virtual Pilot wrapper.

## What changed

- Starts the Pomax web client in `--owner` mode.
- Writes `FLIGHT_OWNER_USERNAME`, `FLIGHT_OWNER_PASSWORD`, and `FLIGHT_OWNER_KEY` into the generated `.env` so browser actions can authenticate against the API server.
- Adds **Start VP (Mock)** so the Pomax tutorial flow can be validated without MSFS running.
- Updates the integrated VP screen to show:
  - Release 239 badge
  - current mode (live/mock)
  - owner auth state
  - tutorial validation hint
- Keeps the integrated VP panel inside the Hangar desktop shell.

## Expected behavior to validate

### Mock mode
1. Open **Virtual Pilot**.
2. Click **Start VP (Mock)**.
3. Click **Open VP Panel**.
4. In the VP panel:
   - clicking **AP** should turn it red after the client/server round-trip.
   - clicking the map should add waypoints.

### Live mode
1. Start MSFS 2024.
2. Load into an aircraft.
3. In Hangar Virtual Pilot, click **Start Integrated VP**.
4. Click **Open VP Panel**.
5. Use the VP panel against the live sim.

## Important note

This release does **not** attempt to rewrite Pomax into Python. It fixes the wrapper so the Pomax tutorial's owner-authenticated client/server behavior is actually used.
