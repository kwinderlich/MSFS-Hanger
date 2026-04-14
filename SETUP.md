# MSFS Hangar

Use `run_hangar.bat` for browser mode on the same PC.
Use `run_hangar_lan.bat` for browser mode accessible from other devices on your LAN.
Use `run_hangar_desktop.bat` for the recommended desktop shell (Edge/Chrome app window).
Use `run_hangar_qt_desktop.bat` only for Qt troubleshooting.

User data is stored outside the app folder in your local app-data directory so zip upgrades do not overwrite your library or settings.


## MapLibre GL JS
This build loads MapLibre GL JS from CDN links in `frontend/index.html`, so there is no extra Python install step for the map engine. If you want a fully offline build later, the JS/CSS files can be vendored into the frontend and the batch/install flow can simply copy them with the rest of the app files.
