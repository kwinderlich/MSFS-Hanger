"""MSFS Hangar launcher."""
import atexit
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('QT_OPENGL', 'software')
_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '').strip()
_extra_flags = '--disable-gpu-compositing --disable-features=UseSkiaRenderer,CanvasOopRasterization --disable-http-cache --disable-application-cache --disable-gpu-shader-disk-cache'
if _extra_flags not in _flags:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (_flags + ' ' + _extra_flags).strip()
from paths import initialize_user_data, PID_FILE, DESKTOP_PID_FILE, CACHE_ROOT, USER_DATA_DIR, SETTINGS_JSON_PATH, DB_PATH, LOG_DIR, load_settings_file
_backend_proc = None
_shell_proc = None

REQUIRED = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "aiosqlite>=0.20.0",
    "websockets>=12.0",
    "python-multipart>=0.0.9",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.3",
]

CACHE_DIRS = ["cache", "Code Cache", "GPUCache", "DawnCache", "GrShaderCache", "GraphiteDawnCache"]


def _pip(*packages):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *packages])


def install_missing():
    import importlib
    checks = {
        "fastapi": REQUIRED[0],
        "uvicorn": REQUIRED[1],
        "aiosqlite": REQUIRED[2],
        "websockets": REQUIRED[3],
        "multipart": REQUIRED[4],
        "requests": REQUIRED[5],
        "bs4": REQUIRED[6],
    }
    missing = []
    for mod, pkg in checks.items():
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(pkg)
    if missing:
        print("Installing missing packages:", ", ".join(missing), flush=True)
        _pip(*missing)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _terminate_pid(pid: int):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
    except Exception:
        pass


def clear_browser_cache():
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    # Clean legacy Chromium cache folders without touching app data stored in
    # SQLite. We also remove service-worker cache folders because the desktop
    # shell does not need them and stale copies were generating noisy startup
    # errors on some Windows systems.
    targets = [CACHE_ROOT / name for name in CACHE_DIRS]
    for profile_cache in [CACHE_ROOT / 'app_cache', CACHE_ROOT / 'native_cache']:
        targets.append(profile_cache)
        for child in profile_cache.glob('old_*'):
            targets.append(child)
    for storage_dir in [CACHE_ROOT / 'app', CACHE_ROOT / 'native']:
        targets.extend([
            storage_dir / 'Service Worker',
            storage_dir / 'GPUCache',
            storage_dir / 'Code Cache',
            storage_dir / 'DawnCache',
            storage_dir / 'GrShaderCache',
            storage_dir / 'GraphiteDawnCache',
        ])
    for target in targets:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


def stop_previous_desktop_instance():
    if not DESKTOP_PID_FILE.exists():
        return
    try:
        old_pid = int(DESKTOP_PID_FILE.read_text().strip())
    except Exception:
        old_pid = None
    if old_pid and old_pid != os.getpid():
        print(f"Stopping previous desktop instance PID {old_pid}...", flush=True)
        _terminate_pid(old_pid)
        time.sleep(1.0)
    try:
        DESKTOP_PID_FILE.unlink()
    except Exception:
        pass


def register_desktop_instance():
    try:
        DESKTOP_PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass


def stop_previous_backend(port: int):
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            print(f"Stopping previous backend PID {old_pid}...", flush=True)
            _terminate_pid(old_pid)
            time.sleep(1.0)
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass
    if _port_in_use(port) and os.name == "nt":
        try:
            out = subprocess.check_output(["netstat", "-ano"], text=True, errors="replace")
            pids = set()
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        try:
                            pids.add(int(parts[-1]))
                        except Exception:
                            pass
            for pid in pids:
                print(f"Terminating process on port {port}: PID {pid}", flush=True)
                _terminate_pid(pid)
            if pids:
                time.sleep(1.0)
        except Exception:
            pass


