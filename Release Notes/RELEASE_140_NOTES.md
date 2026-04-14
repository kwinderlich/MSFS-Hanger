MSFS Hangar Release 140

What changed
- Replaced Explore Globe canvas renderer with a simpler SVG-based safe preview to avoid immediate renderer crashes when switching views.
- Kept preserved view state, dot markers, zoom, pan, and click-to-select behavior.
- Reduced visible point load further with viewport-aware clustering and simpler drawing.
- Bumped saved global-map state storage key so older cached globe state will not interfere with the safe preview test.

Purpose
- This release is specifically for isolating and avoiding the immediate Explore Globe crash that was occurring before frontend logging could fire.
