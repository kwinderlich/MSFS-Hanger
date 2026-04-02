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
from paths import initialize_user_data, PID_FILE, CACHE_ROOT, USER_DATA_DIR, SETTINGS_JSON_PATH, DB_PATH
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
    for name in CACHE_DIRS:
        target = CACHE_ROOT / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


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


def start_backend(port: int):
    global _backend_proc
    cmd = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"]
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


def open_system_browser(port: int):
    import webbrowser
    url = f"http://127.0.0.1:{port}"
    print(f"Opening system browser at {url}", flush=True)
    webbrowser.open(url)


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
    url = f"http://127.0.0.1:{port}"
    cmd = [browser, f"--app={url}", "--new-window"]
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
    (BASE_DIR / "frontend").mkdir(exist_ok=True)
    print("MSFS Hangar starting...", flush=True)
    print(f"User data dir: {USER_DATA_DIR}", flush=True)
    print(f"Settings file : {SETTINGS_JSON_PATH}", flush=True)
    print(f"Library DB    : {DB_PATH}", flush=True)
    install_missing()
    port = int(os.environ.get("HANGAR_PORT", "7891"))
    use_desktop = os.environ.get("HANGAR_DESKTOP", "0") == "1"
    desktop_mode = os.environ.get("HANGAR_DESKTOP_MODE", "app").lower()
    os.environ["HANGAR_SHELL_MODE"] = desktop_mode if use_desktop else "browser"
    stop_previous_backend(port)
    clear_browser_cache()
    start_backend(port)
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
