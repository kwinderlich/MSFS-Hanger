MSFS Hangar Release 133

What changed
- Added verified app-folder move flow.
- Added optional old-folder cleanup after a verified copy; cleanup is deferred to the next launch so the running session does not try to delete files it still has open.
- Added copy verification details to the Application screen result payload.
- Added pending old-folder cleanup display in Settings → Application.
- Kept Google search behavior and Release 131/132 profile/bootstrap changes.

Notes
- When “Remove the old folder after a verified copy” is enabled, Release 133 writes the previous folder into the bootstrap config as pending cleanup and removes it on the next launch after switching to the new root.
- Verification checks copied top-level files and directories, then confirms the copied settings.json and hangar.db can be read back by path.
