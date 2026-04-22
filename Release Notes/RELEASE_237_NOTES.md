# MSFS Hangar Release 237

This package keeps the current Hangar application intact and adds the actual uploaded Pomax repository as a vendored branch under `pomax-port/`.

## What 237 does
- Keeps the rebuilt 236 Hangar baseline intact.
- Vendors the uploaded Pomax repo under `pomax-port/`.
- Includes Pomax runtime/content folders such as:
  - `current/`
  - `docs/`
  - `parts/`
  - `package.json`
  - `package-lock.json`
  - `run.bat`
  - `README.md`
- Adds a Pomax `.env` configured for local testing:
  - `API_PORT=3080`
  - `WEB_PORT=3300`
- Adds launchers:
  - `run_virtual_pilot_pomax.bat`
  - `run_virtual_pilot_pomax_mock.bat`

## Important distinction
This is the real vendored Pomax codebase branch inside the package. It is **not** a claim that the existing Hangar Python virtual-pilot logic has already been translated line-by-line into Python.

## Practical use
- Use the normal Hangar launchers for the current Hangar app.
- Use the Pomax launchers when you want to test the actual uploaded Node server/client branch.
