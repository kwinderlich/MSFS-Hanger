from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

from paths import BROWSER_PROFILE_DIR, USER_DATA_DIR, SETTINGS_JSON_PATH, load_settings_file

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QSystemTrayIcon, QMenu, QFileDialog,
        QMessageBox, QInputDialog, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QSplitter
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineProfile
    from PySide6.QtCore import QUrl, Qt, QSettings, QTimer
    from PySide6.QtGui import (
        QIcon, QPixmap, QColor, QAction, QPainter,
        QFont, QPen, QLinearGradient, QBrush, QKeySequence
    )
    from PySide6.QtGui import QShortcut
    PYSIDE_OK = True
except ImportError:
    PYSIDE_OK = False


def check_pyside() -> bool:
    return PYSIDE_OK


APP_NAME = "MSFS Hangar"
ORG_NAME = "MSFSHangar"
DEFAULT_W = 1650
DEFAULT_H = 980


def _make_icon() -> "QIcon":
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 64, 64)
    g.setColorAt(0, QColor("#0EA5E9"))
    g.setColorAt(1, QColor("#6366F1"))
    p.setBrush(QBrush(g))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    f = QFont("Segoe UI", 26, QFont.Bold)
    p.setFont(f)
    p.setPen(QPen(QColor("white")))
    p.drawText(px.rect(), Qt.AlignCenter, "H")
    p.end()
    return QIcon(px)


def _dark_titlebar(hwnd):
    try:
        import ctypes
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)),
            ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


class HangarPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        try:
            from logger import get_logger
            log = get_logger("browser.js")
            lvl = level.value if hasattr(level, 'value') else 0
            if lvl >= 3:
                log.error("JS %s:%d — %s", source.split("/")[-1], line, message)
            elif lvl == 2:
                log.warning("JS %s:%d — %s", source.split("/")[-1], line, message)
            else:
                log.debug("JS %s:%d — %s", source.split("/")[-1], line, message)
        except Exception:
            pass

    def javaScriptAlert(self, _url, msg):
        b = QMessageBox(); b.setWindowTitle(APP_NAME)
        b.setText(msg); b.setIcon(QMessageBox.Information); b.exec()

    def javaScriptConfirm(self, _url, msg) -> bool:
        b = QMessageBox(); b.setWindowTitle(APP_NAME); b.setText(msg)
        b.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        return b.exec() == QMessageBox.Yes

    def javaScriptPrompt(self, _url, msg, default, result) -> bool:
        text, ok = QInputDialog.getText(None, APP_NAME, msg, text=default)
        if ok:
            result.setValue(text)
        return ok


class NativeBrowserPage(QWebEnginePage):
    def __init__(self, profile, owner):
        super().__init__(profile, owner)
        self._owner = owner

    def createWindow(self, _type):
        # Keep popup/new-tab navigation in the same native pane.
        self._owner.show_browser_panel()
        return self._owner._native_page

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame:
            self._owner._set_browser_url(url.toString())
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def javaScriptConsoleMessage(self, level, message, line, source):
        try:
            from logger import get_logger
            get_logger("native.browser.js").debug("JS %s:%d — %s", source.split("/")[-1], line, message)
        except Exception:
            pass