def start_backend(host: str, port: int):
    global _backend_proc
    cmd = [sys.executable, "-m", "uvicorn", "app:app", "--host", str(host), "--port", str(port), "--log-level", "info"]
    print("Starting backend:", " ".join(cmd), flush=True)
    _backend_proc = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    PID_FILE.write_text(str(_backend_proc.pid))

    def _output():
        assert _backend_proc is not None
        for line in _backend_proc.stdout:
            print("[backend]", line.decode("utf-8", errors="replace").rstrip(), flush=True)

    threading.Thread(target=_output, daemon=True).start()
    return _backend_proc


def stop_backend():
    global _backend_proc, _shell_proc
    if _shell_proc and _shell_proc.poll() is None:
        try:
            _shell_proc.terminate()
        except Exception:
            pass
    if _backend_proc and _backend_proc.poll() is None:
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


atexit.register(stop_backend)


def _cleanup_desktop_pid():
    try:
        if DESKTOP_PID_FILE.exists() and DESKTOP_PID_FILE.read_text().strip() == str(os.getpid()):
            DESKTOP_PID_FILE.unlink()
    except Exception:
        pass

atexit.register(_cleanup_desktop_pid)


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/scan/status"
    while time.time() < deadline:
        if _backend_proc and _backend_proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False




def _local_browser_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"




def _describe_path(path: Path) -> str:
    exists = path.exists()
    if not exists:
        return f"{path} [missing]"
    try:
        stat = path.stat()
        modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        return f"{path} [exists, {stat.st_size:,} bytes, modified {modified}]"
    except Exception:
        return f"{path} [exists]"

def _discover_lan_urls(port: int) -> list[str]:
    urls=[]
    try:
        hostnames={socket.gethostname()}
        try:
            hostnames.add(socket.getfqdn())
        except Exception:
            pass
        ips=set()
        for name in hostnames:
            try:
                for info in socket.getaddrinfo(name, None, family=socket.AF_INET):
                    ip=info[4][0]
                    if ip and not ip.startswith('127.'):
                        ips.add(ip)
            except Exception:
                pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip=s.getsockname()[0]
                if ip and not ip.startswith('127.'):
                    ips.add(ip)
        except Exception:
            pass
        urls=[f"http://{ip}:{port}" for ip in sorted(ips)]
    except Exception:
        pass
    return urls

def open_system_browser(port: int):
    import webbrowser
    url = _local_browser_url(port)
    print(f"Opening system browser at {url}", flush=True)
    webbrowser.open(url)




def _load_saved_window_state() -> dict:
    try:
        settings = load_settings_file() or {}
        raw = settings.get('window_state', {})
        if isinstance(raw, str):
            import json as _json
            raw = _json.loads(raw) if raw.strip() else {}
        if not isinstance(raw, dict):
            return {}
        state = {}
        for key in ('x','y','width','height'):
            try:
                if raw.get(key) is not None:
                    state[key] = int(float(raw.get(key)))
            except Exception:
                pass
        state['maximized'] = bool(raw.get('maximized'))
        return state
    except Exception:
        return {}

def _find_app_browser() -> str | None:
    candidates = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        prog = os.environ.get("PROGRAMFILES", "")
        progx86 = os.environ.get("PROGRAMFILES(X86)", "")
        candidates.extend([
            Path(local) / "Microsoft/Edge/Application/msedge.exe",
            Path(prog) / "Microsoft/Edge/Application/msedge.exe",
            Path(progx86) / "Microsoft/Edge/Application/msedge.exe",
            Path(prog) / "Google/Chrome/Application/chrome.exe",
            Path(progx86) / "Google/Chrome/Application/chrome.exe",
        ])
        for exe in candidates:
            if exe and exe.exists():
                return str(exe)
        for name in ["msedge.exe", "chrome.exe"]:
            try:
                out = subprocess.check_output(["where", name], text=True, stderr=subprocess.DEVNULL)
                first = out.splitlines()[0].strip()
                if first:
                    return first
            except Exception:
                pass
    return None


