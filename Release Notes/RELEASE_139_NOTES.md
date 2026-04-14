# Release 139 Notes

- Removed the unused globe.gl CDN script from the frontend shell to reduce client-side instability in desktop app-window mode.
- Reworked Explore Globe safe preview to cap and cluster very large airport point sets before drawing, reducing renderer load.
- Added additional frontend diagnostics for Explore Globe entry and map view-mode changes.
- Explore Globe status now shows rendered point counts and when clustering is active.
