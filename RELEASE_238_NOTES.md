# MSFS Hangar Release 238

## Goal
Keep MSFS Hangar as the shell, but stop depending on the broken Python-only Virtual Pilot path for actual SimConnect flying.

## What changed
- Added an **Integrated Virtual Pilot Engine** wrapper around the Pomax runtime.
- Added a new backend service manager in `pomax_service.py`.
- Bundled the **runtime-essential** Pomax files under `pomax-core/` instead of shipping the full tutorial repo.
- Virtual Pilot now exposes start/stop/open controls for the integrated Pomax sidecar from inside the app.
- In **Qt desktop mode**, the real Pomax client opens inside the app's native browser panel.
- If Node.js is not already installed on Windows, the app can auto-download the official portable Node.js zip and extract it under the user data folder on first Virtual Pilot start.
- The service manager then runs `npm ci` automatically for the Pomax runtime and launches the API server on **3080** and the web client on **3300**.

## Important notes
- This build is aimed at **desktop Qt mode**.
- The Pomax sidecar is now integrated into the application workflow, but it is still a sidecar service under the hood.
- Hangar route import/export is **not yet bridged** into Pomax in this build.
- The main objective of 238 is to restore **real SimConnect-backed Virtual Pilot capability** inside MSFS Hangar without requiring manual Node setup.

## How to run
1. Run `run_hangar_desktop.bat`
2. Open **Virtual Pilot**
3. Click **Start Integrated VP**
4. Wait for status to turn **Ready**
5. Click **Open VP Panel**

On first run, the app may need a few minutes to download portable Node and run npm install. That only happens if Node is missing or the runtime dependencies are not present yet.
