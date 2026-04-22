from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from logger import get_logger
from paths import BASE_DIR, USER_DATA_DIR, LOG_DIR

log = get_logger(__name__)

BUILD_TAG = '261'
API_PORT = 3080
WEB_PORT = 3300
NODE_VERSION = '22.16.0'
NODE_WIN_X64_ZIP_URL = f'https://nodejs.org/download/release/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip'

POMAX_BUNDLED_DIR = BASE_DIR / 'pomax-core'
POMAX_RUNTIME_ROOT = USER_DATA_DIR / 'virtual_pilot_pomax'
POMAX_RUNTIME_APP = POMAX_RUNTIME_ROOT / 'app'
POMAX_RUNTIME_NODE = POMAX_RUNTIME_ROOT / 'node'
POMAX_RUNTIME_CACHE = POMAX_RUNTIME_ROOT / 'npm-cache'
POMAX_DOWNLOADS = POMAX_RUNTIME_ROOT / 'downloads'
POMAX_LOG_FILE = LOG_DIR / 'pomax.log'
POMAX_BUILD_STAMP = POMAX_RUNTIME_APP / '.hangar_build'


def _port_open(port: int, host: str = '127.0.0.1') -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False


POMAX_PID_DIR = POMAX_RUNTIME_ROOT / 'pids'
API_PID_FILE = POMAX_PID_DIR / 'api.pid'
WEB_PID_FILE = POMAX_PID_DIR / 'web.pid'
SETUP_PID_FILE = POMAX_PID_DIR / 'setup.pid'

def _read_pid(pid_file: Path) -> int | None:
    try:
        if pid_file.exists():
            return int(pid_file.read_text(encoding='utf-8', errors='ignore').strip())
    except Exception:
        return None
    return None

def _write_pid(pid_file: Path, pid: int | None):
    try:
        POMAX_PID_DIR.mkdir(parents=True, exist_ok=True)
        if pid is None:
            if pid_file.exists():
                pid_file.unlink()
        else:
            pid_file.write_text(str(pid), encoding='utf-8')
    except Exception:
        pass

def _kill_pid(pid: int, force: bool = True):
    try:
        if os.name == 'nt':
            cmd = ['taskkill', '/PID', str(pid), '/T']
            if force:
                cmd.append('/F')
            subprocess.run(cmd, capture_output=True, timeout=10)
        else:
            import signal
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except Exception:
        pass

def _listening_pids(port: int) -> set[int]:
    pids: set[int] = set()
    if os.name == 'nt':
        try:
            out = subprocess.check_output(['netstat', '-ano'], text=True, errors='replace')
            for line in out.splitlines():
                if f':{port}' in line and 'LISTENING' in line.upper():
                    parts = line.split()
                    try:
                        pids.add(int(parts[-1]))
                    except Exception:
                        pass
        except Exception:
            pass
    return pids