class HangarWindow(QMainWindow):
    def __init__(self, port: int = 7891):
        super().__init__()
        self._port = port
        self._url = f"http://127.0.0.1:{port}"
        self._cfg = QSettings(ORG_NAME, APP_NAME)
        self._devtools = None
        self._browser_state = {}
        self._requested_url = ""
        self._requested_id = 0

        icon = _make_icon()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(1100, 720)
        _dark_titlebar(int(self.winId()))

        profile_path = Path(BROWSER_PROFILE_DIR)
        app_storage = profile_path / 'app'
        app_cache = profile_path / 'app_cache'
        native_storage = profile_path / 'native'
        native_cache = profile_path / 'native_cache'
        for folder in (profile_path, app_storage, app_cache, native_storage, native_cache):
            folder.mkdir(parents=True, exist_ok=True)

        # Use explicit profile paths but disable Chromium's on-disk HTTP cache.
        # Earlier builds could emit noisy cross-drive cache-move errors on Windows
        # when QtWebEngine tried to recycle old cache folders. The app data itself
        # lives in SQLite; these profiles are only for browser state.
        self._profile = QWebEngineProfile("HangarProfile", None)
        self._profile.setPersistentStoragePath(str(app_storage))
        self._profile.setHttpCacheType(QWebEngineProfile.NoCache)
        self._profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        self._native_profile = QWebEngineProfile("HangarNativeProfile", None)
        self._native_profile.setPersistentStoragePath(str(native_storage))
        self._native_profile.setHttpCacheType(QWebEngineProfile.NoCache)
        self._native_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        # Main app browser
        self._app_page = HangarPage(self._profile)
        self._browser = QWebEngineView()
        self._browser.setPage(self._app_page)
        self._enable_browser_settings(self._browser)
        self._setup_bridge()

        # Native browsing panel
        self._native_page = NativeBrowserPage(self._native_profile, self)
        self._native_browser = QWebEngineView()
        self._native_browser.setPage(self._native_page)
        self._enable_browser_settings(self._native_browser)
        self._native_browser.setUrl(QUrl("about:blank"))
        self._native_browser.urlChanged.connect(lambda u: self._report_browser_state(u.toString(), self._native_browser.title()))
        self._native_browser.titleChanged.connect(lambda t: self._report_browser_state(self._native_browser.url().toString(), t))
        self._native_browser.loadFinished.connect(lambda ok: self._report_browser_state(self._native_browser.url().toString(), self._native_browser.title()))

        self._browser_title = QLabel("Native Browser")
        self._browser_title.setStyleSheet("font-weight:600;color:#E2E8F0")
        self._browser_url = QLineEdit()
        self._browser_url.setPlaceholderText("https://...")
        self._browser_url.returnPressed.connect(self._go_native_url)
        self._browser_url.setStyleSheet("background:#0F172A;color:#E2E8F0;border:1px solid #334155;padding:6px 8px;border-radius:6px;")
        btn_go = QPushButton("Go")
        btn_go.clicked.connect(self._go_native_url)
        btn_back = QPushButton("←")
        btn_back.clicked.connect(self._native_browser.back)
        btn_fwd = QPushButton("→")
        btn_fwd.clicked.connect(self._native_browser.forward)
        btn_reload = QPushButton("↻")
        btn_reload.clicked.connect(self._native_browser.reload)
        btn_open = QPushButton("External")
        btn_open.clicked.connect(self._open_native_external)
        btn_hide = QPushButton("Hide")
        btn_hide.clicked.connect(self.hide_browser_panel)
        for b in [btn_go, btn_back, btn_fwd, btn_reload, btn_open, btn_hide]:
            b.setStyleSheet("background:#0F172A;color:#E2E8F0;border:1px solid #334155;padding:6px 10px;border-radius:6px;")

        self._browser_panel = QWidget()
        right_layout = QVBoxLayout(self._browser_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(self._browser_title, 1)
        top.addWidget(btn_back)
        top.addWidget(btn_fwd)
        top.addWidget(btn_reload)
        top.addWidget(btn_open)
        top.addWidget(btn_hide)
        right_layout.addLayout(top)
        url_row = QHBoxLayout()
        url_row.addWidget(self._browser_url, 1)
        url_row.addWidget(btn_go)
        right_layout.addLayout(url_row)
        right_layout.addWidget(self._native_browser, 1)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setOpaqueResize(False)
        self._splitter.setHandleWidth(6)
        self._splitter.addWidget(self._browser)
        self._splitter.addWidget(self._browser_panel)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._browser_sizes = None
        self.setCentralWidget(self._splitter)
        self._loading_overlay = QLabel("Please wait - App Starting", self._splitter)
        self._loading_overlay.setAlignment(Qt.AlignCenter)
        self._loading_overlay.setStyleSheet("background:rgba(10,22,40,0.92);color:#F8FAFC;border:1px solid #334155;border-radius:12px;font-size:18px;font-weight:700;padding:18px;")
        self._loading_overlay.raise_()
        self.hide_browser_panel(initial=True)

        self._browser.loadFinished.connect(self._on_load_finished)
        self._browser.loadStarted.connect(lambda: self._log(f"App load started: {self._url}"))
        self._browser.loadProgress.connect(lambda p: self._log(f"App load progress: {p}%"))
        try:
            self._browser.renderProcessTerminated.connect(lambda status, code: self._log(f"App browser render process terminated: status={status} code={code}"))
            self._native_browser.renderProcessTerminated.connect(lambda status, code: self._log(f"Native browser render process terminated: status={status} code={code}"))
        except Exception:
            pass

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(f"MSFS Hangar — {self._url}")
        self._build_tray_menu()
        self._tray.activated.connect(lambda r: self.show_and_raise() if r == QSystemTrayIcon.DoubleClick else None)
        self._tray.show()

        QShortcut(QKeySequence("F5"), self).activated.connect(self._browser.reload)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._browser.reload)
        QShortcut(QKeySequence("F12"), self).activated.connect(self._open_devtools)

        geom = self._cfg.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(DEFAULT_W, DEFAULT_H)
            screen = QApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - DEFAULT_W) // 2, (screen.height() - DEFAULT_H) // 2)

        self._log(f"Using user data dir: {USER_DATA_DIR}")
        self._log(f"Settings file: {SETTINGS_JSON_PATH}")
        self._browser.setUrl(QUrl(self._url))

        self._browser_timer = QTimer(self)
        self._browser_timer.timeout.connect(self._sync_browser_state)
        self._browser_timer.start(2500)

    def _enable_browser_settings(self, view: QWebEngineView):
        s = view.settings()
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        try:
            s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        except Exception:
            pass

    def _api_json(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        url = self._url + path
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(url, data=data, headers=headers, method=method)
        with urlrequest.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}

    def _sync_browser_state(self):
        try:
            state = self._api_json("/api/browser/state")
        except Exception:
            return
        self._browser_state = state
        requested = state.get("requested_url") or ""
        requested_id = int(state.get("request_id") or 0)
        visible = bool(state.get("visible"))
        if visible and requested:
            self.show_browser_panel()
            if requested != self._requested_url or requested_id != self._requested_id:
                self._requested_url = requested
                self._requested_id = requested_id
                self._native_browser.setUrl(QUrl(requested))
                self._browser_title.setText(state.get("requested_title") or requested)
                self._browser_url.setText(requested)
        else:
            self._requested_url = ""
            self._requested_id = 0
            if self._browser_panel.isVisible():
                self.hide_browser_panel()

    def _normalize_state_url(self, url: str) -> str:
        try:
            from urllib.parse import urlparse, parse_qs, unquote
            parsed = urlparse(url or "")
            if parsed.path.endswith('/api/research/open'):
                q = parse_qs(parsed.query).get('url', [''])[0]
                return unquote(q) or url
            if parsed.path.endswith('/api/research/searchpage'):
                q = parse_qs(parsed.query).get('q', [''])[0]
                return 'search:' + (unquote(q) or '')
        except Exception:
            return url
        return url

    def _emit_app_browser_state(self, url: str, title: str, visible: bool):
        try:
            payload = json.dumps({
                "type": "hangar-native-browser-state",
                "url": url or "",
                "title": title or "",
                "visible": bool(visible),
            })
            js = f"try{{window.postMessage({payload}, '*');}}catch(e){{}}"
            self._browser.page().runJavaScript(js)
        except Exception:
            pass

    def _report_browser_state(self, url: str, title: str):
        try:
            display_url = self._normalize_state_url(url or "")
            display_title = title or "Native Browser"
            if isinstance(display_url, str) and display_url.startswith("search:") and display_title in {"MSFS Hangar", "Native Browser"}:
                display_title = display_url
            self._browser_title.setText(display_title or "Native Browser")
            self._browser_url.setText(display_url or "")
            self._emit_app_browser_state(display_url or "", display_title or "Native Browser", True)
            self._api_json("/api/browser/update", method="POST", payload={
                "current_url": display_url,
                "current_title": display_title,
                "visible": True,
            })
        except Exception:
            pass

    def _set_browser_url(self, url: str):
        self._browser_url.setText(url or "")

    def _go_native_url(self):
        url = self._browser_url.text().strip()
        if not url:
            return
        if not (url.startswith(("http://", "https://")) or "." in url.split()[0]):
            from urllib.parse import quote_plus
            provider = 'bing'
            try:
                provider = str(load_settings_file().get('search_provider') or 'bing').strip().lower()
            except Exception:
                provider = 'bing'
            if provider == 'google':
                url = "https://www.google.com/search?hl=en&gl=us&pws=0&q=" + quote_plus(url)
            else:
                url = "https://www.bing.com/search?q=" + quote_plus(url)
        elif not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.show_browser_panel()
        self._requested_url = url
        self._requested_id = 0
        self._native_browser.setUrl(QUrl(url))
        self._report_browser_state(url, self._native_browser.title() or url)

    def _open_native_external(self):
        import webbrowser
        url = self._native_browser.url().toString()
        if url and url != "about:blank":
            webbrowser.open(url)

    def show_browser_panel(self):
        if self._browser_panel.isVisible():
            return
        self._browser_panel.show()
        if self._browser_sizes and len(self._browser_sizes) == 2 and self._browser_sizes[1] > 0:
            self._splitter.setSizes(self._browser_sizes)
        else:
            total = max(self.width(), 1400)
            self._browser_sizes = [int(total * 0.58), int(total * 0.42)]
            self._splitter.setSizes(self._browser_sizes)

    def hide_browser_panel(self, initial: bool = False):
        if not initial:
            try:
                self._api_json("/api/browser/close", method="POST", payload={})
            except Exception:
                pass
        try:
            if self._browser_panel.isVisible():
                self._browser_sizes = self._splitter.sizes()
        except Exception:
            pass
        try:
            self._native_browser.stop()
        except Exception:
            pass
        try:
            self._native_browser.setUrl(QUrl("about:blank"))
        except Exception:
            pass
        self._browser_title.setText("Native Browser")
        self._browser_url.setText("")
        self._emit_app_browser_state("", "", False)
        self._browser_panel.hide()
        self._splitter.setSizes([1, 0])

    def _log(self, message: str):
        try:
            print(f"[desktop] {message}", flush=True)
            from logger import get_logger
            get_logger("desktop").warning(message)
        except Exception:
            pass

    def _setup_bridge(self):
        try:
            from PySide6.QtWebChannel import QWebChannel
            from PySide6.QtCore import QObject, Slot

            class Bridge(QObject):
                @Slot(str, str, result=str)
                def pickFolder(self, title: str = "Select Folder", current: str = "") -> str:
                    start = current if current and Path(current).exists() else str(Path.home())
                    return QFileDialog.getExistingDirectory(
                        self.parent(), title or "Select Folder", start,
                        QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
                    ) or ""

                @Slot(str, str, str, result=str)
                def pickFile(self, title: str = "Select File", current: str = "", pattern: str = "") -> str:
                    start = current if current and Path(current).exists() else str(Path.home())
                    filt = pattern or "All Files (*)"
                    # Accept web-style *.ext,*.ext lists from the frontend and turn them into
                    # a Qt file-filter expression.
                    if filt and ';;' not in filt and '(' not in filt:
                        parts = [part.strip() for part in filt.split(',') if part.strip()]
                        filt = f"Matching Files ({' '.join(parts)});;All Files (*)" if parts else "All Files (*)"
                    path, _ = QFileDialog.getOpenFileName(
                        self.parent(), title or "Select File", start, filt
                    )
                    return path or ""

            self._bridge = Bridge(self)
            ch = QWebChannel(self)
            ch.registerObject("bridge", self._bridge)
            self._app_page.setWebChannel(ch)
        except Exception:
            pass

    def _on_load_finished(self, ok: bool):
        self._log(f"App load finished: ok={ok}, url={self._browser.url().toString()}")
        try:
            if ok:
                self._loading_overlay.hide()
            else:
                self._loading_overlay.show()
                self._loading_overlay.setText("MSFS Hangar could not load the UI")
        except Exception:
            pass
        if ok:
            return
        html = f'<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#0A1628;color:#F1F5F9;padding:24px"><h2>MSFS Hangar could not load the UI</h2><p>The backend URL was <code>{self._url}</code>.</p></body></html>'
        self._browser.setHtml(html, QUrl(self._url))

    def _build_tray_menu(self):
        m = QMenu()
        a_open = QAction("Open Hangar", self)
        a_open.triggered.connect(self.show_and_raise)
        a_diag = QAction("View Diagnostics", self)
        a_diag.triggered.connect(lambda: self._browser.setUrl(QUrl(self._url + "/api/diag")))
        a_reload = QAction("Reload UI (F5)", self)
        a_reload.triggered.connect(self._browser.reload)
        a_quit = QAction("Quit MSFS Hangar", self)
        a_quit.triggered.connect(QApplication.quit)
        m.addAction(a_open)
        m.addSeparator()
        m.addAction(a_reload)
        m.addAction(a_diag)
        m.addSeparator()
        m.addAction(a_quit)
        self._tray.setContextMenu(m)

    def _open_devtools(self):
        if not self._devtools:
            self._devtools = QWebEngineView()
            self._devtools.setWindowTitle(f"{APP_NAME} — DevTools")
            self._devtools.resize(1100, 700)
        self._app_page.setDevToolsPage(self._devtools.page())
        self._devtools.show()
        self._devtools.raise_()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            sizes = self._splitter.sizes()
            left_width = sizes[0] if sizes else max(320, int(self.width() * 0.68))
            self._loading_overlay.setGeometry(18, 18, max(320, left_width - 36), max(72, self.height() - 54))
            self._loading_overlay.raise_()
        except Exception:
            pass

    def closeEvent(self, event):
        self._cfg.setValue("geometry", self.saveGeometry())
        self.hide()
        self._tray.showMessage(APP_NAME, "MSFS Hangar is still running. Right-click the tray icon → Quit to exit.", QSystemTrayIcon.Information, 2500)
        event.ignore()


def run_desktop_window(port: int = 7891) -> int:
    if not PYSIDE_OK:
        return 1
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)
    win = HangarWindow(port=port)
    win.show()
    return app.exec()