def open_app_shell(port: int):
    global _shell_proc
    browser = _find_app_browser()
    if not browser:
        print("No Edge/Chrome browser found for app shell mode.", flush=True)
        return False
    url = _local_browser_url(port)
    cmd = [browser, f"--app={url}", "--new-window"]
    state = _load_saved_window_state()
    width = state.get('width')
    height = state.get('height')
    x = state.get('x')
    y = state.get('y')
    maximized = bool(state.get('maximized'))
    if maximized:
        cmd.append('--start-maximized')
    else:
        if width and height and width > 200 and height > 200:
            cmd.append(f"--window-size={int(width)},{int(height)}")
        if x is not None and y is not None:
            cmd.append(f"--window-position={int(x)},{int(y)}")
    print("Launching app shell:", " ".join(cmd), flush=True)
    _shell_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def open_desktop_window(port: int) -> bool:
    try:
        from window import check_pyside, run_desktop_window
        if not check_pyside():
            print("PySide desktop shell not available. Using browser mode.", flush=True)
            return False
        print("Launching PySide desktop window...", flush=True)
        code = run_desktop_window(port=port) or 0
        raise SystemExit(code)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Desktop window failed: {e}", flush=True)
        return False


def main():
    global _shell_proc, _backend_proc
    initialize_user_data()
    stop_previous_desktop_instance()
    register_desktop_instance()
    (BASE_DIR / "frontend").mkdir(exist_ok=True)
    print("MSFS Hangar starting...", flush=True)
    print(f"User data dir : {USER_DATA_DIR}", flush=True)
    print(f"Settings file : {_describe_path(SETTINGS_JSON_PATH)}", flush=True)
    print(f"Library DB    : {_describe_path(DB_PATH)}", flush=True)
    print(f"Logs folder   : {LOG_DIR if 'LOG_DIR' in globals() else USER_DATA_DIR / 'logs'}", flush=True)
    install_missing()
    port = int(os.environ.get("HANGAR_PORT", "7891"))
    bind_host = os.environ.get("HANGAR_HOST", os.environ.get("HANGAR_BIND", "127.0.0.1")).strip() or "127.0.0.1"
    use_desktop = os.environ.get("HANGAR_DESKTOP", "0") == "1"
    desktop_mode = os.environ.get("HANGAR_DESKTOP_MODE", "app").lower()
    os.environ["HANGAR_SHELL_MODE"] = desktop_mode if use_desktop else "browser"
    stop_previous_backend(port)
    clear_browser_cache()
    start_backend(bind_host, port)
    if not wait_for_server(port):
        print("Backend failed to start.", flush=True)
        print(f"Open diagnostics when available: http://127.0.0.1:{port}/api/diag", flush=True)
        print(f"Check logs in: {BASE_DIR / 'data' / 'logs'}", flush=True)
        sys.exit(1)

    if use_desktop:
        if desktop_mode == "qt":
            try:
                open_desktop_window(port)
                return
            except SystemExit:
                raise
        else:
            if not open_app_shell(port):
                open_system_browser(port)
    else:
        open_system_browser(port)

    print("Backend is running. Leave this window open while using MSFS Hangar.", flush=True)
    if bind_host not in ("127.0.0.1", "localhost"):
        lan_urls=_discover_lan_urls(port)
        if lan_urls:
            print("LAN browser access:", flush=True)
            for url in lan_urls:
                print(f"  {url}", flush=True)
            print("If another device cannot connect, allow Python/port 7891 through Windows Firewall.", flush=True)
    if use_desktop and desktop_mode == "app":
        print("Desktop shell mode: Edge/Chrome app window.", flush=True)
        print("Note: keep this console open while using the desktop shell.", flush=True)
    elif use_desktop:
        print("Desktop shell mode: Qt WebEngine.", flush=True)
    try:
        while True:
            if _backend_proc and _backend_proc.poll() is not None:
                print("Backend stopped unexpectedly.", flush=True)
                break
            if _shell_proc is not None and _shell_proc.poll() is not None:
                if use_desktop and desktop_mode == "app":
                    print("Desktop launcher process exited. Backend will stay running; close this console when finished.", flush=True)
                    _shell_proc = None
                else:
                    print("Desktop shell closed. Stopping backend.", flush=True)
                    break
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
