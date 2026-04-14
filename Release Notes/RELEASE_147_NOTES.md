# MSFS Hangar Release 147

## Livery management
- tightened built-in livery parsing to stay inside the current aircraft package only
- improved MSFS cfg parsing so inline comments after values no longer pollute ui_variation or texture values
- built-in livery cards now prefer:
  - `[GENERAL] icao_model` as the base model title
  - `[FLTSIM.X] ui_variation` as the header when it already contains the model family
  - `atc_airline` and `atc_flight_number` as supporting rows when present
- built-in livery thumbnails resolve from `texture.<token>/thumbnail.*`
- package name for built-in liveries remains the folder directly under `SimObjects/Airplanes`

## Explore Globe
- kept Explore Globe on MapLibre GL JS
- increased zoom depth and click-to-focus zoom for airport markers
- marker labels can appear earlier when ICAO/FAA labels are enabled

## Notes
- this build continues using the MapLibre GL JS browser library already integrated into the frontend
- a future offline-bundled pass can vendor the MapLibre assets locally if desired
