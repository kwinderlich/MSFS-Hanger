# MSFS Hangar Release 165

- Fixed Global Map / Explorer Globe regression where airport markers and airport list data failed to render because shared marker-color helpers were not defined in the Global Map scope.
- Moved airport marker color/size helper functions to shared frontend scope so both Globe and Global Map logic can use them safely.
- This is a focused hotfix release for the `safeSubtypeColor is not defined` error.