def _port_owner_paths(pid: int) -> str:
    if os.name != 'nt':
        return ''
    try:
        out = subprocess.check_output(['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'ExecutablePath,CommandLine', '/value'], text=True, errors='replace')
        return out.lower()
    except Exception:
        return ''

def _kill_stale_pomax_ports():
    runtime_hint = str(POMAX_RUNTIME_ROOT).lower().replace('\\', '/')
    base_hint = str(BASE_DIR).lower().replace('\\', '/')
    for pid_file in (API_PID_FILE, WEB_PID_FILE, SETUP_PID_FILE):
        pid = _read_pid(pid_file)
        if pid:
            _kill_pid(pid, force=True)
        _write_pid(pid_file, None)
    for port in (API_PORT, WEB_PORT):
        for pid in list(_listening_pids(port)):
            details = _port_owner_paths(pid)
            if (runtime_hint and runtime_hint in details) or (base_hint and base_hint in details) or True:
                _kill_pid(pid, force=True)


class PomaxManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._api_proc: Optional[subprocess.Popen] = None
        self._web_proc: Optional[subprocess.Popen] = None
        self._setup_proc: Optional[subprocess.Popen] = None
        self._lines: list[str] = []
        self._mode = 'live'
        self._state = {
            'running': False,
            'starting': False,
            'ready': False,
            'message': 'Integrated Virtual Pilot idle.',
            'last_error': '',
            'web_url': f'http://127.0.0.1:{WEB_PORT}',
            'api_url': f'http://127.0.0.1:{API_PORT}',
            'node_ready': False,
            'deps_ready': False,
            'api_up': False,
            'web_up': False,
            'mode': 'live',
            'owner_mode': True,
            'auth_configured': False,
            'runtime_dir': str(POMAX_RUNTIME_APP),
            'log_tail': [],
            'updated_at': time.time(),
        }

    def _set_state(self, **kwargs):
        with self._lock:
            self._state.update(kwargs)
            self._state['updated_at'] = time.time()
            self._state['api_up'] = _port_open(API_PORT)
            self._state['web_up'] = _port_open(WEB_PORT)
            self._state['log_tail'] = self._lines[-40:]
            own_api = self._api_proc is not None and self._api_proc.poll() is None
            own_web = self._web_proc is not None and self._web_proc.poll() is None
            if own_api and own_web and self._state['api_up'] and self._state['web_up'] and not self._state.get('last_error'):
                self._state['ready'] = True
                self._state['running'] = True
                self._state['starting'] = False

    def _append_line(self, text: str):
        line = str(text).rstrip()
        if not line:
            return
        with self._lock:
            self._lines.append(line)
            if len(self._lines) > 400:
                self._lines = self._lines[-400:]
            self._state['log_tail'] = self._lines[-40:]
            self._state['updated_at'] = time.time()
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with POMAX_LOG_FILE.open('a', encoding='utf-8') as fh:
                fh.write(line + '\n')
        except Exception:
            pass

    def status(self) -> dict:
        self._set_state()
        with self._lock:
            return dict(self._state)

    def start(self, mode: str = 'live') -> dict:
        with self._lock:
            mode = 'mock' if str(mode).strip().lower() == 'mock' else 'live'
            self._mode = mode
            if self._state.get('ready') and self._api_proc and self._web_proc and self._api_proc.poll() is None and self._web_proc.poll() is None and self._state.get('mode') == mode:
                self._set_state(message='Integrated Virtual Pilot already running.', running=True, ready=True, starting=False, mode=mode)
                return dict(self._state)
            if self._thread and self._thread.is_alive():
                self._set_state(message='Integrated Virtual Pilot is already starting.', starting=True)
                return dict(self._state)
            self._state.update({'starting': True, 'running': False, 'ready': False, 'last_error': '', 'message': f'Preparing Integrated Virtual Pilot runtime ({mode})...', 'mode': mode})
            self._thread = threading.Thread(target=self._start_worker, daemon=True)
            self._thread.start()
            return dict(self._state)

    def stop(self) -> dict:
        with self._lock:
            for proc, name, pid_file in ((self._web_proc, 'web', WEB_PID_FILE), (self._api_proc, 'api', API_PID_FILE), (self._setup_proc, 'setup', SETUP_PID_FILE)):
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=6)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    self._append_line(f'[{name}] stopped')
                _write_pid(pid_file, None)
            self._web_proc = None
            self._api_proc = None
            self._setup_proc = None
        _kill_stale_pomax_ports()
        self._set_state(running=False, ready=False, starting=False, message='Integrated Virtual Pilot stopped.')
        return dict(self._state)

    def _creationflags(self) -> int:
        if os.name == 'nt':
            return getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        return 0

    def _reader(self, proc: subprocess.Popen, prefix: str):
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.decode('utf-8', errors='replace').rstrip()
                self._append_line(f'[{prefix}] {line}')
        except Exception as exc:
            self._append_line(f'[{prefix}] output reader ended: {exc}')

    def _wait_for_port(self, port: int, timeout: float = 35.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _port_open(port):
                return True
            if self._api_proc and self._api_proc.poll() is not None:
                return False
            if self._web_proc and self._web_proc.poll() is not None and port == WEB_PORT:
                return False
            time.sleep(0.4)
        return False

    def _sync_runtime_source(self):
        POMAX_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        if not POMAX_BUNDLED_DIR.exists():
            raise RuntimeError(f'Bundled Pomax core not found at {POMAX_BUNDLED_DIR}')
        runtime_needs_sync = (not POMAX_RUNTIME_APP.exists()) or (not POMAX_BUILD_STAMP.exists())
        if not runtime_needs_sync and POMAX_BUILD_STAMP.exists():
            try:
                runtime_needs_sync = POMAX_BUILD_STAMP.read_text(encoding='utf-8', errors='ignore').strip() != BUILD_TAG
            except Exception:
                runtime_needs_sync = True
        if runtime_needs_sync:
            if POMAX_RUNTIME_APP.exists():
                shutil.rmtree(POMAX_RUNTIME_APP, ignore_errors=True)
            shutil.copytree(POMAX_BUNDLED_DIR, POMAX_RUNTIME_APP, dirs_exist_ok=True)
            POMAX_BUILD_STAMP.write_text(BUILD_TAG, encoding='utf-8')
        owner_user = 'hangar'
        owner_pass = 'hangar'
        import base64
        owner_key = base64.b64encode(f'{owner_user}{owner_pass}'.encode('utf-8')).decode('ascii')

        # Optional ALOS terrain dataset auto-discovery. The Pomax code requires
        # a real unpacked JAXA ALOS tiles directory. We look for a user-provided
        # folder and wire it into .env if it exists.
        data_folder = None
        candidates = [
            USER_DATA_DIR / 'alos-data',
            USER_DATA_DIR / 'ALOS',
            USER_DATA_DIR / 'terrain' / 'alos-data',
            POMAX_RUNTIME_ROOT / 'alos-data',
            POMAX_RUNTIME_ROOT / 'ALOS',
            POMAX_RUNTIME_APP / 'alos-data',
            BASE_DIR / 'alos-data',
        ]
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_dir() and next(candidate.rglob('*.tif'), None):
                    data_folder = candidate
                    break
            except Exception:
                continue
        env_lines = [
            f'API_PORT={API_PORT}',
            f'WEB_PORT={WEB_PORT}',
            'ALOS_PORT=9000',
            f'FLIGHT_OWNER_USERNAME={owner_user}',
            f'FLIGHT_OWNER_PASSWORD={owner_pass}',
            f'FLIGHT_OWNER_KEY={owner_key}',
            'HANGAR_USE_SIM_AP=1',
        ]
        if data_folder:
            env_lines.append(f'DATA_FOLDER={data_folder.as_posix()}')
            self._append_line(f'[setup] detected ALOS terrain dataset: {data_folder}')
        else:
            self._append_line('[setup] no ALOS terrain dataset detected; terrain follow will remain unavailable until a dataset folder is configured.')
        env_path = POMAX_RUNTIME_APP / '.env'
        env_path.write_text('\n'.join(env_lines) + '\n', encoding='utf-8')
        self._set_state(auth_configured=True)
        self._append_line(f'[setup] runtime synced to {POMAX_RUNTIME_APP} (build {BUILD_TAG})')

    def _system_node(self) -> tuple[str | None, list[str] | None]:
        node = shutil.which('node.exe') or shutil.which('node')
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        if node:
            return node, ([npm] if npm else None)
        return None, None

    def _portable_node_paths(self) -> tuple[str | None, list[str] | None]:
        if not POMAX_RUNTIME_NODE.exists():
            return None, None
        node_exe = next(iter(POMAX_RUNTIME_NODE.rglob('node.exe')), None)
        npm_cmd = next(iter(POMAX_RUNTIME_NODE.rglob('npm.cmd')), None)
        if node_exe:
            if npm_cmd:
                return str(node_exe), [str(npm_cmd)]
            npm_cli = next(iter(POMAX_RUNTIME_NODE.rglob('npm-cli.js')), None)
            if npm_cli:
                return str(node_exe), [str(node_exe), str(npm_cli)]
            return str(node_exe), None
        return None, None

    def _ensure_node_runtime(self) -> tuple[str, list[str]]:
        sys_node, sys_npm = self._system_node()
        if sys_node and sys_npm:
            self._append_line(f'[setup] using system Node runtime: {sys_node}')
            self._set_state(node_ready=True)
            return sys_node, sys_npm

        if os.name != 'nt':
            raise RuntimeError('Node.js not found on PATH and portable auto-download is only enabled for Windows builds.')

        portable_node, portable_npm = self._portable_node_paths()
        if portable_node and portable_npm:
            self._append_line(f'[setup] using portable Node runtime: {portable_node}')
            self._set_state(node_ready=True)
            return portable_node, portable_npm

        POMAX_DOWNLOADS.mkdir(parents=True, exist_ok=True)
        zip_path = POMAX_DOWNLOADS / f'node-v{NODE_VERSION}-win-x64.zip'
        self._append_line(f'[setup] downloading portable Node.js {NODE_VERSION} from official archive...')
        urllib.request.urlretrieve(NODE_WIN_X64_ZIP_URL, zip_path)
        POMAX_RUNTIME_NODE.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(POMAX_RUNTIME_NODE)
        portable_node, portable_npm = self._portable_node_paths()
        if not portable_node or not portable_npm:
            raise RuntimeError('Portable Node.js download completed but node.exe/npm.cmd were not found after extraction.')
        self._append_line(f'[setup] portable Node ready: {portable_node}')
        self._set_state(node_ready=True)
        return portable_node, portable_npm

    def _ensure_dependencies(self, node_cmd: str, npm_cmd: list[str]):
        package_json = POMAX_RUNTIME_APP / 'package.json'
        current_dir = POMAX_RUNTIME_APP / 'current'
        required = [
            POMAX_RUNTIME_APP / 'node_modules' / 'socketless',
            POMAX_RUNTIME_APP / 'node_modules' / 'msfs-simconnect-api-wrapper',
            POMAX_RUNTIME_APP / 'node_modules' / 'dotenv',
        ]
        if package_json.exists() and all(p.exists() for p in required):
            self._append_line('[setup] npm dependencies already present.')
            self._set_state(deps_ready=True)
            return
        self._append_line('[setup] installing Pomax runtime dependencies with npm ci ...')
        env = os.environ.copy()
        env['npm_config_cache'] = str(POMAX_RUNTIME_CACHE)
        env['npm_config_loglevel'] = 'warn'
        env['npm_config_fund'] = 'false'
        env['npm_config_audit'] = 'false'
        cmd = list(npm_cmd) + ['ci', '--no-audit', '--no-fund']
        env['npm_config_fetch_retries'] = '2'
        env['npm_config_fetch_retry_maxtimeout'] = '20000'
        proc = subprocess.Popen(
            cmd,
            cwd=str(POMAX_RUNTIME_APP),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=self._creationflags(),
        )
        self._setup_proc = proc
        assert proc.stdout is not None
        for raw in proc.stdout:
            self._append_line('[npm] ' + raw.decode('utf-8', errors='replace').rstrip())
        code = proc.wait()
        self._setup_proc = None
        if code != 0:
            raise RuntimeError(f'npm ci failed with exit code {code}.')
        if not current_dir.exists():
            raise RuntimeError('Pomax runtime current/ folder missing after dependency install.')
        self._append_line('[setup] npm dependencies installed successfully.')
        self._set_state(deps_ready=True)

    def _start_servers(self, node_cmd: str):
        env = os.environ.copy()
        env['API_PORT'] = str(API_PORT)
        env['WEB_PORT'] = str(WEB_PORT)
        env['FLIGHT_OWNER_USERNAME'] = 'hangar'
        env['FLIGHT_OWNER_PASSWORD'] = 'hangar'
        env['FLIGHT_OWNER_KEY'] = 'aGFuZ2FyaGFuZ2Fy'
        env['HANGAR_USE_SIM_AP'] = '1'
        current_dir = POMAX_RUNTIME_APP / 'current'
        if not current_dir.exists():
            raise RuntimeError(f'Pomax current/ runtime folder missing at {current_dir}')
        api_cmd = [node_cmd, '--env-file=../.env', 'api-server.js']
        if self._mode == 'mock':
            api_cmd.append('--mock')
        web_cmd = [node_cmd, '--env-file=../.env', 'web-server.js', '--owner']
        self._append_line(f'[api] starting integrated API server ({self._mode})...')
        self._api_proc = subprocess.Popen(
            api_cmd,
            cwd=str(current_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=self._creationflags(),
)
        _write_pid(API_PID_FILE, self._api_proc.pid)
        threading.Thread(target=self._reader, args=(self._api_proc, 'api'), daemon=True).start()
        if not self._wait_for_port(API_PORT, timeout=25):
            raise RuntimeError('Pomax API server did not come up on port 3080.')
        self._append_line('[web] starting integrated web client server...')
        self._web_proc = subprocess.Popen(
            web_cmd,
            cwd=str(current_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=self._creationflags(),
)
        _write_pid(WEB_PID_FILE, self._web_proc.pid)
        threading.Thread(target=self._reader, args=(self._web_proc, 'web'), daemon=True).start()
        if not self._wait_for_port(WEB_PORT, timeout=25):
            raise RuntimeError('Pomax web client did not come up on port 3300.')
        self._append_line(f'[setup] integrated Virtual Pilot is ready in {self._mode} mode.')
        self._set_state(running=True, ready=True, starting=False, message=f'Integrated Virtual Pilot running ({self._mode}).', mode=self._mode)

    def _start_worker(self):
        try:
            self._append_line('[setup] cleaning up any stale Virtual Pilot servers from previous sessions...')
            _kill_stale_pomax_ports()
            self.stop()
            self._set_state(starting=True, running=False, ready=False, message=f'Preparing integrated Virtual Pilot runtime ({self._mode})...', last_error='', mode=self._mode)
            self._sync_runtime_source()
            node_cmd, npm_cmd = self._ensure_node_runtime()
            if not npm_cmd:
                raise RuntimeError('npm was not found next to the resolved Node runtime.')
            self._ensure_dependencies(node_cmd, npm_cmd)
            self._start_servers(node_cmd)
        except Exception as exc:
            self._append_line(f'[error] {exc}')
            log.exception('Integrated Virtual Pilot startup failed: %s', exc)
            self.stop()
            self._set_state(starting=False, running=False, ready=False, last_error=str(exc), message='Integrated Virtual Pilot startup failed.')


_manager = PomaxManager()


def start_pomax(mode: str = 'live') -> dict:
    return _manager.start(mode=mode)


def stop_pomax() -> dict:
    return _manager.stop()


def get_pomax_status() -> dict:
    return _manager.status()
