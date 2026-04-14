This build updates the Release 129 baseline with two targeted changes:

1. Browser search is forced back to Google for:
   - Research tab
   - Airport Data browser
   - Aircraft Data browser
   - image-search flows that use the embedded browser

2. Settings > Application is simplified:
   - shows the current base app folder
   - lets the user browse to a new app folder using a native folder picker
   - saves that folder as the forced storage root for the next launch
   - optionally copies current app data into the new folder
   - can reveal the active app folder in Explorer/Finder
   - creates a backup zip with a native Save dialog using the name pattern:
     MSFSHangar Backup YYYYMMDD_HHMMSS.zip

Technical notes:
- The forced storage root is persisted in a bootstrap config file:
  MSFSHangar_bootstrap.json in the user's home directory.
- The current session continues using the active folder until the app is restarted.
- Storage test now fails loudly if write/read-back verification does not succeed immediately.
