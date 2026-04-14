# Release 157 Notes

- Fixed startup crash caused by `viewMode` being referenced inside `useIsMobile()` before `viewMode` existed.
- The mobile resize effect now uses an empty dependency array so the app can finish loading normally.
