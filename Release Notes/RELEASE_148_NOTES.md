# MSFS Hangar Release 148

## Livery handling
- Reworked built-in livery card display for aircraft variants that live inside the aircraft package.
- For built-in airliners, the card header now prefers the variant name (`ui_variation`).
- For built-in GA / non-airliner aircraft, the card header now prefers the model (`icao_model`).
- Removed Flight row from built-in livery cards.
- Renamed Airline row to **Airline ATC Code**.
- Moved Package row to the bottom of the card details.
- Hid Active / Shared Package chips for built-in livery cards.
- Internal scan now tags built-in items with `is_airliner` so the UI can format them correctly.

## Explore Globe / Global Map
- Increased Explore Globe max zoom and click-to-focus zoom depth.
- Disabled clustering in Explore Globe so airport markers stay visible as individual markers.
- Increased marker hit target size for easier clicking.
- Globe marker click now flies directly toward the airport instead of only centering it.
- Added a refresh/invalidate pass when returning from Explore Globe to Current Global Map to reduce blank-map cases.

## Notes
- Localization settings already exist under **Settings → User Interface → Localization** and continue to control language, currency, calendar format, and route/distance units.
