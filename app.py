from __future__ import annotations

import asyncio
import copy
import base64
import configparser
import json
import logging
import mimetypes
import base64
import os
import shlex
import hashlib
import subprocess
from datetime import datetime
import re
import shutil
import time
import uuid
import sys
import unicodedata
import math
import textwrap
import xml.etree.ElementTree as ET
from html import escape, unescape
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse, parse_qs, urljoin

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import SUBTYPE_MAP, Addon
import linker
import scanner as scan_module
import storage
from realworld import fetch_aircraft_specs, guess_icao
from logger import build_diag_report, get_logger, write_startup_snapshot, setup_logging
from paths import BASE_DIR, USER_DATA_DIR, initialize_user_data, SETTINGS_JSON_PATH, DB_PATH, LOG_DIR, BROWSER_PROFILE_DIR, BACKUP_DIR, TEST_DIR, LEGACY_HYBRID_DIR, LEGACY_HQ_DIR, LEGACY_QT_DIR, BOOTSTRAP_CONFIG_PATH, get_forced_storage_root, save_bootstrap_config, load_bootstrap_config, storage_mode, get_library_profiles, get_active_profile, get_active_profile_id
from native_dialogs import pick_or_create_folder
from flight_tracker import FlightTracker
from virtual_pilot import get_virtual_pilot_config
from pomax_service import start_pomax, stop_pomax, get_pomax_status

log = get_logger(__name__)

SIMCONNECT_ENDPOINT_LOG = logging.getLogger('simconnect')

def _simconnect_endpoint_log(level: str, message: str, *args):
    logger = SIMCONNECT_ENDPOINT_LOG
    try:
        getattr(logger, level.lower())(message, *args)
    finally:
        for h in list(getattr(logger, 'handlers', []) or []):
            try:
                h.flush()
            except Exception:
                pass


app = FastAPI(title="MSFS Hangar", version="2.0.138")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get('/api/map-tile/{provider}/{z}/{x}/{y}.png')
async def proxy_map_tile(provider: str, z: int, x: int, y: int):
    provider_key = str(provider or '').strip().lower()
    if provider_key == 'osm':
        url = f'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
        headers = {'User-Agent': 'MSFS-Hangar/225 (+local-proxy)'}
    elif provider_key in {'esri', 'arcgis'}:
        url = f'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        headers = {'User-Agent': 'MSFS-Hangar/225 (+local-proxy)'}
    else:
        raise HTTPException(status_code=404, detail='Unknown map tile provider')
    try:
        resp = requests.get(url, timeout=20, headers=headers)
        resp.raise_for_status()
        return Response(content=resp.content, media_type='image/png', headers={'Cache-Control': 'public, max-age=3600'})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
initialize_user_data()
setup_logging()
VP_ROUTE_DIR = USER_DATA_DIR / 'vp_routes'
VP_ROUTE_DIR.mkdir(parents=True, exist_ok=True)

def _slugify_route_name(value: str) -> str:
    raw = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii')
    raw = re.sub(r'[\\/:*?"<>|]+', ' ', raw)
    raw = re.sub(r'\s+', ' ', raw).strip(' .')
    if not raw:
        raw = f'route-{int(time.time())}'
    return raw

def _friendly_route_file_name(name: str) -> str:
    base_name = _slugify_route_name(name)
    if not base_name.lower().endswith('.json'):
        base_name += '.json'
    return base_name

def _normalize_route_points(points) -> list[dict]:
    out = []
    for pt in list(points or []):
        try:
            lat = float(pt.get('lat'))
            lon_val = pt.get('lon', pt.get('long'))
            lon = float(lon_val)
            item = {'lat': lat, 'long': lon}
            alt_val = pt.get('alt')
            if alt_val not in (None, ''):
                try:
                    item['alt'] = float(alt_val)
                except Exception:
                    pass
            out.append(item)
        except Exception:
            continue
    return out

def _vp_route_file_path(name: str = '', file_name: str = '') -> Path:
    chosen = str(file_name or '').strip() or _friendly_route_file_name(name)
    chosen = Path(chosen).name
    if not chosen.lower().endswith('.json'):
        chosen += '.json'
    return VP_ROUTE_DIR / chosen

def _write_vp_route_file(name: str, points, file_name: str = '') -> dict:
    pts = _normalize_route_points(points)
    if len(pts) < 2:
        raise ValueError('At least two valid waypoints are required.')
    path = _vp_route_file_path(name=name, file_name=file_name)
    payload = {'name': str(name or path.stem), 'saved_at': datetime.utcnow().isoformat() + 'Z', 'points': pts}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return {'file_name': path.name, 'path': str(path), 'count': len(pts), 'points': pts, 'name': payload['name']}

def _read_vp_route_file(name: str = '', file_name: str = '') -> dict:
    path = _vp_route_file_path(name=name, file_name=file_name)
    if not path.exists():
        raise FileNotFoundError(f'Route file not found: {path.name}')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(raw, list):
        payload = {'name': path.stem, 'points': raw}
    else:
        payload = {'name': raw.get('name') or path.stem, 'points': raw.get('points') or []}
    pts = _normalize_route_points(payload.get('points'))
    if len(pts) < 2:
        raise ValueError('Route file does not contain at least two valid waypoints.')
    return {'file_name': path.name, 'path': str(path), 'name': payload['name'], 'count': len(pts), 'points': pts}

def _build_pomax_load_script(points: list[dict], plan_name: str) -> str:
    payload = json.dumps(points, ensure_ascii=False)
    plan_name_js = json.dumps(str(plan_name or 'Hangar Route'))
    script = textwrap.dedent("""
        (function() {
          const plan = __PAYLOAD__;
          const planName = __PLAN_NAME__;
          const loadPlan = () => {
            try {
              const browserClient = globalThis.browserClient;
              const plane = browserClient?.plane || globalThis.plane;
              const server = browserClient?.server || globalThis.server || plane?.server;
              if (!server?.autopilot?.setFlightPlan) return false;
              server.autopilot.setFlightPlan(plan);
              const flightData = plane?.state?.flightInformation?.data || {};
              if (!flightData.onGround && Number.isFinite(Number(flightData.lat)) && Number.isFinite(Number(flightData.long)) && typeof server.autopilot.revalidate === 'function') {
                server.autopilot.revalidate(Number(flightData.lat), Number(flightData.long));
              }
              try { globalThis.__hangarLoadedRouteName = planName; } catch (e) {}
              try { window.dispatchEvent(new CustomEvent('hangar-route-loaded', { detail: { name: planName, count: plan.length } })); } catch (e) {}
              try { if (plane?.requestZoomToRoute) plane.requestZoomToRoute(); } catch (e) { console.warn('Hangar zoom-to-route request failed', e); }
              return true;
            } catch (e) {
              console.error('Hangar route bridge failed', e);
              return false;
            }
          };
          if (loadPlan()) return 'ok';
          let tries = 0;
          const timer = setInterval(() => {
            tries += 1;
            if (loadPlan() || tries > 40) clearInterval(timer);
          }, 500);
          return 'queued';
        })();
    """)

    return script.replace('__PAYLOAD__', payload).replace('__PLAN_NAME__', plan_name_js)


def _build_pomax_command_script(command: str) -> str:
    cmd = str(command or '').strip().lower()
    command_json = json.dumps(cmd)
    script = textwrap.dedent("""
        (function(){
          const command = __COMMAND__;
          const server = globalThis.browserClient?.server || globalThis.server || globalThis.browserClient?.plane?.server;
          const plane = globalThis.browserClient?.plane || globalThis.plane;
          if (!server) return {ok:false,error:'server_unavailable'};
          const trigger = (name, value) => server?.api?.trigger ? server.api.trigger(name, value) : false;
          if (command === 'pause_on') {
            trigger('PAUSE_ON', 0);
            if (plane?.updatePauseButton) plane.updatePauseButton(true);
            return {ok:true};
          }
          if (command === 'pause_off') {
            trigger('PAUSE_OFF', 0);
            if (plane?.updatePauseButton) plane.updatePauseButton(false);
            return {ok:true};
          }
          return {ok:false,error:'unknown_command'};
        })();
    """)
    return script.replace('__COMMAND__', command_json)


def _bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dlon = math.radians(float(lon2) - float(lon1))
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def _build_pomax_slew_script(points: list[dict], pause_after: bool = True) -> str:
    pts = _normalize_route_points(points)
    if not pts:
        raise ValueError('At least one valid waypoint is required for slew.')
    wp1 = dict(pts[0])
    if len(pts) > 1:
        try:
            wp1['heading'] = round(_bearing_degrees(wp1['lat'], wp1['long'], pts[1]['lat'], pts[1]['long']), 1)
        except Exception:
            pass
    payload = json.dumps(wp1, ensure_ascii=False)
    pause_json = 'true' if pause_after else 'false'
    script = textwrap.dedent("""
        (async function(){
          const waypoint = __WAYPOINT__;
          const pauseAfter = __PAUSE_AFTER__;
          const getServer = () => globalThis.browserClient?.server || globalThis.server || globalThis.browserClient?.plane?.server;
          const plane = globalThis.browserClient?.plane || globalThis.plane;
          const apiBase = globalThis.__hangarApiBase || 'http://127.0.0.1:7891';
          const toRad = (v) => Number(v) * Math.PI / 180;
          const tryRun = async () => {
            const server = getServer();
            if (!server?.api?.set || !server?.api?.trigger) return false;
            const api = server.api;
            const lat = Number(waypoint.lat);
            const lon = Number(waypoint.long);
            const heading = Number(waypoint.heading);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
            try { await api.trigger('SLEW_ON', 0); } catch (e) { console.warn('SLEW_ON failed', e); }
            await new Promise(r => setTimeout(r, 180));
            try {
              await api.set({
                PLANE_LATITUDE: toRad(lat),
                PLANE_LONGITUDE: toRad(lon),
                ...(Number.isFinite(Number(waypoint.alt)) && Number(waypoint.alt) > 0 ? { INDICATED_ALTITUDE: Number(waypoint.alt) } : {}),
                ...(Number.isFinite(heading) ? { PLANE_HEADING_DEGREES_TRUE: toRad(heading), AUTOPILOT_HEADING_LOCK_DIR: heading } : {})
              });
            } catch (e) { console.error('Hangar slew position set failed', e); }
            await new Promise(r => setTimeout(r, 350));
            try { await api.trigger('SLEW_OFF', 0); } catch (e) { console.warn('SLEW_OFF failed', e); }
            await new Promise(r => setTimeout(r, 220));
            if (pauseAfter) {
              try {
                await fetch(`${apiBase}/api/pomax/command`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ command: 'pause_on' })
                });
                if (plane?.updatePauseButton) plane.updatePauseButton(true);
              } catch (e) { console.warn('Pause after slew failed', e); }
            }
            return true;
          };
          if (await tryRun()) return 'queued';
          let tries = 0;
          const timer = setInterval(async () => {
            tries += 1;
            if (await tryRun() || tries > 20) clearInterval(timer);
          }, 500);
          return 'waiting';
        })();
    """)
    return script.replace('__WAYPOINT__', payload).replace('__PAUSE_AFTER__', pause_json)

DATA_DIR = USER_DATA_DIR
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")
ASSETS_DIR = FRONTEND_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

_scan_cancel: Optional[asyncio.Event] = None
_scan_running = False
_enrich_running = False
_enrich_progress = {"running": False, "pct": 0, "current": "", "done": 0, "total": 0, "message": "", "type": "idle"}
_subtype_enrich_running = False
_subtype_enrich_progress = {"running": False, "pct": 0, "current": "", "done": 0, "total": 0, "message": "", "type": "idle"}

_browser_state = {
    'requested_url': '',
    'requested_title': '',
    'request_id': 0,
    'current_url': '',
    'current_title': '',
    'visible': False,
    'minimal_controls': False,
    'panel_kind': '',
    'requested_script': '',
    'script_id': 0,
    'updated_at': 0.0,
}

_search_cache: dict[tuple[str, str], dict] = {}
_SEARCH_CACHE_VERSION = 'v1'
_SEARCH_CACHE_TTL = 900
_flight_tracker = FlightTracker()
SCAN_LOG_FILE = LOG_DIR / 'scan.log'
AI_LOG_FILE = LOG_DIR / 'ai.log'

def _append_text_log_lines(path: Path, lines: list[str]):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as fh:
            for line in (lines or []):
                fh.write(str(line).rstrip() + '\n')
    except Exception as e:
        log.warning('Could not append text log %s: %s', path, e)

def _append_scan_log_lines(lines: list[str]):
    _append_text_log_lines(SCAN_LOG_FILE, lines)

def _append_ai_log_lines(lines: list[str]):
    _append_text_log_lines(AI_LOG_FILE, lines)

def _update_browser_state(**kwargs):
    _browser_state.update({k: v for k, v in kwargs.items() if v is not None})
    _browser_state['updated_at'] = time.time()


@app.on_event("startup")
async def startup():
    initialize_user_data()
    try:
        stop_pomax()
    except Exception:
        pass
    await storage.init_db()
    settings = await storage.get_all_settings()
    flight_cfg = await storage.get_json_setting('flight_tracker_settings', {'poll_interval': 1.0})
    try:
        _flight_tracker.configure(poll_interval=float((flight_cfg or {}).get('poll_interval', 1.0) or 1.0))
    except Exception:
        pass
    write_startup_snapshot(settings)
    settings_info = _file_info(SETTINGS_JSON_PATH)
    db_info = _file_info(DB_PATH)
    log.info("Using external data dir: %s", USER_DATA_DIR)
    log.info("Settings file: %s | exists=%s | size=%s | modified=%s", settings_info["path"], settings_info["exists"], settings_info["size"], settings_info["modified"] or "")
    log.info("Library DB: %s | exists=%s | size=%s | modified=%s", db_info["path"], db_info["exists"], db_info["size"], db_info["modified"] or "")


@app.on_event("shutdown")
async def shutdown():
    try:
        stop_pomax()
    except Exception:
        pass


def _file_info(path: Path) -> dict:
    exists = path.exists()
    return {
        'path': str(path),
        'exists': exists,
        'size': (path.stat().st_size if exists and path.is_file() else 0),
        'modified': (datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds') if exists else ''),
    }


def _dir_listing(path: Path) -> list[dict]:
    items = []
    try:
        if path.exists():
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                items.append({
                    'name': child.name,
                    'path': str(child),
                    'type': 'dir' if child.is_dir() else 'file',
                    'size': (child.stat().st_size if child.is_file() else 0),
                    'modified': datetime.fromtimestamp(child.stat().st_mtime).isoformat(timespec='seconds'),
                })
    except Exception:
        pass
    return items


def _search_live_datastore() -> dict:
    base = USER_DATA_DIR
    targets = {
        'hangar.db': base / 'hangar.db',
        'storage_test_marker.json': TEST_DIR / 'storage_test_marker.json',
        'settings.json': SETTINGS_JSON_PATH,
    }
    found = {name: _file_info(path) for name, path in targets.items()}
    legacy = []
    for path in base.glob('*.json'):
        if path.name not in {'settings.json'}:
            legacy.append(_file_info(path))
    return {'targets': found, 'legacy_json': legacy}


def _open_in_explorer(path_value: str) -> bool:
    path = Path(path_value)
    target = path if path.exists() else path.parent
    if not target:
        return False
    try:
        if os.name == 'nt':
            os.startfile(str(target))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(target)])
        else:
            subprocess.Popen(['xdg-open', str(target)])
        return True
    except Exception:
        return False


def _native_pick_folder(initial_dir: str = '', title: str = 'Choose MSFS Hangar App Folder') -> str:
    return pick_or_create_folder(initial_dir or str(USER_DATA_DIR), title)


def _native_pick_save_path(initial_dir: str = '', initial_file: str = '') -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.asksaveasfilename(
            initialdir=initial_dir or str(BACKUP_DIR),
            initialfile=initial_file or f"MSFSHangar Backup {datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            title='Save MSFSHangar Backup',
            defaultextension='.zip',
            filetypes=[('Zip files', '*.zip')],
        )
        root.destroy()
        return selected or ''
    except Exception:
        return ''


class ApplicationFolderUpdate(BaseModel):
    path: str
    copy_current_data: bool = True
    verify_copy: bool = True
    remove_old_after_copy: bool = False


class BackupTargetRequest(BaseModel):
    path: Optional[str] = None


class LibraryProfileCreateRequest(BaseModel):
    name: str
    platform: str = 'msfs2024'
    storage_root: str
    copy_current_data: bool = False
    switch_to: bool = False


class LibraryProfileSwitchRequest(BaseModel):
    profile_id: str


class WindowStateUpdate(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    maximized: bool = False
    shell_mode: str = ''
    saved_at: str = ''


@app.get("/api/application/info")
async def application_info():
    sources = await storage.detect_storage_sources()
    override = get_forced_storage_root()
    active_profile = get_active_profile() or {}
    profiles = get_library_profiles()
    return {
        "base_dir": str(BASE_DIR),
        "base_app_folder": str(USER_DATA_DIR),
        "user_data_dir": str(USER_DATA_DIR),
        "settings_file": str(SETTINGS_JSON_PATH),
        "db_path": str(DB_PATH),
        "log_dir": str(LOG_DIR),
        "browser_profile_dir": str(BROWSER_PROFILE_DIR),
        "backup_dir": str(BACKUP_DIR),
        "test_dir": str(TEST_DIR),
        "storage_mode": storage_mode(),
        "forced_storage_root": override,
        "pending_delete_root": str(load_bootstrap_config().get('pending_delete_root') or ''),
        "bootstrap_config": str(BOOTSTRAP_CONFIG_PATH),
        "bootstrap_exists": BOOTSTRAP_CONFIG_PATH.exists(),
        "host_mode": os.environ.get('HANGAR_SHELL_MODE', 'local_or_desktop'),
        "shell_mode": os.environ.get('HANGAR_SHELL_MODE', 'local_or_desktop'),
        "user_data_exists": USER_DATA_DIR.exists(),
        "settings_exists": SETTINGS_JSON_PATH.exists(),
        "db_exists": DB_PATH.exists(),
        "log_dir_exists": LOG_DIR.exists(),
        "browser_profile_exists": BROWSER_PROFILE_DIR.exists(),
        "settings_file_info": _file_info(SETTINGS_JSON_PATH),
        "db_file_info": _file_info(DB_PATH),
        "backup_dir_exists": BACKUP_DIR.exists(),
        "test_dir_exists": TEST_DIR.exists(),
        "storage_sources": sources,
        "active_data_listing": _dir_listing(USER_DATA_DIR),
        "live_datastore_search": _search_live_datastore(),
        "library_profiles": profiles,
        "active_profile_id": get_active_profile_id(),
        "active_profile": active_profile,
        "window_state": await storage.get_json_setting('window_state', {}),
    }


@app.get('/api/application/window-state')
async def application_window_state():
    return await storage.get_json_setting('window_state', {})


@app.post('/api/application/window-state')
async def application_save_window_state(body: WindowStateUpdate):
    payload = body.model_dump()
    payload['saved_at'] = payload.get('saved_at') or datetime.utcnow().isoformat() + 'Z'
    try:
        await storage.set_json_setting('window_state', payload)
        return {'ok': True, 'window_state': payload}
    except Exception as exc:
        if 'locked' in str(exc).lower():
            return {'ok': False, 'warning': 'window_state_database_locked', 'window_state': payload}
        raise


@app.post('/api/frontend-log')
async def frontend_log(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}
    level = str(body.get('level') or 'info').lower().strip()
    msg = str(body.get('message') or '').strip() or 'frontend-log'
    ctx = body.get('context') or {}
    logger = get_logger('frontend')
    line = f"FRONTEND {level.upper()} — {msg} | {ctx}"
    print(line, flush=True)
    if level in {'error','exception','fatal'}:
        logger.error('%s | %s', msg, ctx)
    elif level in {'warning','warn'}:
        logger.warning('%s | %s', msg, ctx)
    else:
        logger.info('%s | %s', msg, ctx)
    category = str(ctx.get('category') or '').strip().lower()
    if category in {'library','scan','flight'}:
        try:
            await storage.add_event_log({
                'id': uuid.uuid4().hex,
                'category': category,
                'action': str(ctx.get('action') or msg)[:120],
                'started_at': datetime.now().isoformat(timespec='seconds'),
                'ended_at': datetime.now().isoformat(timespec='seconds'),
                'duration_seconds': 0.0,
                'screen': str(ctx.get('screen') or category)[:80],
                'status': 'error' if level in {'error','exception','fatal'} else ('warning' if level in {'warning','warn'} else 'success'),
                'addon_id': str(ctx.get('addon_id') or ''),
                'addon_title': str(ctx.get('addon_title') or ''),
                'details': ctx,
                'summary': ctx.get('summary') if isinstance(ctx.get('summary'), dict) else {},
                'error_message': msg if level in {'error','exception','fatal'} else '',
            })
        except Exception as exc:
            logger.warning('Could not persist frontend event log: %s', exc)
    return {'ok': True}

@app.get('/api/library-profiles')
async def application_library_profiles():
    return {'profiles': get_library_profiles(), 'active_profile_id': get_active_profile_id(), 'active_profile': get_active_profile() or {}}


@app.post('/api/library-profiles')
async def application_create_library_profile(body: LibraryProfileCreateRequest):
    name = (body.name or '').strip()
    if not name:
        raise HTTPException(400, 'A profile name is required')
    storage_root = str(Path((body.storage_root or '').strip()).expanduser())
    if not storage_root:
        raise HTTPException(400, 'A storage folder is required')
    target = Path(storage_root)
    target.mkdir(parents=True, exist_ok=True)
    cfg = load_bootstrap_config()
    profiles = get_library_profiles()
    if any((p.get('name') or '').strip().lower() == name.lower() for p in profiles):
        raise HTTPException(400, 'A library profile with that name already exists')
    profile_id = uuid.uuid4().hex[:10]
    profile = {
        'id': profile_id,
        'name': name,
        'platform': (body.platform or 'msfs2024').strip() or 'msfs2024',
        'storage_root': str(target),
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }
    if body.copy_current_data and target.resolve() != USER_DATA_DIR.resolve():
        for child in USER_DATA_DIR.iterdir():
            dest = target / child.name
            if child.name.lower() == 'backend.pid':
                continue
            try:
                if child.is_dir():
                    shutil.copytree(child, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, dest)
            except Exception:
                continue
    profiles.append(profile)
    cfg['library_profiles'] = profiles
    if body.switch_to:
        cfg['active_profile_id'] = profile_id
        cfg['forced_storage_root'] = str(target)
    save_bootstrap_config(cfg)
    return {'ok': True, 'profile': profile, 'restart_required': bool(body.switch_to), 'active_profile_id': cfg.get('active_profile_id')}


@app.post('/api/library-profiles/switch')
async def application_switch_library_profile(body: LibraryProfileSwitchRequest):
    profile_id = (body.profile_id or '').strip()
    cfg = load_bootstrap_config()
    profiles = get_library_profiles()
    profile = next((p for p in profiles if p.get('id') == profile_id), None)
    if not profile:
        raise HTTPException(404, 'Library profile not found')
    cfg['library_profiles'] = profiles
    cfg['active_profile_id'] = profile_id
    cfg['forced_storage_root'] = str(profile.get('storage_root') or '')
    save_bootstrap_config(cfg)
    return {'ok': True, 'profile': profile, 'restart_required': True}


@app.post('/api/application/test-storage')
async def application_test_storage():
    return await storage.run_storage_test()


@app.post('/api/application/backup')
async def application_backup():
    return await storage.create_data_backup()


@app.post('/api/application/backup-choose')
async def application_backup_choose():
    target = _native_pick_save_path(str(BACKUP_DIR), '')
    if not target:
        raise HTTPException(400, 'No backup destination selected')
    return await storage.create_data_backup(destination=Path(target))


@app.post('/api/application/pick-app-folder')
async def application_pick_app_folder():
    chosen = _native_pick_folder(str(USER_DATA_DIR))
    if not chosen:
        raise HTTPException(400, 'No folder selected')
    return {'path': chosen}


@app.post('/api/application/reveal-active-folder')
async def application_reveal_active_folder():
    if not _open_in_explorer(str(USER_DATA_DIR)):
        raise HTTPException(500, 'Could not open the active app folder')
    return {'ok': True, 'path': str(USER_DATA_DIR)}


def _copy_tree_with_report(source: Path, target: Path) -> tuple[list[str], list[dict]]:
    copied = []
    errors = []
    if not source.exists():
        return copied, errors
    for child in source.iterdir():
        dest = target / child.name
        try:
            if child.is_dir():
                shutil.copytree(child, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, dest)
            copied.append(child.name)
        except Exception as exc:
            errors.append({'item': child.name, 'error': str(exc)})
    return copied, errors


def _verify_copied_items(source: Path, target: Path) -> dict:
    report = {'ok': True, 'checked': [], 'missing': [], 'mismatched': [], 'source_exists': source.exists(), 'target_exists': target.exists()}
    if not source.exists() or not target.exists():
        report['ok'] = False
        return report
    for child in source.iterdir():
        src = child
        dst = target / child.name
        entry = {'item': child.name, 'type': 'dir' if child.is_dir() else 'file'}
        if not dst.exists():
            report['missing'].append({'item': child.name, 'path': str(dst)})
            report['ok'] = False
            continue
        if child.is_file():
            try:
                src_stat = child.stat()
                dst_stat = dst.stat()
                entry.update({'size': src_stat.st_size, 'dest_size': dst_stat.st_size})
                if src_stat.st_size != dst_stat.st_size:
                    report['mismatched'].append({'item': child.name, 'reason': 'size', 'source_size': src_stat.st_size, 'dest_size': dst_stat.st_size})
                    report['ok'] = False
                else:
                    try:
                        with child.open('rb') as s, dst.open('rb') as d:
                            if s.read(4096) != d.read(4096):
                                report['mismatched'].append({'item': child.name, 'reason': 'content_prefix'})
                                report['ok'] = False
                    except Exception as exc:
                        report['mismatched'].append({'item': child.name, 'reason': f'readback: {exc}'})
                        report['ok'] = False
            except Exception as exc:
                report['mismatched'].append({'item': child.name, 'reason': str(exc)})
                report['ok'] = False
        else:
            src_files = [f for f in child.rglob('*') if f.is_file()]
            dst_files = [f for f in dst.rglob('*') if f.is_file()]
            entry.update({'source_files': len(src_files), 'dest_files': len(dst_files)})
            if len(src_files) != len(dst_files):
                report['mismatched'].append({'item': child.name, 'reason': 'file_count', 'source_files': len(src_files), 'dest_files': len(dst_files)})
                report['ok'] = False
            else:
                for src_file in src_files:
                    rel = src_file.relative_to(child)
                    dst_file = dst / rel
                    if not dst_file.exists():
                        report['missing'].append({'item': child.name, 'path': str(dst_file)})
                        report['ok'] = False
                        continue
                    try:
                        src_stat = src_file.stat()
                        dst_stat = dst_file.stat()
                        if src_stat.st_size != dst_stat.st_size:
                            report['mismatched'].append({'item': child.name, 'path': str(rel), 'reason': 'size', 'source_size': src_stat.st_size, 'dest_size': dst_stat.st_size})
                            report['ok'] = False
                            break
                    except Exception as exc:
                        report['mismatched'].append({'item': child.name, 'path': str(rel), 'reason': str(exc)})
                        report['ok'] = False
                        break
        report['checked'].append(entry)
    return report


def _build_move_verification(target: Path) -> dict:
    settings_info = {'path': str(target / 'settings.json'), 'exists': (target / 'settings.json').exists()}
    if settings_info['exists']:
        try:
            raw = json.loads((target / 'settings.json').read_text(encoding='utf-8') or '{}')
            settings_info['readable'] = isinstance(raw, dict)
            settings_info['keys'] = len(raw) if isinstance(raw, dict) else 0
        except Exception as exc:
            settings_info['readable'] = False
            settings_info['error'] = str(exc)
    db_info = {'path': str(target / 'hangar.db'), 'exists': (target / 'hangar.db').exists()}
    if db_info['exists']:
        try:
            import sqlite3
            conn = sqlite3.connect(str(target / 'hangar.db'))
            try:
                cur = conn.execute("select name from sqlite_master where type='table'")
                tables = sorted(r[0] for r in cur.fetchall())
                db_info['readable'] = True
                db_info['tables'] = tables
            finally:
                conn.close()
        except Exception as exc:
            db_info['readable'] = False
            db_info['error'] = str(exc)
    marker_info = {'path': str(target / 'tests' / 'storage_test_marker.json'), 'exists': (target / 'tests' / 'storage_test_marker.json').exists()}
    if marker_info['exists']:
        try:
            marker_info['readable'] = isinstance(json.loads((target / 'tests' / 'storage_test_marker.json').read_text(encoding='utf-8')), dict)
        except Exception as exc:
            marker_info['readable'] = False
            marker_info['error'] = str(exc)
    ok = settings_info['exists'] == False or settings_info.get('readable', False)
    ok = ok and (db_info['exists'] == False or db_info.get('readable', False))
    ok = ok and (marker_info['exists'] == False or marker_info.get('readable', False))
    return {'ok': ok, 'settings': settings_info, 'database': db_info, 'storage_marker': marker_info}


@app.post('/api/application/set-app-folder')
async def application_set_app_folder(body: ApplicationFolderUpdate):
    target = Path((body.path or '').strip()).expanduser()
    if not str(target).strip():
        raise HTTPException(400, 'A target folder is required')
    if not target.is_absolute():
        raise HTTPException(400, 'Please choose an absolute folder path')
    current_root = USER_DATA_DIR.resolve()
    target.mkdir(parents=True, exist_ok=True)
    same_target = target.resolve() == current_root
    copied: list[str] = []
    copy_errors: list[dict] = []
    verification = {'ok': True, 'skipped': True, 'reason': 'copy not requested or target already active'}
    old_folder_removed = False
    old_folder_remove_error = None
    old_folder_removal_deferred = False
    if body.copy_current_data and not same_target:
        copied, copy_errors = _copy_tree_with_report(current_root, target)
        if copy_errors:
            raise HTTPException(500, {'message': 'Copy to the new app-data folder failed.', 'copied_items': copied, 'copy_errors': copy_errors})
        verification = _verify_copied_items(current_root, target) if body.verify_copy else {'ok': True, 'skipped': True, 'reason': 'verification disabled'}
        move_check = _build_move_verification(target)
        verification['move_check'] = move_check
        if not verification.get('ok') or not move_check.get('ok'):
            raise HTTPException(500, {'message': 'The new app-data folder could not be verified after copy.', 'copied_items': copied, 'verification': verification})
        if body.remove_old_after_copy:
            old_folder_removal_deferred = True
    cfg = load_bootstrap_config()
    profiles = get_library_profiles()
    active_id = get_active_profile_id()
    updated = False
    for profile in profiles:
        if profile.get('id') == active_id:
            profile['storage_root'] = str(target)
            profile['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            updated = True
            break
    if not updated and not profiles:
        profiles = [{
            'id': 'default-msfs2024',
            'name': 'MSFS 2024',
            'platform': 'msfs2024',
            'storage_root': str(target),
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
        }]
        cfg['active_profile_id'] = 'default-msfs2024'
    cfg['library_profiles'] = profiles
    cfg['forced_storage_root'] = str(target)
    if old_folder_removal_deferred and not same_target:
        cfg['pending_delete_root'] = str(current_root)
    save_bootstrap_config(cfg)
    return {
        'ok': True,
        'forced_storage_root': str(target),
        'copied_items': copied,
        'verification': verification,
        'old_folder_removed': old_folder_removed,
        'old_folder_removal_deferred': old_folder_removal_deferred,
        'old_folder_remove_error': old_folder_remove_error,
        'restart_required': True,
        'active_profile_id': cfg.get('active_profile_id'),
    }


@app.post('/api/application/migrate-legacy')
async def application_migrate_legacy():
    return await storage.migrate_legacy_storage()

@app.get("/api/diag")
async def diagnostics():
    addons = await storage.get_all_addons()
    settings = await storage.get_all_settings()
    report = build_diag_report(extra={
        "addon_count": len(addons),
        "settings": {k: ("***" if "key" in k.lower() else v) for k, v in settings.items()},
        "scan_running": _scan_running,
    })
    return HTMLResponse(f"<html><body><pre>{escape(json.dumps(report, indent=2))}</pre></body></html>")

@app.get("/thumb/{addon_id}")
async def thumb(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404, "No thumbnail")
    path = None
    if addon.thumbnail_path and Path(addon.thumbnail_path).exists():
        path = addon.thumbnail_path
    elif addon.gallery_paths:
        for gp in addon.gallery_paths:
            if Path(gp).exists():
                path = gp
                break
    if not path:
        raise HTTPException(404, "No thumbnail")
    return FileResponse(path)

@app.get("/gallery/{addon_id}/{index}")
async def gallery(addon_id: str, index: int):
    addon = await storage.get_addon(addon_id)
    if not addon or index < 0 or index >= len(addon.gallery_paths):
        raise HTTPException(404, "No image")
    path = Path(addon.gallery_paths[index])
    if not path.exists():
        raise HTTPException(404, "No image")
    return FileResponse(str(path))


def _addon_image_dir(addon_id: str) -> Path:
    img_dir = USER_DATA_DIR / "gallery" / addon_id
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir


def _guess_ext(filename: str, content_type: str = "") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        if guessed:
            return guessed
    return ".png"


async def _store_gallery_upload(addon_id: str, upload: UploadFile) -> str:
    raw = await upload.read()
    if not raw:
        raise HTTPException(400, "Empty image upload")
    ext = _guess_ext(upload.filename or "image", upload.content_type or "")
    dest = _addon_image_dir(addon_id) / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(raw)
    return str(dest.resolve())


@app.post("/api/addons/{addon_id}/gallery/upload")
async def upload_gallery_image(addon_id: str, file: UploadFile = File(...)):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    path = await _store_gallery_upload(addon_id, file)
    gallery = [gp for gp in addon.gallery_paths if Path(gp).exists()]
    gallery.append(path)
    addon.gallery_paths = list(dict.fromkeys(gallery))
    if not addon.thumbnail_path or not Path(addon.thumbnail_path).exists():
        addon.thumbnail_path = path
    await storage.upsert_addon(addon)
    await _record_library_event('gallery_upload', screen='images', addon_id=addon.id, addon_title=addon.title, details={'image_path': path, 'gallery_count': len(addon.gallery_paths)})
    return addon.to_frontend_dict()


class GalleryDefaultUpdate(BaseModel):
    index: int


@app.post("/api/addons/{addon_id}/gallery/set-default")
async def gallery_set_default(addon_id: str, body: GalleryDefaultUpdate):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    if body.index < 0 or body.index >= len(addon.gallery_paths):
        raise HTTPException(404, "No image")
    path = addon.gallery_paths[body.index]
    if not Path(path).exists():
        raise HTTPException(404, "No image")
    addon.thumbnail_path = path
    await storage.upsert_addon(addon)
    await _record_library_event('gallery_set_default', screen='images', addon_id=addon.id, addon_title=addon.title, details={'thumbnail_path': path, 'index': body.index})
    return addon.to_frontend_dict()


@app.delete("/api/addons/{addon_id}/gallery/{index}")
async def delete_gallery_image(addon_id: str, index: int):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    if index < 0 or index >= len(addon.gallery_paths):
        raise HTTPException(404, "No image")
    path = addon.gallery_paths.pop(index)
    try:
        p = Path(path)
        if str(p).startswith(str(USER_DATA_DIR)) and p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass
    if addon.thumbnail_path == path:
        addon.thumbnail_path = addon.gallery_paths[0] if addon.gallery_paths else None
    await storage.upsert_addon(addon)
    await _record_library_event('gallery_delete', screen='images', addon_id=addon.id, addon_title=addon.title, details={'deleted_path': path, 'gallery_count': len(addon.gallery_paths)})
    return addon.to_frontend_dict()



def _path_under_any_root(path: Path, roots: list[Path]) -> bool:
    try:
        rp = path.resolve()
    except Exception:
        return False
    for root in roots:
        try:
            rr = root.resolve()
            if str(rp).lower().startswith(str(rr).lower()):
                return True
        except Exception:
            continue
    return False


def _strip_cfg_quotes(value: str) -> str:
    v = str(value or '').strip()
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        return v[1:-1].strip()
    return v


def _read_cfg_fields(path: Path) -> dict:
    wanted = {"base_container", "ui_variation", "variation", "atc_airline", "atc_flight_number", "atc_id", "atc_model", "ui_powerplant", "title", "texture", "model", "atc_type", "ui_type", "name"}
    out = {}
    try:
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith(';') or line.startswith('#') or line.startswith('//'):
                continue
            if line.startswith('[') and line.endswith(']'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip().lower()
            if key not in wanted:
                continue
            value = _strip_cfg_quotes(value.strip())
            if value and key not in out:
                out[key] = value
    except Exception:
        return out
    return out


def _read_ini_sections(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    try:
        parser = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';','#'))
        parser.optionxform = str.lower
        parser.read(path, encoding='utf-8')
        for section in parser.sections():
            sec = {}
            for key, value in parser.items(section):
                sec[str(key).lower()] = _clean_cfg_value(str(value))
            sections[str(section).lower()] = sec
    except Exception:
        return sections
    return sections


def _first_existing(paths: list[Path]) -> Optional[Path]:
    for p in paths:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None


def _addon_is_inibuilds(addon: Addon) -> bool:
    values = [
        str(getattr(addon, 'publisher', '') or ''),
        str(getattr(addon, 'package_name', '') or ''),
        str(getattr(addon, 'title', '') or ''),
        str(getattr(getattr(addon, 'pr', None), 'package_name', '') or ''),
        str(Path(addon.addon_path).name if getattr(addon, 'addon_path', '') else ''),
    ]
    joined = ' '.join(values).lower()
    return 'inibuild' in joined


def _addon_allows_external_liveries(addon: Addon) -> bool:
    values = [
        str(getattr(addon, 'publisher', '') or ''),
        str(getattr(addon, 'package_name', '') or ''),
        str(getattr(addon, 'title', '') or ''),
        str(getattr(getattr(addon, 'pr', None), 'package_name', '') or ''),
        str(Path(addon.addon_path).name if getattr(addon, 'addon_path', '') else ''),
    ]
    joined = ' '.join(values).lower()
    allowed_tokens = ('inibuild', 'pmdg', 'ifly', 'tfdi', 'tfdidesign')
    return any(tok in joined for tok in allowed_tokens)


def _aircraft_family_tokens(values: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in values:
        for tok in re.split(r'[^a-z0-9]+', str(raw or '').lower()):
            tok = tok.strip()
            if not tok:
                continue
            compact = re.sub(r'[^a-z0-9]+', '', tok)
            if not compact:
                continue
            m = re.match(r'^([a-z]{1,4})(\d{3,4})([a-z]{0,2})$', compact)
            if m:
                prefix = m.group(1)
                digits = m.group(2)
                out.add(prefix + digits)
                if len(digits) >= 3:
                    out.add(prefix + digits[:3])
                continue
            m = re.match(r'^(\d{3})([a-z]{0,2})$', compact)
            if m:
                digits = m.group(1)
                if digits[0] == '7':
                    out.add('7' + digits[1] + '7')
                    out.add(digits)
                else:
                    out.add(digits)
                continue
            if any(ch.isdigit() for ch in compact):
                out.add(compact)
    return out


def _addon_family_tokens(addon: Addon) -> set[str]:
    return _aircraft_family_tokens(_package_token_candidates(addon))


def _inibuilds_family_tokens_for_addon(addon: Addon) -> set[str]:
    """Return normalized aircraft-family tokens for iniBuilds-style package matching.

    Release 190 referenced this helper during livery preview/import but never
    defined it, which caused the runtime crash captured in the attached console
    log.
    """
    return _addon_family_tokens(addon)


def _path_matches_inibuilds_family(addon: Addon, *values: str) -> bool:
    """Stricter iniBuilds matcher used for external livery package scans."""
    flat_values = [str(v or '') for v in values if str(v or '').strip()]
    if not flat_values:
        return False
    joined = ' '.join(flat_values).lower()
    if 'inibuild' not in joined:
        return False
    return _candidate_matches_aircraft_model(addon, *flat_values)


def _candidate_matches_aircraft_family(addon: Addon, *values: str) -> bool:
    addon_tokens = _addon_family_tokens(addon)
    if not addon_tokens:
        return False
    cand_tokens = _aircraft_family_tokens(list(values))
    if not cand_tokens:
        return False
    return bool(addon_tokens & cand_tokens)


def _sanitize_inibuilds_liveries(addon: Addon, items: list[dict]) -> list[dict]:
    """Keep only livery records that still belong to the current aircraft."""
    cleaned: list[dict] = []
    seen: set[str] = set()
    addon_is_inibuilds = _addon_is_inibuilds(addon)
    family_tokens = _inibuilds_family_tokens_for_addon(addon) if addon_is_inibuilds else set()

    def _dedupe_key(item: dict) -> str:
        parts = [
            str(item.get('package_root') or ''),
            str(item.get('subject_dir') or ''),
            str(item.get('config_path') or ''),
            str(item.get('title_override') or item.get('name') or ''),
            str(item.get('variant') or ''),
            str(item.get('airline') or ''),
            str(item.get('thumbnail_path') or ''),
        ]
        return '|'.join(parts).lower()

    def _matches_item(item: dict) -> bool:
        if not addon_is_inibuilds:
            return True
        if item.get('internal'):
            return True
        parser = str(item.get('parser') or '').lower()
        package_root_raw = str(item.get('package_root') or '')
        if package_root_raw.startswith('internal:'):
            return True
        package_root = Path(package_root_raw) if package_root_raw else None
        cfg = item.get('cfg') or {}
        values = [
            str(item.get('package_name') or ''),
            str(item.get('subject_dir') or ''),
            str(item.get('config_path') or ''),
            str(item.get('title_override') or ''),
            str(item.get('name') or ''),
            str(item.get('variant') or ''),
            str(item.get('airline') or ''),
            str(item.get('model') or ''),
            str(cfg.get('base_container') or ''),
            str(cfg.get('title') or ''),
            str(cfg.get('ui_variation') or ''),
            str(cfg.get('variation') or ''),
            str(cfg.get('name') or ''),
        ]
        joined = ' '.join(v for v in values if v).lower()
        if parser.startswith('inibuilds') and 'inibuild' not in joined:
            return False
        if package_root and package_root.exists() and _external_package_matches_aircraft(addon, package_root, *values):
            return True
        if _candidate_matches_aircraft_model(addon, *values):
            return True
        compact = _aircraft_family_tokens(values)
        if family_tokens and compact and (compact & family_tokens):
            return True
        return False

    for raw in list(items or []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if not _matches_item(item):
            continue
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    cleaned.sort(key=lambda x: (
        str(x.get('internal') is not True),
        str(x.get('category') or '').lower(),
        str(x.get('package_name') or '').lower(),
        str(x.get('title_override') or x.get('name') or '').lower(),
        str(x.get('variant') or '').lower(),
    ))
    return cleaned


def _package_token_candidates(addon: Addon) -> list[str]:
    out = []
    raw_values = [
        Path(addon.addon_path).name if addon.addon_path else '',
        addon.package_name or '',
        addon.pr.package_name or '',
        addon.title or '',
    ]
    for raw in raw_values:
        raw = str(raw or '').strip()
        if raw and raw not in out:
            out.append(raw)
    return out


_LIVERY_IGNORE_TOKENS = {
    'inibuilds','ini','livery','liveries','cabin','cabins','pack','packs','preset','presets','config','thumbnail','variation','aircraft','texture','textures','community','msfs','microsoft','flight','simulator'
}


def _model_like_tokens(values: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in values:
        for tok in re.split(r'[^a-z0-9]+', str(raw or '').lower()):
            tok = tok.strip()
            if not tok or tok in _LIVERY_IGNORE_TOKENS:
                continue
            if any(ch.isdigit() for ch in tok):
                out.add(tok)
    return out


def _candidate_matches_aircraft_model(addon: Addon, *values: str) -> bool:
    if _candidate_matches_aircraft_family(addon, *values):
        return True
    addon_tokens = _model_like_tokens(_package_token_candidates(addon))
    if not addon_tokens:
        return False
    candidate_tokens = _model_like_tokens(list(values))
    if not candidate_tokens:
        return False
    return bool(addon_tokens & candidate_tokens)


def _common_prefix_token_count(a: str, b: str) -> int:
    ta = [t for t in re.split(r'[-_\s]+', (a or '').lower()) if t]
    tb = [t for t in re.split(r'[-_\s]+', (b or '').lower()) if t]
    count = 0
    for x, y in zip(ta, tb):
        if x != y:
            break
        count += 1
    return count


def _parse_livery_variant_parts(value: str) -> tuple[str, str]:
    raw = str(value or '').strip()
    if not raw:
        return '', ''
    m = re.match(r'^(.*?)\s*\((.*?)\)\s*$', raw)
    if not m:
        return raw, ''
    base = m.group(1).strip()
    inside = m.group(2).strip()
    parts = [p.strip() for p in inside.split('|')]
    if len(parts) >= 2 and re.fullmatch(r'(19|20)\d{2}', parts[-1]):
        year = parts[-1]
        reg = ' | '.join(parts[:-1]).strip()
        variant = base + (f' ({reg})' if reg else '')
        return variant.strip(), year
    return raw, ''


def _current_iso_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _find_livery_config(subject_dir: Path, package_root: Path) -> tuple[Optional[Path], dict]:
    checked = set()
    candidates = []
    cur = subject_dir
    while True:
        candidates.extend([cur / 'livery.cfg', cur / 'aircraft.cfg', cur / 'config' / 'aircraft.cfg'])
        if cur == package_root or cur.parent == cur:
            break
        cur = cur.parent
    for cand in candidates:
        try:
            rc = cand.resolve()
        except Exception:
            rc = cand
        if rc in checked:
            continue
        checked.add(rc)
        if cand.exists() and cand.is_file():
            return cand, _read_cfg_fields(cand)
    return None, {}


def _norm_key(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (value or '').lower())


def _collect_livery_thumbnail_candidates(root: Path) -> list[Path]:
    exts = {'.png', '.jpg', '.jpeg', '.webp'}
    out = []
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        nm = p.name.lower()
        if nm in {'thumbnail.png', 'thumbnail.jpg', 'thumbnail.jpeg', 'thumbnail.webp', 'thumbnail_variation.png'} or (p.parent.name.lower() == 'thumbnail' and 'thumbnail' in nm):
            out.append(p)
    return out


def _strip_cfg_quotes(value: str) -> str:
    raw = str(value or '').strip()
    if len(raw) >= 2 and ((raw[0] == '"' and raw[-1] == '"') or (raw[0] == "'" and raw[-1] == "'")):
        return raw[1:-1].strip()
    return raw


def _clean_cfg_value(value: str) -> str:
    raw = str(value or '')
    out = []
    quote = ''
    i = 0
    while i < len(raw):
        ch = raw[i]
        if quote:
            if ch == quote:
                quote = ''
            out.append(ch)
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch in (';', '#'):
            break
        out.append(ch)
        i += 1
    return _strip_cfg_quotes(''.join(out).strip())

def _parse_aircraft_cfg_variants(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    general: dict[str, str] = {}
    variants: list[dict[str, str]] = []
    current_section = ''
    current_variant: dict[str, str] | None = None
    try:
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw.strip()
            if not line or line.startswith(';') or line.startswith('#') or line.startswith('//'):
                continue
            if line.startswith('[') and line.endswith(']'):
                sec = line[1:-1].strip().lower()
                current_section = sec
                if sec == 'general':
                    current_variant = None
                elif sec.startswith('fltsim.'):
                    current_variant = {'section': sec}
                    variants.append(current_variant)
                else:
                    current_variant = None
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip().lower()
            value = _clean_cfg_value(value)
            if current_section == 'general':
                if value:
                    general[key] = value
            elif current_section.startswith('fltsim.') and current_variant is not None:
                current_variant[key] = value
    except Exception:
        return general, variants
    return general, variants


def _display_title_for_internal_variant(is_airliner: bool, general_title: str, ui_variation: str, package_name: str, texture_token: str) -> str:
    general_title = _clean_cfg_value(general_title)
    ui_variation = _clean_cfg_value(ui_variation)
    texture_token = _clean_cfg_value(texture_token)
    if is_airliner:
        return ui_variation or general_title or package_name or texture_token or 'Livery'
    return general_title or ui_variation or package_name or texture_token or 'Livery'


def _secondary_variant_for_internal_variant(is_airliner: bool, general_title: str, ui_variation: str, reg: str, texture_token: str) -> str:
    ui_variation = _clean_cfg_value(ui_variation)
    reg = _clean_cfg_value(reg)
    texture_token = _clean_cfg_value(texture_token)
    if is_airliner:
        return ''
    return ui_variation or reg or texture_token or ''


def _looks_like_registration(value: str) -> bool:
    v = _clean_cfg_value(value)
    if not v:
        return False
    return bool(re.fullmatch(r'[A-Za-z0-9-]{3,10}', v))


def _find_child_dir_case_insensitive(base: Path, name: str) -> Optional[Path]:
    if not base.exists() or not base.is_dir():
        return None
    low = str(name or '').strip().lower()
    for child in base.iterdir():
        try:
            if child.is_dir() and child.name.strip().lower() == low:
                return child
        except Exception:
            continue
    return None


def _norm_fs_token(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(value or '').strip().lower())


def _resolve_texture_dir(base_dir: Path, texture_token: str) -> Optional[Path]:
    token = str(texture_token or '').strip()
    if not token or not base_dir.exists() or not base_dir.is_dir():
        return None
    candidates = []
    if token.lower().startswith('texture.'):
        candidates.append(token)
    else:
        candidates.append(f'texture.{token}')
        candidates.append(token)
    seen = set()
    for cand in candidates:
        match = _find_child_dir_case_insensitive(base_dir, cand)
        if match:
            return match
        seen.add(_norm_fs_token(cand))
    try:
        for child in base_dir.rglob('*'):
            if not child.is_dir():
                continue
            nm = _norm_fs_token(child.name)
            if nm in seen:
                return child
    except Exception:
        pass
    return None


def _find_thumbnail_in_dir(base_dir: Optional[Path]) -> Optional[Path]:
    if not base_dir or not base_dir.exists() or not base_dir.is_dir():
        return None
    direct = _first_existing([
        base_dir / 'thumbnail.jpg', base_dir / 'thumbnail.jpeg', base_dir / 'thumbnail.png', base_dir / 'thumbnail.webp',
        base_dir / 'Thumbnail.jpg', base_dir / 'Thumbnail.jpeg', base_dir / 'Thumbnail.png', base_dir / 'Thumbnail.webp',
    ])
    if direct:
        return direct
    try:
        for child in base_dir.iterdir():
            if child.is_file() and child.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} and child.name.lower().startswith('thumbnail'):
                return child
    except Exception:
        pass
    return None


def _ui_variation_contains_model(icao_model: str, ui_variation: str) -> bool:
    model = _strip_cfg_quotes(icao_model)
    variation = _strip_cfg_quotes(ui_variation)
    if not model or not variation:
        return False
    model_norm = _norm_key(model)
    variation_norm = _norm_key(variation)
    if model_norm and model_norm in variation_norm:
        return True
    tokens = set()
    tokens.update(_aircraft_family_tokens([model]))
    tokens.update(_model_like_tokens([model]))
    for tok in tokens:
        compact = _norm_key(tok)
        if compact and compact in variation_norm:
            return True
    return False


def _internal_livery_header_and_secondary(general_title: str, ui_variation: str, atc_airline: str, reg: str, texture_token: str) -> tuple[str, str]:
    general_title = _clean_cfg_value(general_title)
    ui_variation = _clean_cfg_value(ui_variation)
    atc_airline = _clean_cfg_value(atc_airline)
    reg = _clean_cfg_value(reg)
    texture_token = _clean_cfg_value(texture_token)
    if ui_variation and _ui_variation_contains_model(general_title, ui_variation):
        header = ui_variation
        secondary = reg if _looks_like_registration(reg) else ''
        return header or general_title or texture_token, secondary
    header = general_title or ui_variation or texture_token or reg
    secondary = ui_variation or (reg if _looks_like_registration(reg) else '') or texture_token
    if _norm_key(secondary) == _norm_key(header):
        secondary = reg if _looks_like_registration(reg) and _norm_key(reg) != _norm_key(header) else ''
    return header, secondary


def _read_manifest_match_values(package_root: Path) -> list[str]:
    values = [package_root.name]
    try:
        mf = package_root / 'manifest.json'
        if mf.exists() and mf.is_file():
            import json as _json
            raw = _json.loads(mf.read_text(encoding='utf-8', errors='ignore') or '{}')
            for key in ('title','package_name','creator','manufacturer','name'):
                val = str(raw.get(key) or '').strip()
                if val and val not in values:
                    values.append(val)
            content = raw.get('content_type')
            if isinstance(content, str) and content.strip() and content not in values:
                values.append(content.strip())
    except Exception:
        pass
    return values


def _external_package_matches_aircraft(addon: Addon, package_root: Path, *values: str) -> bool:
    candidate_values = list(_read_manifest_match_values(package_root)) + [str(v or '') for v in values]
    if _candidate_matches_aircraft_model(addon, *candidate_values):
        return True
    addon_title_norm = _norm_key(str(getattr(addon, 'title', '') or ''))
    for raw in candidate_values:
        norm = _norm_key(str(raw or ''))
        if addon_title_norm and norm and (addon_title_norm in norm or norm in addon_title_norm):
            return True
    return False


def _addon_is_airliner(addon: Addon) -> bool:
    values = [
        str(getattr(addon, 'sub', '') or ''),
        str(getattr(addon, 'type', '') or ''),
        str(getattr(addon, 'title', '') or ''),
        str(getattr(addon, 'package_name', '') or ''),
    ]
    joined = ' '.join(values).lower()
    if 'airliner' in joined:
        return True
    tokens = {'a220','a300','a310','a318','a319','a320','a321','a330','a340','a350','a380','b707','b717','b727','b737','b747','b757','b767','b777','b787','rj','146','crj','atr','q400','md11','md-11','e170','e175','e190','e195','f28','f70','f100'}
    norm = _norm_key(joined)
    return any(_norm_key(tok) in norm for tok in tokens)


def _scan_internal_liveries_for_aircraft(addon: Addon, community_dir: Optional[Path]) -> list[dict]:
    addon_root = Path(getattr(addon, 'addon_path', '') or '')
    if not addon_root.exists():
        return []
    airplanes_root = addon_root / 'SimObjects' / 'Airplanes'
    if not airplanes_root.exists() or not airplanes_root.is_dir():
        return []
    results = []
    seen = set()
    is_airliner = _addon_is_airliner(addon)
    direct_aircraft_dirs = [p for p in airplanes_root.iterdir() if p.is_dir()]
    for aircraft_dir in direct_aircraft_dirs:
        cfg_path = aircraft_dir / 'aircraft.cfg'
        if not cfg_path.exists() or not cfg_path.is_file():
            continue
        try:
            cfg_path.resolve().relative_to(addon_root.resolve())
        except Exception:
            continue
        package_name = aircraft_dir.name
        general, variants = _parse_aircraft_cfg_variants(cfg_path)
        general_title = _clean_cfg_value(general.get('icao_model', '') or general.get('ui_type', '') or general.get('title', '') or package_name)
        powerplant = _clean_cfg_value(general.get('icao_engine_type', '') or '')
        for fields in variants:
            sec_low = str(fields.get('section') or '').strip().lower()
            texture_token = _clean_cfg_value(fields.get('texture', '') or '')
            ui_variation = _clean_cfg_value(fields.get('ui_variation', '') or '')
            atc_airline = _clean_cfg_value(fields.get('atc_airline', '') or fields.get('icao_airline', '') or '')
            reg = _clean_cfg_value(fields.get('atc_id', '') or '')
            header = _display_title_for_internal_variant(is_airliner, general_title, ui_variation, package_name, texture_token)
            display_variant = _secondary_variant_for_internal_variant(is_airliner, general_title, ui_variation, reg, texture_token)
            texture_dir = _resolve_texture_dir(aircraft_dir, texture_token) if texture_token else None
            if not texture_dir and reg:
                texture_dir = _resolve_texture_dir(aircraft_dir, reg)
            if not texture_dir:
                ui_thumb = _clean_cfg_value(fields.get('ui_thumbnailfile', '') or '')
                if ui_thumb:
                    try:
                        cand = (aircraft_dir / ui_thumb).resolve()
                        if cand.exists() and cand.is_file():
                            texture_dir = cand.parent
                    except Exception:
                        pass
            thumb = _find_thumbnail_in_dir(texture_dir)
            item_id = hashlib.md5((str(cfg_path.resolve()) + '|' + sec_low + '|' + package_name + '|' + reg + '|' + texture_token).encode('utf-8', 'ignore')).hexdigest()
            subject_dir = texture_dir or aircraft_dir
            item = {
                'id': item_id,
                'name': header,
                'airline': atc_airline or '',
                'variant': display_variant or '',
                'year': '',
                'flight_number': '',
                'model': general_title or getattr(addon, 'title', '') or package_name,
                'powerplant': powerplant,
                'base_container': '',
                'category': 'Livery',
                'thumbnail_path': str(thumb.resolve()) if thumb else '',
                'package_root': f'internal:{addon.id}:{package_name}',
                'package_name': package_name,
                'subject_dir': str(subject_dir.resolve()),
                'config_path': str(cfg_path.resolve()),
                'enabled': False,
                'fav': False,
                'scanned_at': _current_iso_timestamp(),
                'parser': 'internal-variant',
                'title_override': header,
                'internal': True,
                'is_airliner': is_airliner,
                'texture_token': texture_token,
                'debug_thumb': str(thumb.resolve()) if thumb else '',
            }
            key = (item['package_root'] + '|' + sec_low + '|' + texture_token + '|' + reg).lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    results.sort(key=lambda x: ((x.get('package_name') or '').lower(), (x.get('title_override') or x.get('name') or '').lower(), (x.get('variant') or '').lower()))
    return results


def _scan_inibuilds_livery_candidates_for_aircraft(addon: Addon, liveries_root: Path) -> list[dict]:
    if not liveries_root.exists():
        return []
    results = []
    seen = set()
    family_tokens = _inibuilds_family_tokens_for_addon(addon)
    if not family_tokens:
        return []
    for package_root in [p for p in liveries_root.iterdir() if p.is_dir()]:
        pkg_name_lower = package_root.name.lower()
        if 'inibuild' not in pkg_name_lower:
            continue
        if not _path_matches_inibuilds_family(addon, package_root.name):
            continue
        # Cabin pack structure: presets/**/config/aircraft.cfg with thumbnail/thumbnail_variation.png
        for cfg_path in package_root.rglob('config/aircraft.cfg'):
            lower_parts = [x.lower() for x in cfg_path.parts]
            if 'presets' not in lower_parts:
                continue
            variation_root = cfg_path.parent.parent
            thumb = _first_existing([variation_root / 'thumbnail' / 'thumbnail_variation.png', package_root / 'thumbnail' / 'thumbnail_variation.png'])
            cfg = _read_cfg_fields(cfg_path)
            extra_names = [package_root.name, variation_root.name]
            if not _external_package_matches_aircraft(addon, package_root, package_root.name, variation_root.name, cfg.get('base_container',''), cfg.get('title',''), cfg.get('ui_variation',''), cfg.get('variation','')):
                continue
            key = ('cabin|' + str(cfg_path.resolve())).lower()
            if key in seen:
                continue
            seen.add(key)
            results.append({
                'kind': 'cabin',
                'package_root': package_root,
                'subject_dir': variation_root,
                'cfg_path': cfg_path,
                'cfg': cfg,
                'thumb': thumb,
            })
        # Separate livery packages with lowest livery.cfg and thumbnail/thumbnail.png
        for livery_cfg in package_root.rglob('livery.cfg'):
            subject_dir = livery_cfg.parent
            thumb = _first_existing([subject_dir / 'thumbnail' / 'thumbnail.png', package_root / 'thumbnail' / 'thumbnail.png'])
            sections = _read_ini_sections(livery_cfg)
            cfg = {}
            cfg.update(_read_cfg_fields(livery_cfg))
            cfg['name'] = sections.get('general', {}).get('name', '') or cfg.get('name', '')
            extra_names = [package_root.name, subject_dir.name]
            if not _external_package_matches_aircraft(addon, package_root, package_root.name, subject_dir.name, cfg.get('base_container',''), cfg.get('title',''), cfg.get('name','')):
                continue
            key = ('livery|' + str(livery_cfg.resolve())).lower()
            if key in seen:
                continue
            seen.add(key)
            results.append({
                'kind': 'livery',
                'package_root': package_root,
                'subject_dir': subject_dir,
                'cfg_path': livery_cfg,
                'cfg': cfg,
                'thumb': thumb,
            })
    return results


def _livery_scan_candidates_for_aircraft(addon: Addon, liveries_root: Path) -> list[dict]:
    if not liveries_root.exists():
        return []
    if _addon_is_inibuilds(addon):
        filtered = []
        seen = set()
        for item in _scan_inibuilds_livery_candidates_for_aircraft(addon, liveries_root):
            pkg_name = str(item.get('package_root').name if item.get('package_root') else '')
            subject_name = str(item.get('subject_dir').name if item.get('subject_dir') else '')
            cfg = item.get('cfg') or {}
            if not _candidate_matches_aircraft_family(addon, pkg_name, subject_name, cfg.get('base_container',''), cfg.get('title',''), cfg.get('ui_variation',''), cfg.get('variation',''), cfg.get('name','')):
                continue
            key = (str(item.get('kind') or '') + '|' + str(item['subject_dir'].resolve())).lower()
            if key in seen:
                continue
            seen.add(key)
            filtered.append(item)
        return filtered
    results = []
    seen = set()
    thumbs = _collect_livery_thumbnail_candidates(liveries_root)
    for thumb in thumbs:
        try:
            rel = thumb.relative_to(liveries_root)
        except Exception:
            continue
        if not rel.parts:
            continue
        package_root = liveries_root / rel.parts[0]
        subject_dir = thumb.parent.parent if thumb.parent.name.lower() == 'thumbnail' else thumb.parent
        cfg_path, cfg = _find_livery_config(subject_dir, package_root)
        if not _external_package_matches_aircraft(addon, package_root, rel.parts[0], subject_dir.name, cfg.get('base_container',''), cfg.get('title',''), cfg.get('ui_variation',''), cfg.get('variation',''), cfg.get('name','')):
            continue
        key = str(subject_dir.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'thumb': thumb,
            'rel': rel,
            'package_root': package_root,
            'subject_dir': subject_dir,
            'cfg_path': cfg_path,
            'cfg': cfg,
            'kind': 'generic',
        })
    # Prefer iniBuilds-specific candidates when present for iniBuilds aircraft, but also include them generally because they represent concrete packages.
    for item in _scan_inibuilds_livery_candidates_for_aircraft(addon, liveries_root):
        key = (item['kind'] + '|' + str(item['subject_dir'].resolve())).lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results




def _build_livery_item(existing_map: dict, package_root: Path, subject_dir: Path, thumb: Optional[Path], cfg_path: Optional[Path], cfg: dict, *, addon: Addon, category: str, name: str, airline: str, variant: str, package_name: str, parser: str, year: str = '', extra: Optional[dict] = None, community_dir: Optional[Path] = None) -> dict:
    """Create a normalized external livery record.

    Release 192 still referenced this helper from the iniBuilds and generic
    livery scanners but never defined it, which caused the external-livery path
    to crash even after the earlier sanitize helpers were restored.
    """
    cfg = dict(cfg or {})
    extra = dict(extra or {})
    package_root_resolved = package_root.resolve() if package_root else package_root
    subject_dir_resolved = subject_dir.resolve() if subject_dir else subject_dir
    cfg_path_resolved = cfg_path.resolve() if cfg_path else None
    thumb_path = str(thumb.resolve()) if thumb else ''
    package_root_str = str(package_root_resolved) if package_root_resolved else ''
    subject_dir_str = str(subject_dir_resolved) if subject_dir_resolved else ''
    cfg_path_str = str(cfg_path_resolved) if cfg_path_resolved else ''

    name = str(name or '').strip()
    airline = str(airline or '').strip()
    variant = str(variant or '').strip()
    year = str(year or '').strip()
    package_name = str(package_name or (package_root.name if package_root else '')).strip()
    parser = str(parser or 'generic').strip()
    category = str(category or 'Livery').strip()

    title_override = str(extra.get('title_override') or name or airline or package_name or (subject_dir.name if subject_dir else 'Livery')).strip()
    base_container = _clean_cfg_value(cfg.get('base_container') or '')
    model = _clean_cfg_value(
        cfg.get('atc_type')
        or cfg.get('ui_type')
        or cfg.get('title')
        or cfg.get('variation')
        or cfg.get('ui_variation')
        or getattr(addon, 'title', '')
        or package_name
        or (subject_dir.name if subject_dir else '')
    )
    powerplant = _clean_cfg_value(cfg.get('ui_powerplant') or '')
    texture_token = _clean_cfg_value(cfg.get('texture') or '')
    is_airliner = _addon_is_airliner(addon)

    item_key = (package_root_str + '|' + variant + '|' + airline + '|' + thumb_path).lower()
    existing = dict(existing_map.get(item_key) or {})

    enabled = bool(existing.get('enabled', False))
    if community_dir and package_root_str and not package_root_str.startswith('internal:'):
        try:
            enabled = bool(linker.find_link_in_community(Path(community_dir), Path(package_root_str)))
        except Exception:
            enabled = bool(existing.get('enabled', False))

    item_id_seed = '|'.join([package_root_str, subject_dir_str, cfg_path_str, parser, title_override, airline, variant, thumb_path])
    item_id = hashlib.md5(item_id_seed.encode('utf-8', 'ignore')).hexdigest()

    item = {
        'id': item_id,
        'name': name or title_override or 'Livery',
        'airline': airline or '',
        'variant': variant or '',
        'year': year or '',
        'flight_number': _clean_cfg_value(cfg.get('atc_flight_number') or ''),
        'model': model,
        'powerplant': powerplant,
        'base_container': base_container,
        'category': category,
        'thumbnail_path': thumb_path,
        'package_root': package_root_str,
        'package_name': package_name,
        'subject_dir': subject_dir_str,
        'config_path': cfg_path_str,
        'enabled': enabled,
        'fav': bool(existing.get('fav', False)),
        'scanned_at': _current_iso_timestamp(),
        'parser': parser,
        'title_override': title_override,
        'internal': False,
        'is_airliner': is_airliner,
        'texture_token': texture_token,
        'debug_thumb': thumb_path,
        'cfg': cfg,
    }

    for key, value in extra.items():
        if value is not None:
            item[key] = value

    for preserve_key in ('notes', 'rating', 'tags'):
        if preserve_key in existing and preserve_key not in item:
            item[preserve_key] = existing.get(preserve_key)

    return item

def _scan_liveries_for_aircraft(addon: Addon, liveries_root: Path, community_dir: Optional[Path]) -> list[dict]:
    existing_map = {}
    try:
        for ex in list(getattr(addon.usr, 'liveries', []) or []):
            ex_key = ((ex.get('package_root') or '') + '|' + (ex.get('variant') or '') + '|' + (ex.get('airline') or '') + '|' + (ex.get('thumbnail_path') or '')).lower()
            if ex_key:
                existing_map[ex_key] = ex
    except Exception:
        existing_map = {}
    results = []
    seen = set()
    for item in _scan_internal_liveries_for_aircraft(addon, community_dir):
        item_key = (item.get('package_root','') + '|' + item.get('variant','') + '|' + item.get('airline','') + '|' + item.get('thumbnail_path','')).lower()
        if item_key in seen:
            continue
        seen.add(item_key)
        results.append(item)
    if not liveries_root.exists() or not _addon_allows_external_liveries(addon):
        results.sort(key=lambda x: ((x.get('category') or '').lower(), (x.get('package_name') or '').lower(), (x.get('variant') or '').lower(), x.get('name') or ''))
        return results
    candidates = _livery_scan_candidates_for_aircraft(addon, liveries_root)
    for cand in candidates:
        thumb = cand.get('thumb')
        package_root = cand['package_root']
        subject_dir = cand['subject_dir']
        cfg_path = cand.get('cfg_path')
        cfg = cand.get('cfg') or {}
        kind = str(cand.get('kind') or 'generic').lower()
        if kind == 'cabin':
            variant = str(cfg.get('ui_variation', '') or cfg.get('variation', '') or subject_dir.name).strip()
            item = _build_livery_item(existing_map, package_root, subject_dir, thumb, cfg_path, cfg, addon=addon, category='Cabin Pack', name=variant or 'Cabin Pack', airline='', variant=variant, package_name=package_root.name, parser='inibuilds-cabin', extra={'title_override': variant or 'Cabin Pack'}, community_dir=community_dir)
        elif kind == 'livery':
            airline = str(cfg.get('name', '') or '').strip()
            item = _build_livery_item(existing_map, package_root, subject_dir, thumb, cfg_path, cfg, addon=addon, category='Livery', name=airline or subject_dir.name, airline=airline or subject_dir.name, variant='', package_name=package_root.name, parser='inibuilds-livery', extra={'title_override': airline or subject_dir.name}, community_dir=community_dir)
        else:
            airline = str(cfg.get('atc_airline', '') or '').strip()
            raw_variant = str(cfg.get('ui_variation', '') or cfg.get('variation', '') or cfg.get('title', '') or '').strip()
            variant, year = _parse_livery_variant_parts(raw_variant)
            lower_subject = str(subject_dir).lower()
            category = 'Cabin Pack' if ('cabin' in lower_subject or 'preset' in lower_subject) else 'Livery'
            item = _build_livery_item(existing_map, package_root, subject_dir, thumb, cfg_path, cfg, addon=addon, category=category, name=airline or variant or subject_dir.name, airline=airline or subject_dir.parent.name.replace('_',' ').replace('-',' '), variant=variant or raw_variant or subject_dir.name, year=year, package_name=package_root.name, parser='generic', community_dir=community_dir)
        item_key = (item['package_root'] + '|' + item.get('variant','') + '|' + item.get('airline','') + '|' + item.get('thumbnail_path','')).lower()
        if item_key in seen:
            continue
        seen.add(item_key)
        results.append(item)
    results.sort(key=lambda x: ((x.get('category') or '').lower(), (x.get('airline') or x.get('name') or '').lower(), (x.get('variant') or '').lower(), x.get('package_name') or ''))
    return results


class LiveryToggleRequest(BaseModel):
    package_root: str
    enabled: bool


class LiveryBatchToggleRequest(BaseModel):
    package_roots: list[str] = []
    enabled: bool = True




@app.get('/api/airport-overlay/{addon_id}')
async def airport_overlay(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404, 'Addon not found')
    code = str(getattr(getattr(addon, 'rw', None), 'icao', '') or getattr(addon, 'icao', '') or '')
    return overlay_stub_for_airport(addon.id, code)
@app.get('/api/livery-thumb')
async def livery_thumb(path: str):
    p = Path(path)
    roots = [USER_DATA_DIR]
    addons_root = await storage.get_setting('addons_root')
    liveries_root = await storage.get_setting('liveries_root')
    community_dir = await storage.get_setting('community_dir')
    if addons_root:
        roots.append(Path(addons_root))
    if liveries_root:
        roots.append(Path(liveries_root))
    if community_dir:
        roots.append(Path(community_dir))
    try:
        for addon in await storage.get_addons():
            ap = str(getattr(addon, 'addon_path', '') or '').strip()
            if ap:
                roots.append(Path(ap))
    except Exception:
        pass
    dedup=[]; seen=set()
    for root in roots:
        try:
            rr=str(Path(root).resolve()).lower()
        except Exception:
            continue
        if rr in seen:
            continue
        seen.add(rr)
        dedup.append(Path(root))
    if not p.exists() or not _path_under_any_root(p, dedup):
        raise HTTPException(404, 'No image')
    return FileResponse(str(p))


@app.post('/api/liveries/toggle')
async def toggle_livery(body: LiveryToggleRequest):
    community_dir = await storage.get_setting('community_dir')
    if not community_dir:
        raise HTTPException(400, 'Community folder not set')
    ok, msg = linker.toggle_addon(body.package_root, community_dir, body.enabled)
    if not ok:
        raise HTTPException(500, msg)
    enabled = linker.find_link_in_community(Path(community_dir), Path(body.package_root))
    return {'ok': True, 'message': msg, 'enabled': enabled, 'package_root': body.package_root}


@app.post('/api/liveries/toggle-batch')
async def toggle_livery_batch(body: LiveryBatchToggleRequest):
    community_dir = await storage.get_setting('community_dir')
    if not community_dir:
        raise HTTPException(400, 'Community folder not set')
    roots = []
    seen = set()
    for raw in list(body.package_roots or []):
        raw = str(raw or '').strip()
        if not raw:
            continue
        low = raw.lower()
        if low in seen:
            continue
        seen.add(low)
        roots.append(raw)
    if not roots:
        raise HTTPException(400, 'No livery packages were selected')
    results = []
    for root in roots:
        ok, msg = linker.toggle_addon(root, community_dir, body.enabled)
        enabled = linker.find_link_in_community(Path(community_dir), Path(root)) if ok else False
        results.append({'package_root': root, 'ok': bool(ok), 'message': msg, 'enabled': enabled})
    failed = [r for r in results if not r['ok']]
    if failed:
        raise HTTPException(500, '; '.join(r.get('message') or 'Failed' for r in failed[:3]))
    return {'ok': True, 'count': len(results), 'enabled': bool(body.enabled), 'results': results}


class LiveryRemoveRequest(BaseModel):
    ids: list[str] = []


@app.get('/api/addons/{addon_id}/scan-liveries-preview')
async def scan_liveries_preview(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    if addon.type != 'Aircraft':
        raise HTTPException(400, 'Livery scanning is only available for aircraft add-ons.')
    liveries_root = await storage.get_setting('liveries_root')
    candidates = []
    if liveries_root:
        root = Path(liveries_root)
        if root.exists():
            candidates.extend(_livery_scan_candidates_for_aircraft(addon, root))
    community_dir = await storage.get_setting('community_dir')
    internal_items = _scan_internal_liveries_for_aircraft(addon, Path(community_dir) if community_dir else None)
    package_names = []
    seen = set()
    for cand in candidates:
        name = cand['package_root'].name
        if name not in seen:
            seen.add(name)
            package_names.append(name)
    if internal_items:
        label = f"{getattr(getattr(addon, 'pr', None), 'package_name', '') or addon.package_name or Path(addon.addon_path).name} (built-in variants)"
        if label not in seen:
            seen.add(label)
            package_names.append(label)
    return {'ok': True, 'candidate_count': len(package_names), 'candidate_packages': package_names[:200]}


@app.post('/api/addons/{addon_id}/remove-liveries')
async def remove_liveries(addon_id: str, body: LiveryRemoveRequest):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    existing = list(getattr(addon.usr, 'liveries', []) or [])
    remove_ids = {str(x) for x in (body.ids or []) if str(x)}
    if not remove_ids:
        raise HTTPException(400, 'No livery ids provided')
    kept = [x for x in existing if str(x.get('id') or '') not in remove_ids]
    addon.usr.liveries = kept
    await storage.upsert_addon(addon)
    return {'ok': True, 'removed': len(existing) - len(kept), 'items': kept}


@app.post('/api/addons/{addon_id}/scan-liveries')
async def scan_liveries(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    if addon.type != 'Aircraft':
        raise HTTPException(400, 'Livery scanning is only available for aircraft add-ons.')
    liveries_root = await storage.get_setting('liveries_root')
    community_dir = await storage.get_setting('community_dir')
    items = []
    if liveries_root:
        root = Path(liveries_root)
        if root.exists():
            items.extend(_scan_liveries_for_aircraft(addon, root, Path(community_dir) if community_dir else None))
        else:
            items.extend(_scan_internal_liveries_for_aircraft(addon, Path(community_dir) if community_dir else None))
    else:
        items.extend(_scan_internal_liveries_for_aircraft(addon, Path(community_dir) if community_dir else None))
    items = _sanitize_inibuilds_liveries(addon, items)
    addon.usr.liveries = items
    await storage.upsert_addon(addon)
    return {'ok': True, 'count': len(items), 'items': items}

async def _sync_enabled_state_from_community(addons: dict[str, object]) -> dict[str, object]:
    """Refresh stored enabled flags from the actual Community folder state.

    This keeps the Library cards honest after any activation/deactivation action
    and also after external tools such as Addons Linker change the Community
    folder behind the scenes. We only persist rows that actually changed.
    """
    community_dir = await storage.get_setting('community_dir')
    if not community_dir:
        return addons
    try:
        enabled_links = linker.get_all_enabled(community_dir)
    except Exception as e:
        log.warning('Could not scan Community folder for enabled-state sync: %s', e)
        return addons

    enabled_targets = {str(Path(target).resolve()) for target in enabled_links.values() if target}
    enabled_names = {name.lower() for name in enabled_links.keys()}
    changed = 0
    for addon in addons.values():
        addon_target = str(Path(addon.addon_path).resolve()) if getattr(addon, 'addon_path', '') else ''
        addon_name = Path(addon.addon_path).name.lower() if getattr(addon, 'addon_path', '') else ''
        actual_enabled = bool(addon_target and (addon_target in enabled_targets or addon_name in enabled_names))
        if addon.enabled != actual_enabled:
            addon.enabled = actual_enabled
            await storage.upsert_addon(addon)
            changed += 1
    if changed:
        log.info('Refreshed Community-link enabled state for %s add-on(s)', changed)
    return addons


@app.get("/api/addons")
async def list_addons():
    addons = await storage.get_all_addons()
    addons = await _sync_enabled_state_from_community(addons)
    return [a.to_frontend_dict() for a in addons.values()]

@app.get("/api/addons/{addon_id}")
async def get_addon(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    synced = await _sync_enabled_state_from_community({addon.id: addon})
    addon = synced.get(addon.id, addon)
    original_liveries = list(getattr(addon.usr, 'liveries', []) or [])
    cleaned_liveries = _sanitize_inibuilds_liveries(addon, original_liveries)
    if cleaned_liveries != original_liveries:
        addon.usr.liveries = cleaned_liveries
        try:
            await storage.update_addon_user_data(addon.id, {'liveries': cleaned_liveries})
        except Exception:
            pass
    return addon.to_frontend_dict()

class UserDataUpdate(BaseModel):
    fav: Optional[bool] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    paid: Optional[float] = None
    source_store: Optional[str] = None
    avionics: Optional[str] = None
    features: Optional[str] = None
    resources: Optional[list] = None
    research_resources: Optional[list] = None
    data_resources: Optional[list] = None
    map_lat: Optional[float] = None
    map_lon: Optional[float] = None
    map_zoom: Optional[int] = None
    map_search_label: Optional[str] = None
    map_polygon: Optional[list] = None
    map_layout: Optional[dict] = None
    liveries: Optional[list] = None

@app.patch("/api/addons/{addon_id}/user")
async def update_user(addon_id: str, body: UserDataUpdate):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields provided")
    await storage.update_addon_user_data(addon_id, update)
    return {"ok": True}

class ToggleRequest(BaseModel):
    enabled: bool

class BrowserOpenRequest(BaseModel):
    url: str
    title: Optional[str] = None
    request_id: Optional[int] = None
    minimal_controls: Optional[bool] = None
    panel_kind: Optional[str] = None

class BrowserScriptRequest(BaseModel):
    script: str
    script_id: Optional[int] = None

class PomaxFlightPlanRequest(BaseModel):
    points: list[dict] = []
    name: Optional[str] = None
    open_panel: Optional[bool] = True

class PomaxRouteFileRequest(BaseModel):
    name: str = 'Hangar Route'
    file_name: str = ''
    points: list[dict] = []
    open_panel: bool = True

class PomaxCommandRequest(BaseModel):
    command: str = ''

class PomaxSlewRequest(BaseModel):
    points: list[dict] = []
    pause_after: bool = True

class BrowserUpdateRequest(BaseModel):
    current_url: Optional[str] = None
    current_title: Optional[str] = None
    visible: Optional[bool] = None

class AddonCoreUpdate(BaseModel):
    type: Optional[str] = None
    sub: Optional[str] = None
    title: Optional[str] = None
    publisher: Optional[str] = None
    summary: Optional[str] = None
    thumbnail_path: Optional[str] = None
    gallery_paths: Optional[list[str]] = None
    manufacturer: Optional[str] = None
    manufacturer_full_name: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    icao: Optional[str] = None
    version: Optional[str] = None
    latest_version: Optional[str] = None
    latest_version_date: Optional[str] = None
    released: Optional[str] = None
    price: Optional[float] = None
    package_name: Optional[str] = None
    product_source_store: Optional[str] = None
    rw_override: Optional[dict] = None

@app.patch("/api/addons/{addon_id}/meta")
async def update_addon_meta(addon_id: str, body: AddonCoreUpdate):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields provided")
    await storage.update_addon_core(addon_id, update)
    return {"ok": True}

@app.post("/api/addons/{addon_id}/toggle")
async def toggle_addon(addon_id: str, body: ToggleRequest):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    if not _addon_supports_link_management(addon):
        raise HTTPException(400, "This library item is not link-managed and cannot be activated from Community controls.")
    community_dir = await storage.get_setting("community_dir")
    if not community_dir:
        raise HTTPException(400, "Community folder not set")
    ok, msg = linker.toggle_addon(addon.addon_path, community_dir, body.enabled)
    if not ok:
        raise HTTPException(500, msg)
    # Sync the actual Community-folder state instead of trusting the requested
    # state blindly. This keeps the visual toggle honest if Windows denied a
    # symlink operation or if the link already existed in a different form.
    synced = await _sync_enabled_state_from_community({addon.id: addon})
    addon = synced.get(addon.id, addon)
    await storage.set_enabled(addon_id, addon.enabled)
    await _record_library_event('addon_' + ('activate' if addon.enabled else 'deactivate'), screen='library', addon_id=addon.id, addon_title=addon.title, details={'message': msg, 'enabled': addon.enabled})
    return {"ok": True, "message": msg, "enabled": addon.enabled}



def _openweather_units_from_setting(raw: str) -> str:
    v = (raw or '').strip().lower()
    if v in {'imperial','metric','standard'}:
        return v
    return 'imperial'


def _fetch_openweather_onecall(lat: float, lon: float, api_key: str, units: str = 'imperial') -> dict:
    params = {'lat': lat, 'lon': lon, 'appid': api_key, 'units': units, 'exclude': 'minutely,daily,alerts'}
    resp = requests.get('https://api.openweathermap.org/data/3.0/onecall', params=params, timeout=25, headers={'User-Agent': 'MSFS-Hangar/2.0'})
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _fetch_openweather_current(lat: float, lon: float, api_key: str, units: str = 'imperial') -> dict:
    params = {'lat': lat, 'lon': lon, 'appid': api_key, 'units': units}
    resp = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params, timeout=25, headers={'User-Agent': 'MSFS-Hangar/2.0'})
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _fetch_aviationweather_metar(icao: str) -> dict | None:
    station=(icao or '').strip().upper()
    if not station:
        return None
    resp = requests.get('https://aviationweather.gov/api/data/metar', params={'ids': station, 'format': 'json'}, timeout=25, headers={'User-Agent': 'MSFS-Hangar/2.0'})
    if resp.status_code == 204:
        return None
    resp.raise_for_status()
    data = resp.json() if resp.content else None
    if isinstance(data, list):
        return (data[0] if data else None)
    if isinstance(data, dict) and isinstance(data.get('data'), list):
        return (data.get('data')[0] if data.get('data') else None)
    return data if isinstance(data, dict) else None


def _normalize_aviationweather_payload(payload: dict | None, *, icao: str) -> dict:
    item = payload if isinstance(payload, dict) else {}
    clouds = item.get('clouds') if isinstance(item.get('clouds'), list) else []
    cloud_parts = []
    cover_map = {
        'FEW': 'Few',
        'SCT': 'Scattered',
        'BKN': 'Broken',
        'OVC': 'Overcast',
        'CLR': 'Clear',
        'SKC': 'Sky Clear',
        'VV': 'Vertical Visibility',
    }
    for c in clouds:
        if not isinstance(c, dict):
            continue
        raw_cover = str(c.get('cover') or c.get('type') or '').strip().upper()
        cover = cover_map.get(raw_cover, raw_cover.title() if raw_cover else '')
        base = c.get('base')
        if cover and base not in (None, ''):
            cloud_parts.append(f"{cover} {base}")
        elif cover:
            cloud_parts.append(cover)
    raw = item.get('rawOb') or item.get('raw_text') or item.get('raw') or ''
    flight_cat = item.get('fltCat') or item.get('flight_category') or ''
    vis = item.get('visib') or item.get('visibility')
    wind_speed = item.get('wspd') or item.get('wind_speed') or item.get('windSpeed')
    wind_deg = item.get('wdir') or item.get('wind_deg') or item.get('windDirection')
    temp_c = item.get('temp') if item.get('temp') is not None else item.get('temp_c')
    dew_c = item.get('dewp') if item.get('dewp') is not None else item.get('dewpoint_c')
    altim = item.get('altim') or item.get('altimeter')
    current = {
        'icao': icao,
        'raw_metar': raw,
        'obs_time': item.get('obsTime') or item.get('observation_time') or item.get('reportTime'),
        'flight_category': flight_cat,
        'temp': temp_c,
        'dew_point': dew_c,
        'visibility': vis,
        'wind_speed': wind_speed,
        'wind_deg': wind_deg,
        'altimeter': altim,
        'clouds_text': ', '.join(cloud_parts),
        'clouds': clouds,
        'description': item.get('wxString') or item.get('weather') or '',
        'main': flight_cat or 'METAR',
        'icon': '',
    }
    return {
        'provider': 'aviationweather_metar',
        'units': 'aviation',
        'current': current,
        'hourly_preview': [],
        'raw_source': 'aviationweather_metar',
    }




def _xml_local_name(tag: str) -> str:
    return str(tag or '').split('}')[-1]


def _offset_latlon_from_ref(ref_lat: float, ref_lon: float, bias_x: float = 0.0, bias_z: float = 0.0) -> tuple[float, float]:
    lat = float(ref_lat) + (float(bias_z) / 111320.0)
    cos_lat = max(0.1, math.cos(math.radians(float(ref_lat))))
    lon = float(ref_lon) + (float(bias_x) / (111320.0 * cos_lat))
    return lat, lon


def _airport_point_from_attrs(attrs: dict, ref_lat: float, ref_lon: float) -> tuple[float, float] | None:
    try:
        if attrs.get('lat') not in (None, '') and attrs.get('lon') not in (None, ''):
            return float(attrs.get('lat')), float(attrs.get('lon'))
        if attrs.get('biasX') not in (None, '') or attrs.get('biasZ') not in (None, ''):
            bx = float(attrs.get('biasX') or 0.0)
            bz = float(attrs.get('biasZ') or 0.0)
            return _offset_latlon_from_ref(ref_lat, ref_lon, bx, bz)
    except Exception:
        return None
    return None


def _build_runway_polygon(center_lat: float, center_lon: float, heading_deg: float, length_m: float, width_m: float) -> dict:
    def move(lat, lon, bearing, meters):
        r = 6378137.0
        d = meters / r
        br = math.radians(bearing)
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(br))
        lon2 = lon1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
        return math.degrees(lat2), ((math.degrees(lon2) + 540.0) % 360.0) - 180.0
    half_len = max(100.0, float(length_m or 0.0)) / 2.0
    half_width = max(8.0, float(width_m or 0.0)) / 2.0
    s_lat, s_lon = move(center_lat, center_lon, heading_deg + 180.0, half_len)
    e_lat, e_lon = move(center_lat, center_lon, heading_deg, half_len)
    p1 = move(s_lat, s_lon, heading_deg - 90.0, half_width)
    p2 = move(e_lat, e_lon, heading_deg - 90.0, half_width)
    p3 = move(e_lat, e_lon, heading_deg + 90.0, half_width)
    p4 = move(s_lat, s_lon, heading_deg + 90.0, half_width)
    return {
        'polygon': [
            {'lat': p1[0], 'lon': p1[1]},
            {'lat': p2[0], 'lon': p2[1]},
            {'lat': p3[0], 'lon': p3[1]},
            {'lat': p4[0], 'lon': p4[1]},
        ],
        'centerline': [
            {'lat': s_lat, 'lon': s_lon},
            {'lat': e_lat, 'lon': e_lon},
        ]
    }


def _score_airport_xml_candidate(path: Path, content_sample: str, icao: str) -> int:
    score = 0
    low = content_sample.lower()
    if '<airport' in low:
        score += 20
    if icao and icao.lower() in low:
        score += 80
    if '<taxiwaypoint' in low:
        score += 25
    if '<taxiwaypath' in low:
        score += 25
    if '<taxiwayparking' in low:
        score += 20
    if '<runway' in low:
        score += 20
    return score


def _parse_airport_layout_from_package_xml(addon: Addon) -> dict | None:
    addon_path = Path((addon.addon_path or '').strip())
    if not addon_path.exists():
        return None
    icao = str((addon.rw.icao or addon.rw.faa_id or '')).strip().upper()
    xml_candidates: list[tuple[int, Path]] = []
    try:
        for idx, xml_path in enumerate(addon_path.rglob('*.xml')):
            if idx > 250:
                break
            try:
                sample = xml_path.read_text(encoding='utf-8', errors='ignore')[:200000]
            except Exception:
                continue
            score = _score_airport_xml_candidate(xml_path, sample, icao)
            if score > 0:
                xml_candidates.append((score, xml_path))
    except Exception:
        return None
    for _score, xml_path in sorted(xml_candidates, key=lambda t: (-t[0], len(str(t[1])))):
        try:
            root = ET.parse(xml_path).getroot()
        except Exception:
            continue
        airport_nodes = [el for el in root.iter() if _xml_local_name(el.tag) == 'Airport']
        for airport in airport_nodes:
            attrs = airport.attrib or {}
            airport_ident = str(attrs.get('ident') or attrs.get('icao') or '').strip().upper()
            if icao and airport_ident and airport_ident != icao:
                continue
            try:
                ref_lat = float(attrs.get('lat'))
                ref_lon = float(attrs.get('lon'))
            except Exception:
                continue
            taxi_points: dict[int, dict] = {}
            taxi_paths: list[dict] = []
            parking: list[dict] = []
            runways: list[dict] = []
            for child in list(airport):
                name = _xml_local_name(child.tag)
                cattrs = child.attrib or {}
                if name == 'TaxiwayPoint':
                    try:
                        idx = int(cattrs.get('index'))
                    except Exception:
                        continue
                    pt = _airport_point_from_attrs(cattrs, ref_lat, ref_lon)
                    if pt:
                        taxi_points[idx] = {'lat': pt[0], 'lon': pt[1], 'type': cattrs.get('type') or ''}
                elif name == 'TaxiwayParking':
                    try:
                        idx = int(cattrs.get('index'))
                    except Exception:
                        idx = None
                    pt = _airport_point_from_attrs(cattrs, ref_lat, ref_lon)
                    if pt:
                        info = {'lat': pt[0], 'lon': pt[1], 'name': cattrs.get('name') or '', 'type': cattrs.get('type') or ''}
                        parking.append(info)
                        if idx is not None:
                            taxi_points[idx] = {'lat': pt[0], 'lon': pt[1], 'type': cattrs.get('type') or 'PARKING'}
                elif name == 'TaxiwayPath':
                    try:
                        s = int(cattrs.get('start'))
                        e = int(cattrs.get('end'))
                    except Exception:
                        continue
                    p1 = taxi_points.get(s)
                    p2 = taxi_points.get(e)
                    if p1 and p2:
                        taxi_paths.append({'name': cattrs.get('type') or cattrs.get('surface') or 'Taxiway', 'points': [{'lat': p1['lat'], 'lon': p1['lon']}, {'lat': p2['lat'], 'lon': p2['lon']}]})
                elif name == 'Runway':
                    pt = _airport_point_from_attrs(cattrs, ref_lat, ref_lon)
                    if not pt:
                        continue
                    heading = None
                    for key in ('heading', 'orientation', 'angle'):
                        if cattrs.get(key) not in (None, ''):
                            try:
                                heading = float(cattrs.get(key))
                                break
                            except Exception:
                                pass
                    if heading is None:
                        heading = 90.0
                    try:
                        length_m = float(cattrs.get('length') or cattrs.get('lengthMeters') or 1800.0)
                    except Exception:
                        length_m = 1800.0
                    try:
                        width_m = float(cattrs.get('width') or cattrs.get('widthMeters') or 45.0)
                    except Exception:
                        width_m = 45.0
                    geom = _build_runway_polygon(pt[0], pt[1], heading, length_m, width_m)
                    runways.append({'id': str(cattrs.get('number') or cattrs.get('designator') or cattrs.get('name') or cattrs.get('primaryNumber') or 'Runway'), 'heading_deg': heading, 'length_ft': round(length_m * 3.28084, 1), 'width_m': width_m, 'polygon': geom['polygon'], 'centerline': geom['centerline']})
            if runways or taxi_paths or parking:
                return {
                    'version': 2,
                    'generated_at': datetime.utcnow().isoformat() + 'Z',
                    'source': 'package_xml',
                    'source_file': str(xml_path),
                    'center': {'lat': ref_lat, 'lon': ref_lon},
                    'runways': runways,
                    'taxiway_paths': taxi_paths,
                    'parking': parking,
                }
    return None

def _normalize_openweather_payload(payload: dict, *, provider: str, units: str) -> dict:
    current = payload.get('current') if isinstance(payload, dict) and isinstance(payload.get('current'), dict) else payload
    weather_list = current.get('weather') if isinstance(current, dict) else None
    weather0 = weather_list[0] if isinstance(weather_list, list) and weather_list else {}
    hourly = payload.get('hourly') if isinstance(payload, dict) and isinstance(payload.get('hourly'), list) else []
    main_block = current.get('main') if isinstance(current, dict) and isinstance(current.get('main'), dict) else {}
    wind_block = current.get('wind') if isinstance(current, dict) and isinstance(current.get('wind'), dict) else {}
    clouds_block = current.get('clouds') if isinstance(current, dict) and isinstance(current.get('clouds'), dict) else {}
    return {
        'provider': provider,
        'units': units,
        'current': {
            'temp': current.get('temp', main_block.get('temp')),
            'feels_like': current.get('feels_like', main_block.get('feels_like')),
            'pressure': current.get('pressure', main_block.get('pressure')),
            'humidity': current.get('humidity', main_block.get('humidity')),
            'dew_point': current.get('dew_point'),
            'uvi': current.get('uvi'),
            'clouds': current.get('clouds', clouds_block.get('all')),
            'visibility': current.get('visibility'),
            'wind_speed': current.get('wind_speed', wind_block.get('speed')),
            'wind_gust': current.get('wind_gust', wind_block.get('gust')),
            'wind_deg': current.get('wind_deg', wind_block.get('deg')),
            'description': weather0.get('description') or '',
            'main': weather0.get('main') or '',
            'icon': weather0.get('icon') or '',
        },
        'hourly_preview': [
            {
                'dt': item.get('dt'),
                'temp': item.get('temp', (item.get('main') or {}).get('temp') if isinstance(item.get('main'), dict) else None),
                'wind_speed': item.get('wind_speed', (item.get('wind') or {}).get('speed') if isinstance(item.get('wind'), dict) else None),
                'clouds': item.get('clouds', (item.get('clouds') or {}).get('all') if isinstance(item.get('clouds'), dict) else None),
                'pop': item.get('pop'),
                'description': ((item.get('weather') or [{}])[0] or {}).get('description', ''),
                'main': ((item.get('weather') or [{}])[0] or {}).get('main', ''),
            }
            for item in hourly[:6] if isinstance(item, dict)
        ],
        'raw_source': provider,
    }

@app.get("/api/settings")
async def get_settings():
    return await storage.get_all_settings()

class SettingUpdate(BaseModel):
    value: str

@app.put("/api/settings/{key}")
async def set_setting(key: str, body: SettingUpdate):
    await storage.set_setting(key, body.value)
    return {"ok": True}

@app.post("/api/library/reset")
async def reset_library():
    await storage.delete_all_addons()
    return {"ok": True}

@app.get("/api/selection")
async def get_selection():
    return {"paths": await storage.get_json_setting("scan_selected_paths", [])}

class SelectionUpdate(BaseModel):
    paths: list[str]

@app.put("/api/selection")
async def set_selection(body: SelectionUpdate):
    await storage.set_json_setting("scan_selected_paths", body.paths)
    return {"ok": True}

class RelocatePreviewRequest(BaseModel):
    old_root: str = ""
    new_root: str = ""
    repair_links: bool = True


class BatchRemoveRequest(BaseModel):
    addon_ids: list[str]
    remove_folders: bool = False
    ignore_future: bool = False


class IgnoreRemoveRequest(BaseModel):
    ignore_ids: list[int]


class ProfilePayload(BaseModel):
    name: str
    addon_ids: list[str] = []


class ProfileApplyRequest(BaseModel):
    profile_id: str


class ExternalToolCreateRequest(BaseModel):
    title: str
    publisher: str = ""
    launch_path: str
    working_dir: str = ""
    type: str = "Utility"
    subtype: str = "Utility"
    notes: str = ""


class ImportCommunityRequest(BaseModel):
    community_dir: str = ""
    addons_root: str = ""


class ImportOfficialRequest(BaseModel):
    official_root: str = ""


class VisibleApplyRequest(BaseModel):
    """Apply the current grid view to the Community folder.

    Any add-on id included here should be enabled. Any add-on not included here
    should be disabled. This lets the grid itself become a simple activation
    workspace without requiring the user to build a dedicated collection first.
    """

    addon_ids: list[str] = []


class CommunityActionRequest(BaseModel):
    """Preview or execute Community-folder linking actions.

    scope:
      - displayed: use the explicit addon_ids supplied by the current grid view
      - collections: use the union of addon ids from the selected collections
      - all: use every add-on in the library

    action:
      - activate: create/keep links for the scoped add-ons only
      - deactivate: remove links for the scoped add-ons only
    """

    scope: str = 'displayed'
    action: str = 'activate'
    addon_ids: list[str] = []
    collection_ids: list[str] = []


def _norm_path_str(value: str) -> str:
    if not value:
        return ""
    s = str(value).strip().replace("/", "\\")
    while len(s) > 3 and s.endswith("\\"):
        s = s[:-1]
    return s


def _path_equal(a: str, b: str) -> bool:
    return _norm_path_str(a).lower() == _norm_path_str(b).lower()


def _is_under_root(path_value: str, root_value: str) -> bool:
    p = _norm_path_str(path_value)
    r = _norm_path_str(root_value)
    if not p or not r:
        return False
    pl = p.lower()
    rl = r.lower()
    return pl == rl or pl.startswith(rl + "\\")


def _replace_root_prefix(path_value: str, old_root: str, new_root: str) -> str:
    p = _norm_path_str(path_value)
    old = _norm_path_str(old_root)
    new = _norm_path_str(new_root)
    if not _is_under_root(p, old):
        return path_value
    suffix = p[len(old):]
    if suffix.startswith("\\"):
        return new + suffix
    if not suffix:
        return new
    return new + "\\" + suffix


def _rewrite_local_paths(value, old_root: str, new_root: str):
    if isinstance(value, str):
        return _replace_root_prefix(value, old_root, new_root) if _is_under_root(value, old_root) else value
    if isinstance(value, list):
        return [_rewrite_local_paths(v, old_root, new_root) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite_local_paths(v, old_root, new_root) for k, v in value.items()}
    return value


def _rewrite_addon_paths(addon, old_root: str, new_root: str):
    addon.addon_path = _replace_root_prefix(addon.addon_path, old_root, new_root)
    if addon.manifest_path:
        addon.manifest_path = _replace_root_prefix(addon.manifest_path, old_root, new_root)
    if addon.thumbnail_path:
        addon.thumbnail_path = _replace_root_prefix(addon.thumbnail_path, old_root, new_root)
    addon.gallery_paths = [_replace_root_prefix(p, old_root, new_root) if _is_under_root(p, old_root) else p for p in (addon.gallery_paths or [])]
    addon.docs = [type(doc)(**_rewrite_local_paths(doc.__dict__, old_root, new_root)) for doc in (addon.docs or [])]
    addon.usr.resources = _rewrite_local_paths(addon.usr.resources or [], old_root, new_root)
    addon.usr.research_resources = _rewrite_local_paths(addon.usr.research_resources or [], old_root, new_root)
    addon.usr.data_resources = _rewrite_local_paths(addon.usr.data_resources or [], old_root, new_root)
    addon.exists = Path(addon.addon_path).exists()
    return addon


def _build_relocation_plan(addons: dict[str, object], old_root: str, new_root: str):
    old_root = _norm_path_str(old_root)
    new_root = _norm_path_str(new_root)
    if not old_root:
        raise HTTPException(400, 'Old add-ons root is empty')
    if not new_root:
        raise HTTPException(400, 'New add-ons root is empty')
    if _path_equal(old_root, new_root):
        raise HTTPException(400, 'Old and new add-ons roots must be different')
    old_exists = Path(old_root).exists()
    new_exists = Path(new_root).exists()
    if not old_exists:
        raise HTTPException(400, f'Old add-ons root not found: {old_root}')
    if not new_exists:
        raise HTTPException(400, f'New add-ons root not found: {new_root}')

    plan_items = []
    missing = []
    manifest_missing = []
    total_relocated = 0
    for addon in addons.values():
        if not getattr(addon, 'addon_path', None):
            continue
        if not _is_under_root(addon.addon_path, old_root):
            continue
        total_relocated += 1
        new_addon_path = _replace_root_prefix(addon.addon_path, old_root, new_root)
        new_manifest = _replace_root_prefix(addon.manifest_path, old_root, new_root) if getattr(addon, 'manifest_path', None) else ''
        exists_new = Path(new_addon_path).exists()
        manifest_exists = bool(new_manifest) and Path(new_manifest).exists()
        item = {
            'addon_id': addon.id,
            'title': addon.title,
            'old_addon_path': addon.addon_path,
            'new_addon_path': new_addon_path,
            'old_manifest_path': addon.manifest_path or '',
            'new_manifest_path': new_manifest or '',
            'enabled': bool(addon.enabled),
            'exists_new': exists_new,
            'manifest_exists': manifest_exists if new_manifest else None,
        }
        plan_items.append(item)
        if not exists_new:
            missing.append({'addon_id': addon.id, 'title': addon.title, 'path': new_addon_path})
        if new_manifest and not manifest_exists:
            manifest_missing.append({'addon_id': addon.id, 'title': addon.title, 'path': new_manifest})

    return {
        'old_root': old_root,
        'new_root': new_root,
        'count': total_relocated,
        'repair_candidates': len([p for p in plan_items if p['enabled']]),
        'missing_count': len(missing),
        'manifest_missing_count': len(manifest_missing),
        'sample': plan_items[:8],
        'missing_sample': missing[:8],
        'manifest_missing_sample': manifest_missing[:8],
        'items': plan_items,
    }


async def _preview_relocation(old_root: str, new_root: str):
    addons = await storage.get_all_addons(include_removed=True)
    return _build_relocation_plan(addons, old_root, new_root)


async def _repair_enabled_links_after_relocation(items: list[dict], community_dir: str):
    repaired = 0
    failed = []
    if not community_dir:
        return repaired, failed
    for item in items:
        if not item.get('enabled'):
            continue
        old_path = item.get('old_addon_path') or ''
        new_path = item.get('new_addon_path') or ''
        try:
            linker.disable_addon(old_path, community_dir)
            ok, msg = linker.enable_addon(new_path, community_dir)
            if ok:
                repaired += 1
            else:
                failed.append({'title': item.get('title') or new_path, 'error': msg})
        except Exception as e:
            failed.append({'title': item.get('title') or new_path, 'error': str(e)})
    return repaired, failed


@app.post('/api/library/relocate/preview')
async def preview_relocate_library(body: RelocatePreviewRequest):
    old_root = body.old_root or await storage.get_setting('addons_root')
    plan = await _preview_relocation(old_root, body.new_root)
    return {'ok': True, **{k:v for k,v in plan.items() if k != 'items'}}


@app.post('/api/library/relocate/execute')
async def execute_relocate_library(body: RelocatePreviewRequest):
    old_root = body.old_root or await storage.get_setting('addons_root')
    plan = await _preview_relocation(old_root, body.new_root)
    addons = await storage.get_all_addons(include_removed=True)
    updated = []
    updated_ids = []
    for item in plan['items']:
        addon = addons.get(item['addon_id'])
        if not addon:
            continue
        old_path = addon.addon_path
        addon = _rewrite_addon_paths(addon, plan['old_root'], plan['new_root'])
        addon.enabled = bool(item.get('enabled'))
        updated.append(addon)
        updated_ids.append(addon.id)
        item['old_addon_path'] = old_path
        item['new_addon_path'] = addon.addon_path
    if updated:
        await storage.update_many_existing(updated)
    # Update settings so future scans and UI defaults point to the new root.
    await storage.set_setting('addons_root', plan['new_root'])
    selected_paths = await storage.get_json_setting('scan_selected_paths', [])
    migrated_selected = [_replace_root_prefix(p, plan['old_root'], plan['new_root']) if _is_under_root(p, plan['old_root']) else p for p in (selected_paths or [])]
    await storage.set_json_setting('scan_selected_paths', migrated_selected)
    await storage.remap_ignored_paths(plan['old_root'], plan['new_root'])
    repaired = 0
    repair_failed = []
    community_dir = await storage.get_setting('community_dir')
    if body.repair_links and community_dir:
        repaired, repair_failed = await _repair_enabled_links_after_relocation(plan['items'], community_dir)
    synced = await _sync_enabled_state_from_community(await storage.get_all_addons(include_removed=False))
    return {
        'ok': True,
        'updated': len(updated_ids),
        'old_root': plan['old_root'],
        'new_root': plan['new_root'],
        'missing_count': plan['missing_count'],
        'manifest_missing_count': plan['manifest_missing_count'],
        'repaired_links': repaired,
        'repair_failed': repair_failed[:12],
        'migrated_selected_paths': len([p for p in migrated_selected if _is_under_root(p, plan['new_root'])]),
        'sample': plan['sample'],
    }


def _safe_folder_delete(path_str: str) -> tuple[bool, str]:
    try:
        p = Path(path_str).resolve()
        if not p.exists():
            return True, f'Folder already missing: {p}'
        if not p.is_dir():
            return False, f'Not a directory: {p}'
        if len(str(p)) < 8 or str(p) in {'/', '\\'}:
            return False, f'Refusing unsafe delete: {p}'
        shutil.rmtree(p)
        return True, f'Removed folder: {p}'
    except Exception as e:
        return False, str(e)


def _profile_store(raw):
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _build_ignore_entry(addon) -> dict:
    return {
        'addon_path': addon.addon_path or '',
        'package_name': addon.package_name or getattr(addon.pr, 'package_name', None) or '',
        'title': addon.title or '',
        'publisher': addon.publisher or '',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'note': 'Removed from library but kept on disk; skip future scans.',
    }


@app.get('/api/library/ignored')
async def list_ignored_library_items():
    return {'items': await storage.list_ignored_addons()}


@app.post('/api/library/ignored/remove')
async def remove_ignored_library_items(body: IgnoreRemoveRequest):
    await storage.remove_ignored_addons(body.ignore_ids or [])
    return {'ok': True}


@app.post('/api/library/remove-selected')
async def remove_selected_addons(body: BatchRemoveRequest):
    addon_ids = [aid for aid in (body.addon_ids or []) if aid]
    if not addon_ids:
        raise HTTPException(400, 'No addons selected')
    addons = await storage.get_all_addons(include_removed=True)
    community_dir = await storage.get_setting('community_dir')
    removed_rows = []
    removed_folders = []
    ignored_entries = []
    failed = []
    for addon_id in addon_ids:
        addon = addons.get(addon_id)
        if not addon:
            failed.append({'addon_id': addon_id, 'error': 'Addon not found'})
            continue
        try:
            if addon.enabled and community_dir:
                linker.toggle_addon(addon.addon_path, community_dir, False)
            if body.remove_folders and addon.addon_path:
                ok, msg = _safe_folder_delete(addon.addon_path)
                if ok:
                    removed_folders.append(addon.addon_path)
                else:
                    failed.append({'addon_id': addon_id, 'error': msg})
                    continue
            elif body.ignore_future:
                ignored_entries.append(_build_ignore_entry(addon))
            removed_rows.append(addon_id)
        except Exception as e:
            failed.append({'addon_id': addon_id, 'error': str(e)})
    if removed_rows:
        await storage.delete_addons(removed_rows)
    if ignored_entries:
        await storage.add_ignored_addons(ignored_entries)
    log.info('Library remove-selected count=%s folders=%s ignored=%s failed=%s', len(removed_rows), len(removed_folders), len(ignored_entries), len(failed))
    return {'ok': True, 'removed_ids': removed_rows, 'removed_folders': removed_folders, 'ignored_count': len(ignored_entries), 'failed': failed}


def _addon_supports_link_management(addon) -> bool:
    return bool(addon and getattr(addon, 'managed', True) and getattr(addon, 'entry_kind', 'addon') == 'addon' and getattr(addon, 'addon_path', ''))


def _addon_can_launch(addon) -> bool:
    return bool(addon and getattr(addon, 'entry_kind', 'addon') == 'tool' and (getattr(addon, 'launch_path', None) or getattr(addon, 'addon_path', '')))


def _safe_tool_subtype(raw: str) -> str:
    value = (raw or '').strip()
    return value or 'Utility'

def _safe_tool_type(raw: str) -> str:
    value = (raw or '').strip()
    allowed = [t for t in DEFAULT_DATA_OPTIONS.get('subtypes', {}).keys() if t != 'External Tool']
    if value in allowed:
        return value
    return 'Utility'


def _is_real_dir_not_link(path: Path) -> bool:
    try:
        return path.exists() and path.is_dir() and not linker.is_junction(path)
    except Exception:
        return False


def _first_manifest_under(path: Path) -> Optional[Path]:
    try:
        manifests = scan_module._discover_manifest_files(path)
        return manifests[0] if manifests else None
    except Exception:
        return None


def _discover_official_package_roots(root: Path) -> list[Path]:
    """Find Marketplace / Official package folders by manifest.json only.

    The Official folder can contain extra cache/support folders; importing every
    directory was too noisy. We only import the direct parent folders that hold a
    manifest.json anywhere below the selected root.
    """
    package_roots = []
    seen = set()
    try:
        manifests = scan_module._discover_manifest_files(root)
    except Exception:
        manifests = []
    for mf in manifests:
        try:
            pkg = mf.parent.resolve()
        except Exception:
            pkg = mf.parent
        key = str(pkg).strip().lower()
        if key and key not in seen:
            seen.add(key)
            package_roots.append(pkg)
    return sorted(package_roots, key=lambda p: p.name.lower())


def _existing_path_keys(addons: dict[str, Addon]) -> set[str]:
    keys=set()
    for addon in addons.values():
        if getattr(addon, 'addon_path', None):
            keys.add(str(addon.addon_path).strip().lower())
    return keys


def _mark_special_library_item(addon: Addon, *, entry_kind: str, managed: bool, enabled: Optional[bool] = None):
    addon.entry_kind = entry_kind
    addon.managed = managed
    if enabled is not None:
        addon.enabled = enabled
    return addon


async def _import_community_only_items(community_dir: str, addons_root: str = ''):
    community_path = Path((community_dir or '').strip())
    addons_root_path = Path((addons_root or '').strip()) if (addons_root or '').strip() else None
    if not community_path.exists():
        raise HTTPException(400, f'Community folder not found: {community_dir}')
    existing = await storage.get_all_addons(include_removed=True)
    existing_paths = _existing_path_keys(existing)
    added=[]
    skipped=0
    for entry in sorted(community_path.iterdir(), key=lambda p: p.name.lower()):
        if not _is_real_dir_not_link(entry):
            continue
        if addons_root_path and _is_under_root(str(entry), str(addons_root_path)):
            skipped += 1
            continue
        mf = _first_manifest_under(entry)
        if not mf:
            skipped += 1
            continue
        addon = scan_module.build_addon_from_manifest(mf, None, entry)
        if not addon:
            skipped += 1
            continue
        addon = _mark_special_library_item(addon, entry_kind='community', managed=False, enabled=True)
        addon.summary = addon.summary or 'Community-only add-on installed directly in the simulator Community folder.'
        addon.usr.source_store = addon.usr.source_store or 'Community Folder'
        key = str(addon.addon_path or '').strip().lower()
        if not key or key in existing_paths:
            skipped += 1
            continue
        existing_paths.add(key)
        added.append(addon)
    if added:
        await storage.upsert_many(added)
    return {'ok': True, 'added': len(added), 'skipped': skipped}


async def _import_official_items(official_root: str):
    official_path = Path((official_root or '').strip())
    if not official_path.exists():
        raise HTTPException(400, f'Official / Marketplace folder not found: {official_root}')
    existing = await storage.get_all_addons(include_removed=True)
    existing_paths = _existing_path_keys(existing)
    added=[]
    skipped=0
    package_roots = _discover_official_package_roots(official_path)
    for entry in package_roots:
        key = str(entry.resolve()).strip().lower()
        if key in existing_paths:
            skipped += 1
            continue
        mf = _first_manifest_under(entry)
        if not mf:
            skipped += 1
            continue
        addon = scan_module.build_addon_from_manifest(mf, None, entry)
        if not addon:
            addon = Addon(
                type='Mod',
                sub='Official / Marketplace',
                title=entry.name,
                publisher='MSFS Marketplace',
                summary='Official / Marketplace content. Inventory item only; not link-managed.',
                addon_path=str(entry.resolve()),
                package_name=entry.name,
                enabled=True,
                exists=True,
            )
        addon = _mark_special_library_item(addon, entry_kind='official', managed=False, enabled=True)
        addon.usr.source_store = addon.usr.source_store or 'MSFS Marketplace'
        if not addon.sub:
            addon.sub = 'Official / Marketplace'
        existing_paths.add(key)
        added.append(addon)
    if added:
        await storage.upsert_many(added)
    return {'ok': True, 'added': len(added), 'skipped': skipped, 'found': len(package_roots)}


def _launch_tool_process(addon: Addon) -> dict:
    launch_path = (getattr(addon, 'launch_path', None) or addon.addon_path or '').strip()
    if not launch_path:
        raise HTTPException(400, 'Tool executable path is empty')
    exe = Path(launch_path)
    if not exe.exists():
        raise HTTPException(400, f'Tool executable not found: {launch_path}')
    working_dir = (getattr(addon, 'working_dir', None) or str(exe.parent)).strip() or str(exe.parent)
    args = (getattr(addon, 'launch_args', None) or '').strip()
    cmd = [str(exe)] + (shlex.split(args, posix=False) if args else [])
    subprocess.Popen(cmd, cwd=working_dir or None, shell=False)
    return {'ok': True, 'title': addon.title, 'launch_path': launch_path, 'working_dir': working_dir}



@app.post('/api/library/import-community-only')
async def import_community_only(body: ImportCommunityRequest):
    community_dir = body.community_dir or await storage.get_setting('community_dir')
    addons_root = body.addons_root or await storage.get_setting('addons_root')
    return await _import_community_only_items(community_dir, addons_root)


@app.post('/api/library/import-official')
async def import_official_library(body: ImportOfficialRequest):
    official_root = body.official_root or await storage.get_setting('official_root')
    if not official_root:
        raise HTTPException(400, 'Set the Official / Marketplace folder first.')
    return await _import_official_items(official_root)


@app.post('/api/tools/add')
async def add_external_tool(body: ExternalToolCreateRequest):
    launch_path = (body.launch_path or '').strip()
    title = (body.title or '').strip()
    if not launch_path:
        raise HTTPException(400, 'Executable path required')
    if not title:
        raise HTTPException(400, 'Display name required')
    exe = Path(launch_path)
    addon = Addon(
        type=_safe_tool_type(body.type),
        sub=_safe_tool_subtype(body.subtype),
        title=title,
        publisher=(body.publisher or '').strip() or exe.parent.name or 'Local Publisher',
        summary=(body.notes or '').strip() or 'Local external tool or utility launched from MSFS Hangar.',
        addon_path=str(exe.resolve()),
        launch_path=str(exe.resolve()),
        working_dir=(body.working_dir or str(exe.parent)).strip() or str(exe.parent),
        launch_args='',
        enabled=False,
        exists=exe.exists(),
        entry_kind='tool',
        managed=False,
    )
    addon.usr.notes = (body.notes or '').strip()
    addon.usr.source_store = 'Local'
    addon.pr.source_store = 'Local'
    await storage.upsert_addon(addon)
    return {'ok': True, 'addon': addon.to_frontend_dict()}


@app.post('/api/tools/{addon_id}/launch')
async def launch_external_tool(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404, 'Tool not found')
    if not _addon_can_launch(addon):
        raise HTTPException(400, 'This library item is not a launchable tool.')
    return _launch_tool_process(addon)


@app.get('/api/profiles')
async def list_profiles():
    raw = await storage.get_setting('profiles_json', '[]')
    return {'profiles': _profile_store(raw)}


@app.post('/api/profiles')
async def create_profile(body: ProfilePayload):
    profiles = _profile_store(await storage.get_setting('profiles_json', '[]'))
    name = (body.name or '').strip()
    if not name:
        raise HTTPException(400, 'Profile name required')
    profile = {'id': uuid.uuid4().hex[:10], 'name': name, 'addon_ids': list(dict.fromkeys(body.addon_ids or [])), 'created_at': datetime.utcnow().isoformat() + 'Z', 'updated_at': datetime.utcnow().isoformat() + 'Z'}
    profiles.append(profile)
    await storage.set_setting('profiles_json', json.dumps(profiles, ensure_ascii=False))
    return {'ok': True, 'profile': profile}


@app.put('/api/profiles/{profile_id}')
async def update_profile(profile_id: str, body: ProfilePayload):
    profiles = _profile_store(await storage.get_setting('profiles_json', '[]'))
    found = None
    for profile in profiles:
        if profile.get('id') == profile_id:
            profile['name'] = (body.name or profile.get('name') or '').strip() or profile.get('name') or 'Profile'
            profile['addon_ids'] = list(dict.fromkeys(body.addon_ids or []))
            profile['created_at'] = profile.get('created_at') or datetime.utcnow().isoformat() + 'Z'
            profile['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            found = profile
            break
    if not found:
        raise HTTPException(404, 'Profile not found')
    await storage.set_setting('profiles_json', json.dumps(profiles, ensure_ascii=False))
    return {'ok': True, 'profile': found}


@app.delete('/api/profiles/{profile_id}')
async def delete_profile(profile_id: str):
    profiles = _profile_store(await storage.get_setting('profiles_json', '[]'))
    next_profiles = [p for p in profiles if p.get('id') != profile_id]
    await storage.set_setting('profiles_json', json.dumps(next_profiles, ensure_ascii=False))
    return {'ok': True}


@app.post('/api/profiles/apply')
async def apply_profile(body: ProfileApplyRequest):
    profile_id = (body.profile_id or '').strip()
    profiles = _profile_store(await storage.get_setting('profiles_json', '[]'))
    profile = next((p for p in profiles if p.get('id') == profile_id), None)
    if not profile:
        raise HTTPException(404, 'Profile not found')
    community_dir = await storage.get_setting('community_dir')
    if not community_dir:
        raise HTTPException(400, 'Community folder not set')
    selected_ids = set(profile.get('addon_ids') or [])
    addons = list((await storage.get_all_addons()).values())
    enabled_count = 0
    disabled_count = 0
    failures = []
    for addon in addons:
        if not _addon_supports_link_management(addon):
            continue
        should_enable = addon.id in selected_ids
        try:
            ok, msg = linker.toggle_addon(addon.addon_path, community_dir, should_enable)
            if not ok:
                failures.append({'addon_id': addon.id, 'title': addon.title, 'error': msg})
                continue
            await storage.set_enabled(addon.id, should_enable)
            if should_enable:
                enabled_count += 1
            else:
                disabled_count += 1
        except Exception as e:
            failures.append({'addon_id': addon.id, 'title': addon.title, 'error': str(e)})
    log.info('Applied profile %s enabled=%s disabled=%s failures=%s', profile.get('name'), enabled_count, disabled_count, len(failures))
    return {'ok': True, 'profile': profile, 'enabled': enabled_count, 'disabled': disabled_count, 'failures': failures}


DEFAULT_DATA_OPTIONS = {
    "sources": sorted(["Aerosoft Shop","flightsim.to","Flightbeam Store","FlyTampa Store","GitHub","iniBuilds Store","Just Flight","MSFS Marketplace","Orbx Direct","PMDG Store","Simmarket","Other"]),
    "avionics": sorted(["Analog","G1000","G3000","G430","G530","G550","G750","GTN 750","Unsure"]),
    "tags": ["IFR","VFR","Study Level","Freeware","Payware","Major Hub","Training","Scenic","GA","Helicopter","Military","Business Jet"],
    "airport_sites": [
        {"name":"SkyVector","url":"https://skyvector.com/airport/{CODE}"},
        {"name":"Airportdata.com","url":"https://www.airportdata.com/search-data/airport-details/icao/{CODE_LOWER}"},
        {"name":"AVIPages","url":"https://aviapages.com/airport/{CODE_LOWER}/?source=site_search"},
        {"name":"Wikipedia","url":"https://en.wikipedia.org/wiki/{TITLE_UNDERSCORE}"},
        {"name":"AIRNAV","url":"https://www.airnav.com/airport/{CODE}"},
    ],
    "aircraft_sites": [
        {"name":"Wikipedia","url":"https://wikipedia.org"},
        {"name":"PlaneSpotters","url":"https://www.planespotters.net"},
        {"name":"SKYbrary","url":"https://skybrary.aero"},
        {"name":"Airliners.net","url":"https://www.airliners.net"},
        {"name":"Simple Flying","url":"https://simpleflying.com"},
        {"name":"FlightGlobal","url":"https://www.flightglobal.com"},
    ],
    "weather_sites": [
        {"name":"meteoblue Clouds","url":"https://www.meteoblue.com/en/weather/maps#coords=14.21/{LAT}/{LON}&map=totalClouds~hourlyAll~auto~sfc~none"},
        {"name":"AviationWeather GFA","url":"https://aviationweather.gov/gfa/#pcpn"},
        {"name":"Windy Radar","url":"https://embed.windy.com/embed2.html?lat={LAT}&lon={LON}&detailLat={LAT}&detailLon={LON}&zoom=7&level=surface&overlay=radar&product=radar&menu=&message=true&marker=true&calendar=now&pressure=true&type=map&location=coordinates&detail=true&metricWind=kt&metricTemp=%C2%B0F"},
    ],
    "subtypes": {
        "Aircraft": ["Airliner","General Aviation","Business Jet","Helicopter","Military","Regional"],
        "Airport": ["Large Commercial","Medium Commercial","General Aviation","Heliport","Seaplane Base","Closed"],
        "Scenery": ["City","Region","Landmark","Mesh","Airport scenery"],
        "Utility": ["Navigation","Tool","Weather","Mission"],
        "Vehicles": ["Car","Truck","Offroad"],
        "Boats": ["Pleasure","Military","Cargo"],
        "Mod": ["Livery","Enhancement","Other"],
    },
}


def _merged_data_options(settings: dict[str, str]) -> dict:
    options = json.loads(json.dumps(DEFAULT_DATA_OPTIONS))
    for key, setting_key in [("sources", "data_options_sources"), ("avionics", "data_options_avionics"), ("tags", "data_options_tags"), ("subtypes", "data_options_subtypes"), ("airport_sites", "data_options_airport_sites"), ("aircraft_sites", "data_options_aircraft_sites"), ("weather_sites", "data_options_weather_sites")]:
        raw = settings.get(setting_key)
        if not raw:
            continue
        try:
            val = json.loads(raw)
            if isinstance(val, (list, dict)):
                options[key] = val
        except Exception:
            continue
    return options


@app.get("/api/data-options")
async def get_data_options():
    settings = await storage.get_all_settings()
    return _merged_data_options(settings)


class DataOptionsUpdate(BaseModel):
    options: dict


@app.put("/api/data-options")
async def set_data_options(body: DataOptionsUpdate):
    options = body.options or {}
    for key, setting_key in [("sources", "data_options_sources"), ("avionics", "data_options_avionics"), ("tags", "data_options_tags"), ("subtypes", "data_options_subtypes"), ("airport_sites", "data_options_airport_sites"), ("aircraft_sites", "data_options_aircraft_sites"), ("weather_sites", "data_options_weather_sites")]:
        if key in options:
            await storage.set_json_setting(setting_key, options[key])
    return {"ok": True}


class ReplaceLibraryValue(BaseModel):
    field: str
    old_value: str
    new_value: str


@app.post("/api/library/replace-value")
async def replace_library_value(body: ReplaceLibraryValue):
    field = (body.field or '').strip()
    old = body.old_value
    new = body.new_value
    if not field or old == new:
        return {"ok": True, "updated": 0}
    addons = await storage.get_all_addons(include_removed=True)
    updated = []
    for addon in addons.values():
        changed = False
        if field == 'source_store' and addon.usr.source_store == old:
            addon.usr.source_store = new; changed = True
        elif field == 'avionics' and addon.usr.avionics == old:
            addon.usr.avionics = new; addon.rw.avionics = new; changed = True
        elif field == 'sub' and addon.sub == old:
            addon.sub = new; changed = True
        elif field == 'type' and addon.type == old:
            addon.type = new; changed = True
        elif field == 'tags' and old in (addon.usr.tags or []):
            addon.usr.tags = [new if t == old else t for t in addon.usr.tags]; changed = True
        if changed:
            updated.append(addon)
    if updated:
        await storage.update_many_existing(updated)
    return {"ok": True, "updated": len(updated)}


def _tree_node(path: Path, depth: int, max_depth: int):
    node = {"name": path.name, "path": str(path), "children": []}
    if depth >= max_depth:
        return node
    try:
        children = [p for p in sorted(path.iterdir(), key=lambda x: x.name.lower()) if p.is_dir() and not p.name.startswith(".")]
    except Exception:
        return node
    for child in children:
        node["children"].append(_tree_node(child, depth + 1, max_depth))
    return node

@app.get("/api/folders/tree")
async def folder_tree(root: Optional[str] = None, max_depth: int = 4):
    if not root:
        root = await storage.get_setting("addons_root")
    if not root:
        return {"root": None, "children": []}
    root_path = Path(root)
    if not root_path.exists():
        raise HTTPException(404, "Addons root not found")
    try:
        children = [_tree_node(p, 1, max_depth) for p in sorted(root_path.iterdir(), key=lambda x: x.name.lower()) if p.is_dir() and not p.name.startswith(".")]
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"root": str(root_path), "children": children}


@app.get("/api/folders/top")
async def folder_top(root: Optional[str] = None):
    if not root:
        root = await storage.get_setting("addons_root")
    if not root:
        return {"root": None, "folders": []}
    root_path = Path(root)
    if not root_path.exists():
        raise HTTPException(404, "Addons root not found")
    folders = []
    for p in sorted(root_path.iterdir(), key=lambda x: x.name.lower()):
        if p.is_dir() and not p.name.startswith('.'):
            folders.append({"name": p.name, "path": str(p.resolve())})
    return {"root": str(root_path), "folders": folders}


@app.get('/api/folders/drives')
async def folder_drives():
    """Return local drive roots for the folder-browser modal.

    The desktop app runs on Windows for Keith's workflow, but a safe fallback is
    included for non-Windows development so the UI can still browse from '/'.
    """

    drives = []
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = f'{letter}:\\'
            if os.path.exists(drive):
                drives.append({'name': drive, 'path': drive})
    else:
        drives.append({'name': '/', 'path': '/'})
    return {'drives': drives}


@app.get('/api/folders/children')
async def folder_children(root: str = Query(...)):
    root_path = Path(root)
    if not root_path.exists():
        raise HTTPException(404, 'Folder not found')
    try:
        folders = []
        for p in sorted(root_path.iterdir(), key=lambda x: x.name.lower()):
            if p.is_dir() and not p.name.startswith('.'):
                folders.append({'name': p.name or str(p), 'path': str(p.resolve())})
        parent = str(root_path.parent.resolve()) if root_path.parent and root_path.parent != root_path else ''
        return {'root': str(root_path.resolve()), 'parent': parent, 'folders': folders}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get('/api/folders/files')
async def folder_files(root: str = Query(...), pattern: str = Query('*.exe')):
    root_path = Path(root)
    if not root_path.exists():
        raise HTTPException(404, 'Folder not found')
    try:
        files = []
        patterns = [p.strip() for p in str(pattern or '*.exe').split(',') if p.strip()] or ['*.exe']
        for p in sorted(root_path.iterdir(), key=lambda x: x.name.lower()):
            if p.name.startswith('.') or not p.is_file():
                continue
            name = p.name.lower()
            matched = False
            for pat in patterns:
                pat = pat.lower().strip()
                if pat.startswith('*.') and name.endswith(pat[1:]):
                    matched = True
                    break
                if pat == '*' or pat == name:
                    matched = True
                    break
            if matched:
                files.append({'name': p.name, 'path': str(p.resolve())})
        parent = str(root_path.parent.resolve()) if root_path.parent and root_path.parent != root_path else ''
        return {'root': str(root_path.resolve()), 'parent': parent, 'files': files}
    except Exception as e:
        raise HTTPException(500, str(e))
@app.get("/api/docs/{addon_id}/{index}")
async def addon_doc(addon_id: str, index: int):
    addon = await storage.get_addon(addon_id)
    if not addon or index < 0 or index >= len(addon.docs):
        raise HTTPException(404)
    doc = addon.docs[index]
    path = Path(doc.path)
    if not path.exists():
        raise HTTPException(404)
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Content-Disposition": f"inline; filename=\"{path.name}\"", "Cache-Control": "no-store"}
    return FileResponse(str(path), media_type=media, headers=headers)

class AircraftFetchRequest(BaseModel):
    manufacturer: str
    model: str
    manufacturer_full_name: Optional[str] = None


class AirportFetchRequest(BaseModel):
    icao: Optional[str] = None
    faa_id: Optional[str] = None
    title: Optional[str] = None


class LayoutExportRequest(BaseModel):
    addon_id: str
    title: Optional[str] = None
    icao: Optional[str] = None
    point: Optional[dict] = None
    layout: Optional[dict] = None


class MapResolveRequest(BaseModel):
    addon_id: str


class MapResolveBatchRequest(BaseModel):
    addon_ids: list[str]


class GlobalMapCandidatePoint(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None


class GlobalMapCandidateItem(BaseModel):
    addon_id: str
    title: Optional[str] = None
    addon_type: Optional[str] = None
    subtype: Optional[str] = None
    icao: Optional[str] = None
    faa_id: Optional[str] = None
    point: Optional[GlobalMapCandidatePoint] = None
    polygon: Optional[list[dict]] = None


class GlobalMapResolveRequest(BaseModel):
    items: list[GlobalMapCandidateItem]


@app.post("/api/aircraft/fetch-specs")
async def aircraft_fetch_specs(body: AircraftFetchRequest):
    try:
        from aircraft_data import fetch_aircraft_specs as wiki_fetch_aircraft_specs
        lookup_mfr = body.manufacturer_full_name or body.manufacturer
        data = wiki_fetch_aircraft_specs(lookup_mfr, body.model)
        return {
            "manufacturer": body.manufacturer,
            "manufacturer_full_name": data.get("manufacturer_full_name") or data.get("mfr") or lookup_mfr,
            "model": data.get("model") or body.model,
            "category": data.get("category") or data.get("wiki_title") or "",
            "engine": data.get("engine") or "",
            "engine_type": data.get("engine_type") or "",
            "max_speed": data.get("max_speed") or "",
            "cruise": data.get("cruise") or "",
            "range": data.get("range") or "",
            "range_nm": data.get("range_nm"),
            "ceiling": data.get("ceiling") or "",
            "seats": data.get("seats") or "",
            "mtow": data.get("mtow") or "",
            "introduced": data.get("introduced") or data.get("first_flight") or "",
            "wiki_title": data.get("wiki_title") or "",
            "wiki_url": data.get("wiki_url") or "",
            "wiki_summary": data.get("wiki_summary") or "",
            "source": "Wikipedia",
        }
    except Exception as e:
        raise HTTPException(502, f"Wikipedia lookup failed: {e}")


def _wiki_request(params: dict) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("origin", "*")
    resp = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=20, headers={"User-Agent": "MSFS-Hangar/2.0"})
    resp.raise_for_status()
    return resp.json()


def _extract_infobox_field(html: str, keys: list[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("table.infobox tr"):
        th = row.find("th")
        td = row.find("td")
        if not th or not td:
            continue
        label = th.get_text(" ", strip=True).lower()
        if any(k in label for k in keys):
            return re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
    return ""

US_STATE_TO_ABBR = {
    'alabama':'AL','alaska':'AK','arizona':'AZ','arkansas':'AR','california':'CA','colorado':'CO','connecticut':'CT','delaware':'DE',
    'district of columbia':'DC','florida':'FL','georgia':'GA','hawaii':'HI','idaho':'ID','illinois':'IL','indiana':'IN','iowa':'IA',
    'kansas':'KS','kentucky':'KY','louisiana':'LA','maine':'ME','maryland':'MD','massachusetts':'MA','michigan':'MI','minnesota':'MN',
    'mississippi':'MS','missouri':'MO','montana':'MT','nebraska':'NE','nevada':'NV','new hampshire':'NH','new jersey':'NJ','new mexico':'NM',
    'new york':'NY','north carolina':'NC','north dakota':'ND','ohio':'OH','oklahoma':'OK','oregon':'OR','pennsylvania':'PA','rhode island':'RI',
    'south carolina':'SC','south dakota':'SD','tennessee':'TN','texas':'TX','utah':'UT','vermont':'VT','virginia':'VA','washington':'WA',
    'west virginia':'WV','wisconsin':'WI','wyoming':'WY'
}

CA_PROVINCE_TO_ABBR = {
    'alberta':'AB','british columbia':'BC','manitoba':'MB','new brunswick':'NB','newfoundland and labrador':'NL','newfoundland':'NL','nova scotia':'NS',
    'northwest territories':'NT','nunavut':'NU','ontario':'ON','prince edward island':'PE','quebec':'QC','saskatchewan':'SK','yukon':'YT'
}

def _normalize_airport_region_fields(data: dict) -> dict:
    out = dict(data or {})
    country = str(out.get('country') or '').strip()
    state = str(out.get('state') or '').strip()
    province = str(out.get('province') or '').strip()
    if country == 'United States' and state:
        out['state'] = US_STATE_TO_ABBR.get(state.lower(), state if len(state) == 2 else state)
        if len(str(out.get('state') or '')) == 2:
            out['region'] = out.get('region') or out['state']
    if country == 'Canada' and province:
        out['province'] = CA_PROVINCE_TO_ABBR.get(province.lower(), province)
    return out


def _airport_lookup_queries(icao: str = '', faa_id: str = '', title: str = '', municipality: str = '', country: str = '') -> list[str]:
    queries = []
    icao = (icao or '').strip().upper()
    faa_id = (faa_id or '').strip().upper()
    title = (title or '').strip()
    clean_title = _clean_airport_name_for_lookup(title)
    preferred = []
    if icao and clean_title:
        preferred.extend([f"{icao} {clean_title}", f"{icao} {clean_title} airport", f"{icao} {clean_title} international airport"])
    if faa_id and clean_title and faa_id != icao:
        preferred.extend([f"{faa_id} {clean_title}", f"{faa_id} {clean_title} airport"])
    if clean_title:
        preferred.extend([clean_title, f"{clean_title} airport", f"{clean_title} international airport"])
    if title and title != clean_title:
        preferred.extend([title, f"{title} airport"])
    queries.extend(preferred)
    for candidate in [clean_title, title]:
        candidate = (candidate or '').strip()
        if not candidate:
            continue
        if municipality:
            queries.append(f"{candidate} airport {municipality}")
        if municipality and country:
            queries.append(f"{candidate} airport {municipality} {country}")
        elif country:
            queries.append(f"{candidate} airport {country}")
    if icao:
        queries.extend([f"{icao} airport", icao])
    if faa_id and faa_id != icao:
        queries.extend([f"{faa_id} airport", faa_id])
    seen = set()
    out = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            out.append(q)
            seen.add(key)
    return out


def _airport_wiki_candidate_score(candidate: str, icao: str = '', faa_id: str = '', title: str = '') -> int:
    t = (candidate or '').strip().lower()
    score = 0
    if not t:
        return score
    clean_title = (_clean_airport_name_for_lookup(title) or title or '').strip().lower()
    if clean_title and t == clean_title:
        score += 220
    if clean_title and clean_title in t:
        score += 140
    if icao and re.search(rf'{re.escape(icao.lower())}', t):
        score += 140
    if faa_id and re.search(rf'{re.escape(faa_id.lower())}', t):
        score += 90
    if 'airport' in t:
        score += 30
    title_tokens = [tok for tok in re.split(r'[^a-z0-9]+', clean_title) if len(tok) > 2]
    coverage = sum(1 for tok in title_tokens if tok in t)
    score += coverage * 16
    if title_tokens and coverage == len(title_tokens):
        score += 80
    if 'international airport' in t:
        score += 20
    return score


def _lookup_airport_coords_by_name(icao: str = '', faa_id: str = '', title: str = '', municipality: str = '', country: str = '') -> dict:
    headers = {"User-Agent": "MSFSHangar/2.0 (local desktop app)", "Accept-Language": "en-US,en;q=0.9"}
    for q in _airport_lookup_queries(icao, faa_id, title, municipality, country):
        try:
            resp = requests.get('https://nominatim.openstreetmap.org/search', params={"q": q, "format": "jsonv2", "limit": 1}, timeout=12, headers=headers)
            resp.raise_for_status()
            rows = resp.json() or []
            if rows:
                row = rows[0]
                if _coord_valid(row.get('lat'), row.get('lon')):
                    return {
                        'lat': float(row['lat']),
                        'lon': float(row['lon']),
                        'name': row.get('display_name') or title or icao,
                        'source': 'Nominatim',
                        'geocode_query': q,
                    }
        except Exception:
            continue
    return {}


def _fetch_airport_data_sync(icao: str = '', faa_id: str = '', title: str = '') -> dict:
    icao = (icao or '').strip().upper()
    faa_id = (faa_id or '').strip().upper()
    title = (title or '').strip()
    csv_data = {}
    primary_code = icao or faa_id
    if len(primary_code) >= 3:
        try:
            from airports import lookup_airport_by_code
            csv_data = lookup_airport_by_code(primary_code) or {}
        except Exception:
            csv_data = {}
    wiki_extra = {}
    wiki_title = ''
    wiki_url = ''
    for q in _airport_lookup_queries(icao, faa_id, title):
        try:
            search = _wiki_request({"action": "opensearch", "search": q, "limit": 8, "namespace": 0})
            titles = search[1] if isinstance(search, list) and len(search) > 1 else []
            urls = search[3] if isinstance(search, list) and len(search) > 3 else []
            if titles:
                ranked = sorted([( _airport_wiki_candidate_score(t, icao=icao, faa_id=faa_id, title=title), idx, t) for idx, t in enumerate(titles)], reverse=True)
                best = ranked[0] if ranked else None
                if best and best[0] > 0:
                    idx = best[1]
                    wiki_title = titles[idx]
                    wiki_url = urls[idx] if idx < len(urls) and urls[idx] else (f"https://en.wikipedia.org/wiki/{quote(wiki_title.replace(' ', '_'))}" if wiki_title else '')
                    break
        except Exception:
            continue
    if wiki_title:
        try:
            parse = _wiki_request({"action": "parse", "page": wiki_title, "prop": "text"})
            html = ((((parse or {}).get("parse") or {}).get("text") or {}).get("*")) or ""
            wiki_extra = {
                "first_opened": _extract_infobox_field(html, ["opened", "first opened", "opening"]),
                "faa_id": _extract_infobox_field(html, ["faa", "faa lid", "faa airport identifier", "faa identifier"]),
                "hub_airlines": _extract_infobox_field(html, ["hub for", "focus city for", "operating base for", "airline hubs"]),
                "passenger_count": _extract_infobox_field(html, ["passengers", "passenger traffic", "annual passenger traffic"]),
                "cargo_count": _extract_infobox_field(html, ["cargo", "cargo throughput"]),
                "us_rank": _extract_infobox_field(html, ["rank in the united states", "u.s. rank", "us rank"]),
                "world_rank": _extract_infobox_field(html, ["world rank", "global rank", "rank worldwide"]),
                "wiki_title": wiki_title,
                "wiki_url": wiki_url,
            }
            q = _wiki_request({"action": "query", "prop": "extracts", "titles": wiki_title, "exintro": True, "explaintext": True, "exsentences": 4})
            pages = (((q or {}).get("query") or {}).get("pages") or {})
            page = next(iter(pages.values())) if pages else {}
            wiki_extra["wiki_summary"] = page.get("extract", "")
            if not wiki_extra.get('name'):
                wiki_extra['name'] = wiki_title
        except Exception:
            pass
    merged = {**csv_data, **wiki_extra}
    if not _coord_valid(merged.get('lat'), merged.get('lon')):
        coords = _lookup_airport_coords_by_name(icao=icao, faa_id=faa_id, title=title or merged.get('name') or wiki_title, municipality=merged.get('municipality') or merged.get('city') or '', country=merged.get('country') or '')
        if coords:
            merged['lat'] = coords.get('lat')
            merged['lon'] = coords.get('lon')
            merged['geocode_query'] = coords.get('geocode_query')
    if not merged.get('name') and title:
        merged['name'] = _clean_airport_name_for_lookup(title) or title
    if icao and not merged.get('icao'):
        merged['icao'] = icao
    if not merged.get('faa_id') and faa_id:
        merged['faa_id'] = faa_id
    src_parts = []
    if csv_data:
        src_parts.append('OurAirports')
    if wiki_extra:
        src_parts.append('Wikipedia')
    if merged.get('geocode_query'):
        src_parts.append('Nominatim')
    merged['source'] = ' + '.join(src_parts) if src_parts else 'Airport Lookup'
    return _normalize_airport_region_fields(merged)



def _build_airport_prompt(icao: str = '', faa_id: str = '', title: str = '', response_language: str = 'English') -> str:
    ident = ' / '.join([x for x in [icao, faa_id] if x]).strip(' /')
    subject = ' '.join([ident, title]).strip() or title or ident
    return f"""Research the real-world airport identified by: {subject}

Return one valid JSON object only with these keys:
summary_html, airport_type, municipality, city, country, state, province, region, continent, first_opened, passenger_count, passenger_year, cargo_count, hub_airlines, world_rank, us_rank, commercial, source_name

Requirements:
- summary_html should be 1 to 2 rich paragraphs describing the airport, its role, and notable traffic significance.
- airport_type should be a plain-language type such as International, Regional, General Aviation, Military, Cargo, or Heliport.
- commercial should be yes or no.
- passenger_count should include the number only when possible and passenger_year should include the year tied to that number.
- hub_airlines should name airlines if the airport is a hub or focus city.
- prefer official airport pages, Wikipedia, airport operator pages, and reputable aviation references.
- if a field is unknown, return an empty string.
- write the summary in {response_language}.
"""


async def _run_provider_airport_lookup(provider: str, settings: dict, icao: str, faa_id: str, title: str, *, gemini_model: Optional[str] = None, openai_model: Optional[str] = None, claude_model: Optional[str] = None):
    provider = (provider or _selected_ai_provider(settings)).lower().strip()
    prompt = _build_airport_prompt(icao=icao, faa_id=faa_id, title=title, response_language=_preferred_language(settings))
    parsed, sources, raw = await asyncio.to_thread(lambda p=prompt, prv=provider: _provider_generate_json(prv, p, settings, use_search=True, gemini_model=(gemini_model or _selected_gemini_interactive_model(settings)), openai_model=(openai_model or _selected_openai_model(settings)), claude_model=(claude_model or _selected_claude_model(settings))))
    if not parsed:
        parsed = _extract_json_pairs_fallback(raw, ['summary_html','airport_type','municipality','city','country','state','province','region','continent','first_opened','passenger_count','passenger_year','cargo_count','hub_airlines','world_rank','us_rank','commercial','source_name'])
    return parsed or {}, sources, raw


@app.post("/api/airport/fetch-data")
async def airport_fetch_data(body: AirportFetchRequest):
    icao = (body.icao or "").strip().upper()
    faa_id = (body.faa_id or "").strip().upper()
    title = (body.title or "").strip()
    if len(icao) < 3 and len(faa_id) < 2 and len(title) < 2:
        raise HTTPException(400, "Airport ICAO, FAA ID, or title required")
    strict_title = '' if (icao or faa_id) else title
    merged = _fetch_airport_data_sync(icao=icao, faa_id=faa_id, title=strict_title)
    settings = await storage.get_all_settings()
    provider = _selected_ai_provider(settings)
    try:
        if (provider == 'gemini' and settings.get('google_api_key')) or (provider == 'openai' and settings.get('openai_key')) or (provider == 'claude' and settings.get('claude_api_key')):
            parsed, sources, _raw = await _run_provider_airport_lookup(provider, settings, icao, faa_id, ('' if (icao or faa_id) else (title or merged.get('name') or '')))
            if parsed:
                merged['airport_type'] = parsed.get('airport_type') or merged.get('airport_type')
                merged['municipality'] = parsed.get('municipality') or merged.get('municipality') or merged.get('city')
                merged['city'] = parsed.get('city') or merged.get('city')
                merged['country'] = parsed.get('country') or merged.get('country')
                merged['state'] = parsed.get('state') or merged.get('state')
                merged['province'] = parsed.get('province') or merged.get('province')
                merged['region'] = parsed.get('region') or merged.get('region')
                merged['continent'] = parsed.get('continent') or merged.get('continent')
                merged['first_opened'] = parsed.get('first_opened') or merged.get('first_opened')
                merged['passenger_count'] = parsed.get('passenger_count') or merged.get('passenger_count')
                merged['passenger_year'] = parsed.get('passenger_year') or merged.get('passenger_year')
                merged['cargo_count'] = parsed.get('cargo_count') or merged.get('cargo_count')
                merged['hub_airlines'] = parsed.get('hub_airlines') or merged.get('hub_airlines')
                merged['world_rank'] = parsed.get('world_rank') or merged.get('world_rank')
                merged['us_rank'] = parsed.get('us_rank') or merged.get('us_rank')
                if parsed.get('summary_html'):
                    merged['wiki_summary'] = parsed.get('summary_html')
                src = parsed.get('source_name') or provider.title()
                if sources:
                    src += ' + ' + ', '.join(sources[:3])
                merged['source'] = src
    except Exception as exc:
        log.warning('AI airport lookup failed icao=%s faa_id=%s title=%s error=%s', icao, faa_id, title, exc)
    return _normalize_airport_region_fields(merged)


class PlaceSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


@app.post("/api/map/search-place")
async def map_search_place(body: PlaceSearchRequest):
    q = (body.query or '').strip()
    if len(q) < 2:
        raise HTTPException(400, 'Search text required')
    limit = max(1, min(int(body.limit or 5), 10))
    headers = {"User-Agent": "MSFSHangar/2.0 (local desktop app)", "Accept-Language": "en-US,en;q=0.9"}
    try:
        resp = requests.get('https://nominatim.openstreetmap.org/search', params={"q": q, "format": "jsonv2", "limit": limit}, timeout=12, headers=headers)
        resp.raise_for_status()
        rows = resp.json() or []
    except Exception as e:
        raise HTTPException(502, f'Place search failed: {e}')
    out = []
    for row in rows:
        try:
            lat = float(row.get('lat'))
            lon = float(row.get('lon'))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
        except Exception:
            continue
        out.append({
            'label': row.get('display_name') or q,
            'lat': lat,
            'lon': lon,
            'type': row.get('type') or row.get('class') or '',
        })
    return {'results': out}


def _coord_valid(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
        if abs(lat) < 1e-9 and abs(lon) < 1e-9:
            return False
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except Exception:
        return False


def _clean_airport_name_for_lookup(name: str) -> str:
    n = (name or '').strip()
    if not n:
        return ''
    prefixes = ['aerosoft', 'iniBuilds', 'inibuilds', 'orbx', 'pmdg', 'flightbeam', 'mk studios', 'drzewiecki design', 'latinvfr', 'fsdreamteam', 'justsim', 'feelthere']
    lower = n.lower()
    for pref in prefixes:
        if lower.startswith(pref + ' '):
            n = n[len(pref):].strip(' -:_')
            lower = n.lower()
            break
    parts = [seg.strip() for seg in n.replace('|', ' - ').split(' - ') if seg.strip()]
    for seg in parts:
        s = seg.lower()
        if 'airport' in s or 'intl' in s or 'international' in s or 'field' in s or 'airfield' in s:
            return seg
    return parts[0] if parts else n


def _valid_polygon_points(points):
    out = []
    if not isinstance(points, list):
        return out
    for p in points:
        lat = (p or {}).get('lat') if isinstance(p, dict) else None
        lon = (p or {}).get('lon') if isinstance(p, dict) else None
        if _coord_valid(lat, lon):
            out.append({'lat': float(lat), 'lon': float(lon)})
    return out


def _centroid(points):
    if not points:
        return None
    lat = sum(float(p['lat']) for p in points) / len(points)
    lon = sum(float(p['lon']) for p in points) / len(points)
    return {'lat': lat, 'lon': lon}


def _resolve_addon_coords_sync(addon):
    if not addon:
        return None
    polygon = _valid_polygon_points(getattr(getattr(addon, 'usr', None), 'map_polygon', None))
    if _coord_valid(getattr(addon, 'lat', None), getattr(addon, 'lon', None)):
        return {'point': {'lat': float(addon.lat), 'lon': float(addon.lon)}, 'source': 'stored', 'polygon': polygon}
    if getattr(addon, 'usr', None) and _coord_valid(getattr(addon.usr, 'map_lat', None), getattr(addon.usr, 'map_lon', None)):
        return {'point': {'lat': float(addon.usr.map_lat), 'lon': float(addon.usr.map_lon)}, 'source': 'user', 'polygon': polygon}
    if getattr(addon, 'rw', None) and _coord_valid(getattr(addon.rw, 'lat', None), getattr(addon.rw, 'lon', None)):
        return {'point': {'lat': float(addon.rw.lat), 'lon': float(addon.rw.lon)}, 'source': getattr(addon.rw, 'source', '') or 'stored', 'polygon': polygon}

    icao = ((getattr(addon, 'rw', None) and getattr(addon.rw, 'icao', None)) or '').strip().upper()
    faa_id = ((getattr(addon, 'rw', None) and getattr(addon.rw, 'faa_id', None)) or '').strip().upper()
    primary_code = icao or faa_id
    if primary_code and len(primary_code) >= 3:
        try:
            from airports import lookup_airport_by_code
            csv_data = lookup_airport_by_code(primary_code) or {}
            if _coord_valid(csv_data.get('lat'), csv_data.get('lon')):
                return {'point': {'lat': float(csv_data['lat']), 'lon': float(csv_data['lon'])}, 'source': 'OurAirports', 'icao': csv_data.get('icao') or icao, 'faa_id': csv_data.get('faa_id') or faa_id, 'polygon': polygon}
        except Exception:
            pass

    title = (getattr(addon, 'title', '') or '').strip()
    clean_title = _clean_airport_name_for_lookup(title)
    pkg = (getattr(addon, 'package_name', '') or '').strip().replace('_', ' ')
    municipality = ((getattr(addon, 'rw', None) and (getattr(addon.rw, 'municipality', None) or getattr(addon.rw, 'city', None))) or '').strip()
    country = ((getattr(addon, 'rw', None) and getattr(addon.rw, 'country', None)) or '').strip()
    queries = []
    if icao:
        queries.append(f'{icao} airport')
    if faa_id and faa_id != icao:
        queries.append(f'{faa_id} airport')
    if clean_title:
        queries.append(clean_title)
        if (getattr(addon, 'type', '') or '') == 'Airport':
            queries.append(f'{clean_title} airport')
            if municipality:
                queries.append(f'{clean_title} airport {municipality}')
            if municipality and country:
                queries.append(f'{clean_title} airport {municipality} {country}')
    if title and title not in queries:
        queries.append(title)
    if pkg and pkg not in queries:
        queries.append(pkg)

    seen = set()
    headers = {"User-Agent": "MSFSHangar/2.0 (local desktop app)", "Accept-Language": "en-US,en;q=0.9"}
    for q in queries:
        key = q.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            resp = requests.get('https://nominatim.openstreetmap.org/search', params={"q": q, "format": "jsonv2", "limit": 1}, timeout=12, headers=headers)
            resp.raise_for_status()
            rows = resp.json() or []
            if rows:
                row = rows[0]
                if _coord_valid(row.get('lat'), row.get('lon')):
                    return {'point': {'lat': float(row['lat']), 'lon': float(row['lon'])}, 'source': 'Nominatim', 'query': q, 'icao': icao, 'faa_id': faa_id, 'polygon': polygon}
        except Exception:
            continue

    if polygon:
        center = _centroid(polygon)
        if center and _coord_valid(center['lat'], center['lon']):
            return {'point': center, 'source': 'polygon-centroid', 'polygon': polygon}
    return None




def _resolve_global_marker_item(candidate):
    addon_id = str(getattr(candidate, 'addon_id', '') or '').strip()
    title = str(getattr(candidate, 'title', '') or '').strip()
    addon_type = str(getattr(candidate, 'addon_type', '') or '').strip()
    subtype = str(getattr(candidate, 'subtype', '') or '').strip()
    icao = str(getattr(candidate, 'icao', '') or '').strip().upper()
    faa_id = str(getattr(candidate, 'faa_id', '') or '').strip().upper()
    point = getattr(candidate, 'point', None)
    polygon = _valid_polygon_points(getattr(candidate, 'polygon', None))
    if point and _coord_valid(getattr(point, 'lat', None), getattr(point, 'lon', None)):
        return {
            'addon_id': addon_id, 'title': title, 'type': addon_type, 'subtype': subtype, 'icao': icao, 'faa_id': faa_id,
            'point': {'lat': float(point.lat), 'lon': float(point.lon)}, 'polygon': polygon, 'source': 'frontend-candidate'
        }
    if polygon:
        center = _centroid(polygon)
        if center and _coord_valid(center['lat'], center['lon']):
            return {
                'addon_id': addon_id, 'title': title, 'type': addon_type, 'subtype': subtype, 'icao': icao, 'faa_id': faa_id,
                'point': {'lat': float(center['lat']), 'lon': float(center['lon'])}, 'polygon': polygon, 'source': 'frontend-polygon'
            }
    return None


@app.post('/api/map/global-markers')
async def map_global_markers(body: GlobalMapResolveRequest):
    items = []
    unresolved = []
    for cand in (body.items or []):
        resolved = _resolve_global_marker_item(cand)
        if not resolved:
            addon = await storage.get_addon(str(getattr(cand, 'addon_id', '') or ''))
            if addon:
                resolved2 = _resolve_addon_coords_sync(addon)
                if resolved2 and resolved2.get('point'):
                    resolved = {
                        'addon_id': str(addon.id),
                        'title': addon.title,
                        'type': getattr(cand, 'addon_type', None) or addon.type,
                        'subtype': getattr(cand, 'subtype', None) or addon.sub,
                        'icao': ((addon.rw and addon.rw.icao) or getattr(cand, 'icao', None) or ''),
                        'faa_id': ((addon.rw and getattr(addon.rw, 'faa_id', None)) or getattr(cand, 'faa_id', None) or ''),
                        'point': resolved2.get('point'),
                        'polygon': resolved2.get('polygon') or [],
                        'source': resolved2.get('source', ''),
                    }
            if not resolved:
                unresolved.append({'addon_id': str(getattr(cand, 'addon_id', '') or ''), 'title': str(getattr(cand, 'title', '') or ''), 'icao': str(getattr(cand, 'icao', '') or ''), 'faa_id': str(getattr(cand, 'faa_id', '') or ''), 'reason': 'unresolved'})
                continue
        items.append(resolved)
    return {'items': items, 'unresolved': unresolved, 'count': len(items)}
@app.post("/api/map/resolve-addon-coords")
async def map_resolve_addon_coords(body: MapResolveRequest):
    addon = await storage.get_addon(body.addon_id)
    if not addon:
        raise HTTPException(404, 'Add-on not found')
    resolved = _resolve_addon_coords_sync(addon)
    if not resolved:
        raise HTTPException(404, 'No coordinates resolved for this add-on')
    point = resolved.get('point') or {}
    payload = {'lat': point.get('lat'), 'lon': point.get('lon'), 'source': resolved.get('source', '')}
    if resolved.get('icao'):
        payload['icao'] = resolved['icao']
    if resolved.get('faa_id'):
        payload['faa_id'] = resolved['faa_id']
    if resolved.get('query'):
        payload['query'] = resolved['query']
    if resolved.get('polygon'):
        payload['polygon'] = resolved['polygon']
    return payload


@app.post("/api/map/resolve-addons-coords")
async def map_resolve_addons_coords(body: MapResolveBatchRequest):
    addon_ids = [str(x).strip() for x in (body.addon_ids or []) if str(x).strip()]
    items = []
    unresolved = []
    for addon_id in addon_ids:
        addon = await storage.get_addon(addon_id)
        if not addon:
            unresolved.append({'addon_id': addon_id, 'reason': 'not-found'})
            continue
        resolved = _resolve_addon_coords_sync(addon)
        if not resolved:
            unresolved.append({'addon_id': addon_id, 'reason': 'unresolved'})
            continue
        items.append({
            'addon_id': addon_id,
            'point': resolved.get('point'),
            'polygon': resolved.get('polygon') or [],
            'source': resolved.get('source', ''),
            'icao': resolved.get('icao', ''),
            'faa_id': resolved.get('faa_id', ''),
            'query': resolved.get('query', ''),
        })
    return {'items': items, 'unresolved': unresolved, 'count': len(items)}


# --- Research helpers ---

_MODERN_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def _fetch_url(url: str, timeout: int = 30) -> tuple[str, str]:
    resp = requests.get(url, timeout=timeout, headers=_MODERN_BROWSER_HEADERS)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "text" in content_type or "html" in content_type:
        return resp.text, content_type
    return resp.content.decode("utf-8", errors="replace"), content_type


def _postmessage_script(current_url: str) -> str:
    url_json = json.dumps(current_url)
    return """<script>
(function(){{
  function report(state){{
    try{{ parent.postMessage(Object.assign({{type:'hangar-browser-state'}}, state||{{url:{u}, title:document.title||{u}}}), '*'); }}catch(e){{}}
  }}
  window.addEventListener('load', function(){{ report(); }});
  document.addEventListener('DOMContentLoaded', function(){{ report(); }});
  document.addEventListener('click', function(ev){{
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if(a){{
      setTimeout(function(){{ report({{url:a.getAttribute('data-final-url')||a.href||{u}, title:(a.textContent||document.title||'').trim()}}); }}, 0);
    }}
  }}, true);
}})();
</script>""".format(u=url_json)


def _safe_browse_url(url: str) -> str:
    return "/api/research/open?url=" + quote(url, safe="")


def _proxy_html(url: str) -> str:
    parsed = urlparse(url)
    html, _ = _fetch_url(url, timeout=20)
    soup = BeautifulSoup(html, "html.parser")
    keep_scripts = any(host in parsed.netloc for host in ["skyvector.com"])
    if not keep_scripts:
        for tag in soup(["script", "noscript"]):
            tag.decompose()
    for meta in soup.select("meta[http-equiv]"):
        meta.decompose()
    for base in soup.select("base"):
        base.decompose()
    for form in soup.select("form[action]"):
        action = form.get("action") or url
        abs_action = urljoin(url, action)
        form["action"] = _safe_browse_url(abs_action)
        form["method"] = "get"
        form["target"] = "_self"
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if href.startswith("#"):
            continue
        abs_href = urljoin(url, href)
        if abs_href.startswith(("http://", "https://")):
            a["href"] = _safe_browse_url(abs_href)
            a["target"] = "_self"
            a["data-final-url"] = abs_href
    for img in soup.select("img[src]"):
        img["src"] = urljoin(url, img.get("src") or "")
    for tag in soup.select("[srcset]"):
        tag.attrs.pop("srcset", None)
    head = soup.head or soup.new_tag("head")
    head.insert(0, soup.new_tag("base", href=url))
    style = soup.new_tag("style")
    style.string = "body{max-width:none;margin:0;padding:18px;font-family:Segoe UI,Arial,sans-serif;line-height:1.5} img,video{max-width:100%;height:auto} a{color:#2563eb} iframe{max-width:100%}"
    head.append(style)
    bridge = BeautifulSoup(_postmessage_script(url), 'html.parser')
    head.append(bridge)
    if not soup.head:
        soup.insert(0, head)
    return str(soup)


def _query_tokens(query: str) -> list[str]:
    return [t for t in re.split(r"[^A-Za-z0-9]+", (query or '').lower()) if len(t) > 1]


_SEARCH_STOPWORDS = {
    'the','and','for','with','from','that','this',
    'guide','official','product','addon','site'
}


def _significant_tokens(query: str) -> list[str]:
    toks = []
    for tok in _query_tokens(query):
        if tok in _SEARCH_STOPWORDS:
            continue
        toks.append(tok)
    return toks or _query_tokens(query)


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def _normalized_phrase(query: str) -> str:
    folded = _ascii_fold((query or '').replace('"', ' '))
    return re.sub(r"\s+", " ", folded.strip()).lower()


_KNOWN_VENDORS = [
    'just flight','aerosoft','sofly','inibuilds','orbx','pmdg','simmarket','flytampa',
    'flightbeam','blacksquare','black square','fsreborn','parallel 42','milviz','fss','got friends'
]


def _remove_search_operators(query: str) -> str:
    q = re.sub(r'\bsite\s*:\s*[^\s]+', ' ', query or '', flags=re.I)
    q = re.sub(r'\b(inurl|intitle)\s*:\s*[^\s]+', ' ', q, flags=re.I)
    return re.sub(r'\s+', ' ', q).strip()


def _strip_known_vendors(query: str) -> str:
    q = ' ' + (query or '').strip() + ' '
    for vendor in _KNOWN_VENDORS:
        q = re.sub(r'(?i)(^|\s)' + re.escape(vendor) + r'(\s|$)', ' ', q)
    return re.sub(r'\s+', ' ', q).strip()


def _focus_query(query: str, context: str = 'web') -> str:
    q = _remove_search_operators(query or '')
    if context == 'research':
        # Preserve publisher/vendor and addon wording for product-focused searches.
        q = re.sub(r'(?i)\b(videos?|youtube)\b', ' ', q)
        q = re.sub(r'\s+', ' ', q).strip()
        return q or _remove_search_operators(query or '').strip()

    q = _strip_known_vendors(q)
    q = re.sub(r'(?i)\b(msfs|microsoft flight simulator|flight simulator|review|reviews|video|videos|guide|preview|official|edition|pack|addon)\b', ' ', q)
    if context == 'airport':
        q = re.sub(r'(?i)\b(international|municipal|airfield|aerodrome|msfs|2020|2024)\b', ' ', q)
    if context == 'aircraft':
        q = re.sub(r'(?i)\b(aircraft|airplane|plane|msfs|2020|2024)\b', ' ', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q or _remove_search_operators(query or '').strip()

def _youtube_mode(query: str, context: str = 'web') -> bool:
    q = (query or '').lower()
    return context == 'video' or 'site:youtube.com' in q or 'site:youtu.be' in q or q.strip().startswith('youtube ')


def _youtube_search_url(query: str) -> str:
    base = _remove_search_operators(query or '')
    base = re.sub(r'(?i)\byoutube\b', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    return 'https://www.youtube.com/results?search_query=' + quote(base)


def _is_probably_english_result(title: str, url: str, snippet: str = '') -> bool:
    host = (urlparse(url).netloc or '').lower()
    path = (urlparse(url).path or '').lower()
    lowered = f"{title} {snippet} {host} {path}".lower()
    bad_tlds = ('.fr', '.de', '.es', '.it', '.pt', '.ru', '.jp', '.cn', '.kr', '.pl', '.cz', '.hu', '.tr')
    if any(host.endswith(tld) for tld in bad_tlds):
        return False
    if re.search(r'/(fr|de|es|it|pt|ru|jp|cn|kr|pl)(/|$)', path):
        return False
    bad_flags = [' deutsch', 'français', 'español', 'italiano', 'русский', '日本語', '中文', 'português']
    if any(flag in lowered for flag in bad_flags):
        return False
    sample = (title or '') + ' ' + (snippet or '')
    if sample:
        ascii_ratio = (sum(1 for ch in sample if ord(ch) < 128) / max(len(sample), 1))
        if ascii_ratio < 0.85:
            return False
    return True


def _domain_score(host: str, context: str = 'web') -> int:
    host = (host or '').lower()
    research = ['flightsim.to','justflight.com','inibuilds.com','forum.inibuilds.com','simmarket.com','orbxdirect.com','orbx.com','pmdg.com','aerosoft.com','forums.flightsimulator.com','avsim.com','fselite.net','msfsaddons.com','thresholdx.net','cruiselevel.de','youtube.com']
    common = ['wikipedia.org','ourairports.com','skyvector.com'] + research
    aircraft = ['wikipedia.org','simpleflying.com','skybrary.aero','faa.gov','easa.europa.eu','flightglobal.com','planespotters.net']
    airport = ['skyvector.com','ourairports.com','wikipedia.org','flightaware.com','airnav.com','airport-technology.com','aena.es']
    preferred = common
    if context == 'research':
        preferred = research + common
    elif context == 'aircraft':
        preferred = aircraft + common
    elif context == 'airport':
        preferred = airport + common
    for i, dom in enumerate(preferred):
        if dom in host:
            return max(30 - i, 6)
    if any(bad in host for bad in ['figma.com','pinterest.com','facebook.com','instagram.com','linkedin.com']):
        return -28
    return 0

def _score_result(query: str, title: str, url: str, snippet: str = '', context: str = 'web') -> int:
    sig = _significant_tokens(query)
    phrase = _normalized_phrase(query)
    text = f"{title} {snippet} {url}".lower()
    host = (urlparse(url).netloc or '').lower()
    score = _domain_score(host, context)
    if phrase and phrase in text:
        score += 70
    token_hits = sum(1 for tok in sig if tok in text)
    coverage = token_hits / max(len(sig), 1)
    score += int(coverage * 42)
    score += token_hits * 5
    for a, b in zip(sig, sig[1:]):
        if f"{a} {b}" in text:
            score += 16
    if any(m in text for m in ['airport','aircraft','msfs','flight simulator','aviation','runway','icao','review','preview','addon']):
        score += 10
    if context == 'research':
        if any(term in text for term in ['msfs','microsoft flight simulator','flight simulator','addon','review','preview','2020','2024']):
            score += 18
        elif _domain_score(host, 'research') <= 0:
            score -= 18
        if any(vendor in text for vendor in _KNOWN_VENDORS):
            score += 8
    elif context == 'airport':
        if any(term in text for term in ['airport','icao','runway','skyvector','ourairports','terminal']):
            score += 12
    elif context == 'aircraft':
        if any(term in text for term in ['cruise speed','range','ceiling','specifications','variant','engine','wikipedia']):
            score += 12
    if 'youtube.com' in host or 'youtu.be' in host:
        if any(term in text for term in ['review','preview','video','walkaround','landing']):
            score += 14
        else:
            score += 6
    return score

def _relevance_ok(query: str, title: str, url: str, snippet: str = '', context: str = 'web') -> bool:
    text = _normalized_phrase(f"{title} {snippet} {url}")
    sig = _significant_tokens(query)
    if not sig:
        return True
    hits = [tok for tok in sig if tok in text]
    coverage = len(hits) / max(len(sig), 1)
    host = (urlparse(url).netloc or '').lower()
    exact_phrase = _normalized_phrase(query) in text if _normalized_phrase(query) else False
    preferred = _domain_score(host, context) > 0
    query_lower = _normalized_phrase(query)
    if exact_phrase:
        return True
    if context == 'research':
        if preferred and len(hits) >= 1:
            return True
        if any(term in query_lower for term in ['msfs','review','addon','2020','2024']) and not any(term in text for term in ['msfs','flight simulator','review','addon','2020','2024']):
            return False
        return coverage >= 0.28 or len(hits) >= min(2, len(sig))
    if 'msfs' in query_lower and not any(term in text for term in ['msfs','microsoft flight simulator','flight simulator','simulator']):
        if not preferred and 'youtube' not in host:
            return False
    if preferred and len(hits) >= 1:
        return True
    if len(sig) <= 3:
        return coverage >= 0.28 or len(hits) >= 1
    return coverage >= 0.34 or len(hits) >= min(2, len(sig))

def _rank_results(query: str, results: list[dict], context: str = 'web') -> list[dict]:
    seen = set()
    ranked = []
    for r in results:
        url = _clean_result_url(r.get('url') or '')
        title = r.get('title') or ''
        snippet = r.get('snippet') or ''
        if not url or url in seen:
            continue
        if not _is_probably_english_result(title, url, snippet):
            continue
        if not _relevance_ok(query, title, url, snippet, context):
            continue
        seen.add(url)
        ranked.append({**r, 'url': url, 'display_url': _display_result_url(url), 'score': _score_result(query, title, url, snippet, context)})
    ranked.sort(key=lambda r: (-r.get('score', 0), len(r.get('title') or '')))
    return ranked


def _search_google(query: str, count: int = 24, context: str = 'web') -> list[dict]:
    url = f"https://www.google.com/search?hl=en&gl=us&pws=0&num={count}&q={quote(query)}"
    html, _ = _fetch_url(url, timeout=5)
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.select('a[href]'):
        href = a.get('href') or ''
        if href.startswith('/url?'):
            qs = parse_qs(urlparse(href).query)
            href = unquote((qs.get('q') or [''])[0])
        href = _clean_result_url(href)
        if not href.startswith('http'):
            continue
        host = (urlparse(href).netloc or '').lower()
        if 'google.' in host:
            continue
        title = a.get_text(' ', strip=True)
        if not title:
            h3 = a.select_one('h3')
            title = h3.get_text(' ', strip=True) if h3 else ''
        if not title or href in seen:
            continue
        snippet = ''
        card = a.find_parent('div')
        if card:
            snippet = card.get_text(' ', strip=True)
            if title and snippet.startswith(title):
                snippet = snippet[len(title):].strip(' -–—:')
        seen.add(href)
        out.append({'title': title, 'url': href, 'snippet': snippet[:300], 'source': 'Google'})
        if len(out) >= count:
            break
    return out


def _search_duckduckgo(query: str, context: str = 'web') -> list[dict]:
    out = []
    for search_url in [f"https://html.duckduckgo.com/html/?q={quote(query)}&kl=us-en", f"https://lite.duckduckgo.com/lite/?q={quote(query)}&kl=us-en"]:
        try:
            html, _ = _fetch_url(search_url, timeout=4)
            soup = BeautifulSoup(html, "html.parser")
            seen = set()
            for item in soup.select('.result, .result__body'):
                a = item.select_one('a.result__a, a.result-link, a[href]')
                if not a:
                    continue
                href = a.get('href') or ''
                title = a.get_text(' ', strip=True)
                snippet_el = item.select_one('.result__snippet, .result-snippet')
                snippet = snippet_el.get_text(' ', strip=True) if snippet_el else ''
                if href.startswith('//'):
                    href = 'https:' + href
                if href.startswith('/l/?uddg='):
                    qs = parse_qs(urlparse(href).query)
                    href = unquote((qs.get('uddg') or [''])[0])
                if href.startswith('http') and title and href not in seen and 'duckduckgo.com' not in href:
                    seen.add(href)
                    out.append({'title': title, 'url': href, 'snippet': snippet, 'source': 'DuckDuckGo'})
                if len(out) >= 24:
                    break
            if out:
                return out
        except Exception:
            continue
    return out


def _search_wikipedia(query: str, context: str = 'web') -> list[dict]:
    try:
        payload = _wiki_request({"action": "opensearch", "search": query, "limit": 12, "namespace": 0})
        titles = payload[1] if len(payload) > 1 else []
        urls = payload[3] if len(payload) > 3 else []
        return [{"title": t, "url": u, 'snippet': '', 'source': 'Wikipedia'} for t, u in zip(titles, urls) if t and u]
    except Exception:
        return []


def _clean_result_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or '').lower()
        if 'bing.com' in host and parsed.path.startswith('/ck/a'):
            qs = parse_qs(parsed.query)
            token = (qs.get('u') or [''])[0]
            if token.startswith('a1'):
                payload = token[2:]
                payload += '=' * ((4 - len(payload) % 4) % 4)
                decoded = base64.b64decode(payload).decode('utf-8', errors='ignore')
                return unquote(decoded) or url
            if token:
                return unquote(token)
        if 'duckduckgo.com' in host and parsed.path.startswith('/l/'):
            qs = parse_qs(parsed.query)
            target = (qs.get('uddg') or [''])[0]
            return unquote(target) or url
    except Exception:
        return url
    return url


def _display_result_url(url: str) -> str:
    try:
        cleaned = _clean_result_url(url)
        parsed = urlparse(cleaned)
        path = parsed.path.rstrip('/') or '/'
        short = f"{parsed.netloc}{path}"
        return short[:90] + ('…' if len(short) > 90 else '')
    except Exception:
        return url


def _search_variants(query: str, context: str = 'web') -> list[str]:
    q = (query or '').strip()
    if not q:
        return []
    base = _remove_search_operators(q)
    focus = _focus_query(q, context)
    lower = base.lower()
    variants = []
    if _youtube_mode(q, context):
        core = base or focus
        variants = [f'"{core}" site:youtube.com', f'{core} site:youtube.com']
    elif context == 'research':
        core = base
        stripped = _strip_known_vendors(base)
        variants = [f'"{core}"', core]
        if 'msfs' not in lower and 'flight simulator' not in lower:
            variants += [f'"{core}" MSFS', f'{core} MSFS']
        if 'review' not in lower and 'preview' not in lower:
            variants += [f'"{core}" review', f'{core} addon review']
        if stripped and stripped.lower() != core.lower():
            variants += [f'"{stripped}" MSFS', f'{stripped} MSFS review']
    elif context == 'aircraft':
        core = focus or base
        variants = [f'"{core}"', f'{core} aircraft', f'{core} specifications', f'{core} range speed ceiling']
    elif context == 'airport':
        core = focus or base
        icao = guess_icao(base, known_only=True) if 'guess_icao' in globals() else None
        variants = [f'"{core}" airport', f'{core} airport', f'"{core}" aviation']
        if icao:
            variants += [f'{icao} airport', f'{icao} aviation']
    else:
        variants = [f'"{base}"', base]
    seen = set(); out = []
    for v in variants:
        v = re.sub(r'\s+', ' ', v).strip()
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out[:6]

def _search_cache_get(query: str, context: str = 'web') -> Optional[dict]:
    key = (_SEARCH_CACHE_VERSION, (context or 'web').lower(), (query or '').strip().lower())
    entry = _search_cache.get(key)
    if not entry:
        return None
    if time.time() - entry.get('ts', 0) > _SEARCH_CACHE_TTL:
        _search_cache.pop(key, None)
        return None
    return entry


def _search_cache_set(query: str, context: str, payload: dict):
    key = (_SEARCH_CACHE_VERSION, (context or 'web').lower(), (query or '').strip().lower())
    _search_cache[key] = {'ts': time.time(), **payload}


def _simple_results_html(engine: str, query: str, results: list[dict], page: int = 1, total_pages: int = 1, total_results: int = 0) -> str:
    rows = []
    for r in results:
        title = escape(r.get("title") or r.get("url") or "Result")
        url = _clean_result_url(r.get("url") or "")
        host = escape(urlparse(url).netloc or url)
        display_url = escape(r.get('display_url') or _display_result_url(url))
        snippet = escape(r.get('snippet') or '')
        open_url = _safe_browse_url(url)
        snippet_html = f"<div class='snippet'>{snippet}</div>" if snippet else ""
        rows.append(f"<div class='card'><a class='title' href='{escape(open_url, quote=True)}' data-final-url='{escape(url, quote=True)}' target='_self'>{title}</a><div class='host'>{host}</div><div class='link'>{display_url}</div>{snippet_html}</div>")
    body = "".join(rows) if rows else "<div class='empty'>No results found.</div>"
    pager = f"<div class='pager'>Page {page} of {max(total_pages,1)} • {total_results} results</div>"
    return f"<html><head><meta charset='utf-8'><style>body{{font-family:Segoe UI,Arial,sans-serif;background:#0A1628;color:#F1F5F9;margin:0;padding:18px}} .top{{margin-bottom:14px}} .eng{{color:#94A3B8;font-size:12px;text-transform:uppercase;letter-spacing:.08em}} .q{{font-size:20px;font-weight:700;margin-top:4px}} .card{{background:#0F1E35;border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:12px 14px;margin-bottom:10px}} .title{{color:#8bd3ff;font-size:16px;font-weight:700;text-decoration:none}} .title:hover{{text-decoration:underline}} .host{{color:#34D399;font-size:12px;margin-top:4px}} .link{{color:#94A3B8;font-size:11px;margin-top:4px;word-break:break-all}} .snippet{{color:#CBD5E1;font-size:12px;margin-top:8px;line-height:1.5}} .pager{{color:#94A3B8;font-size:12px;margin-bottom:10px}} .empty{{color:#94A3B8;font-size:14px}}</style>{_postmessage_script('search:'+query)}</head><body><div class='top'><div class='eng'>{escape(engine)} search</div><div class='q'>{escape(query)}</div></div>{pager}{body}</body></html>"




def _extract_product_meta_from_text(text: str) -> dict:
    txt = re.sub(r"\s+", " ", text or " ").strip()
    out: dict[str, object] = {}
    version_patterns = [
        r'version\s*([0-9]+(?:\.[0-9A-Za-z]+){0,4})',
        r'current\s+version\s*[:\-]?\s*([0-9]+(?:\.[0-9A-Za-z]+){0,4})',
        r'updated\s+to\s+([0-9]+(?:\.[0-9A-Za-z]+){0,4})',
        r'v\s*([0-9]+(?:\.[0-9A-Za-z]+){0,4})',
    ]
    for pat in version_patterns:
        m = re.search(pat, txt, re.I)
        if m:
            out['version'] = m.group(1).strip()
            break
    latest_date_patterns = [
        r'\b(?:latest\s+version\s+date|current\s+version\s+date|updated\s+on|last\s+updated|version\s+date|update\s+date)\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        r'\b(?:latest\s+version\s+date|current\s+version\s+date|updated\s+on|last\s+updated|version\s+date|update\s+date)\s*[:\-]?\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',
        r'\b(?:latest\s+version\s+date|current\s+version\s+date|updated\s+on|last\s+updated|version\s+date|update\s+date)\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2})',
    ]
    for pat in latest_date_patterns:
        m = re.search(pat, txt, re.I)
        if m:
            out['latest_version_date'] = m.group(1).strip()
            break
    currency_matches = []
    for pat in [r'USD\s*([0-9]{1,4}(?:[.,][0-9]{2})?)', r'\$\s*([0-9]{1,4}(?:[.,][0-9]{2})?)', r'€\s*([0-9]{1,4}(?:[.,][0-9]{2})?)', r'£\s*([0-9]{1,4}(?:[.,][0-9]{2})?)']:
        for m in re.finditer(pat, txt, re.I):
            try:
                val = float(m.group(1).replace(',', '.'))
                if 0 < val < 1000:
                    currency_matches.append(val)
            except Exception:
                pass
    if currency_matches:
        out['price'] = currency_matches[0]
    date_patterns = [
        r'(?:released?|release date|available(?: from)?|published|launch(?:ed)?)\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        r'(?:released?|release date|available(?: from)?|published|launch(?:ed)?)\s*[:\-]?\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',
        r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',
        r'(20\d{2}-\d{2}-\d{2})',
    ]
    for pat in date_patterns:
        m = re.search(pat, txt)
        if m:
            out['released'] = m.group(1).strip()
            break
    return out


def _lookup_addon_product_meta_sync(publisher: str, title: str) -> dict:
    query = ' '.join([publisher or '', title or '']).strip()
    if not query:
        return {}
    variants = [
        f'"{query}" msfs',
        f'{query} msfs',
        f'"{query}" version price release',
        f'{query} addon version price',
    ]
    merged = []
    seen = set()
    bad_hosts = {'youtube.com','www.youtube.com','bing.com','www.bing.com','duckduckgo.com','html.duckduckgo.com','lite.duckduckgo.com','google.com','www.google.com'}
    for variant in variants:
        for fn in (lambda v=variant: _search_google(v, 10, 'research'), lambda v=variant: _search_duckduckgo(v, 'research')):
            try:
                for r in fn() or []:
                    url = _clean_result_url(r.get('url') or '')
                    host = (urlparse(url).netloc or '').lower()
                    if not url or url in seen or host in bad_hosts:
                        continue
                    if host and host.count('.') == 1 and (urlparse(url).path or '/') == '/':
                        # Skip generic homepages unless the title/snippet already looks like the product page.
                        text = ' '.join([r.get('title') or '', r.get('snippet') or '']).lower()
                        if (title or '').lower() not in text and (publisher or '').lower() not in text:
                            continue
                    seen.add(url)
                    merged.append({**r, 'url': url})
            except Exception:
                continue
    ranked = _rank_results(query, merged, 'research')[:8] if merged else []
    best: dict[str, object] = {}
    chosen_source = None
    for r in ranked[:5]:
        meta = _extract_product_meta_from_text(' '.join([r.get('title') or '', r.get('snippet') or '']))
        try:
            html, _ = _fetch_url(r.get('url') or '', timeout=8)
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script','style','noscript']):
                tag.decompose()
            page_text = soup.get_text(' ', strip=True)[:50000]
            page_meta = _extract_product_meta_from_text(page_text)
            for k, v in page_meta.items():
                meta.setdefault(k, v)
        except Exception:
            pass
        if meta and not chosen_source:
            chosen_source = {'source_url': r.get('url') or '', 'source_title': r.get('title') or ''}
        for k, v in meta.items():
            best.setdefault(k, v)
        if {'version', 'released', 'price'}.issubset(best.keys()):
            break
    if chosen_source:
        best.update({k: v for k, v in chosen_source.items() if v})
    return best




def _extract_json_object(text: str) -> dict:
    raw = (text or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I | re.S).strip()
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except Exception:
        pass
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        snippet = raw[start:end+1]
        try:
            val = json.loads(snippet)
            return val if isinstance(val, dict) else {}
        except Exception:
            snippet = re.sub(r',\s*([}\]])', r'\1', snippet)
            try:
                val = json.loads(snippet)
                return val if isinstance(val, dict) else {}
            except Exception:
                return {}
    return {}


GEMINI_INTERACTIVE_MODEL = 'gemini-2.5-flash'
GEMINI_BULK_MODEL = 'gemini-2.5-flash-lite'
OPENAI_DEFAULT_MODEL = 'gpt-5-mini'
CLAUDE_DEFAULT_MODEL = 'claude-haiku-4-5-20251001'

_last_openai_usage: dict[str, object] = {}
_last_gemini_status: dict[str, object] = {}
_last_claude_status: dict[str, object] = {}


def _selected_ai_provider(settings: dict) -> str:
    raw = (settings.get('ai_provider') or '').strip().lower()
    if raw in {'gemini', 'openai', 'claude'}:
        return raw
    # Prefer Gemini as the safe default when no explicit saved provider exists.
    # This avoids new releases silently drifting to OpenAI just because an API key
    # happens to be present from older testing.
    if settings.get('google_api_key'):
        return 'gemini'
    if settings.get('openai_key'):
        return 'openai'
    if settings.get('claude_api_key'):
        return 'claude'
    return 'gemini'


def _selected_openai_model(settings: dict) -> str:
    raw = (settings.get('openai_model') or OPENAI_DEFAULT_MODEL).strip() or OPENAI_DEFAULT_MODEL
    model_name = raw.lower()
    legacy = {
        'gpt-5.4-nano',
        'gpt-5-nano-preview',
        'gpt-5.4-mini',
        'gpt-4o-mini',
        'gpt-4o',
        'gpt-4.1-mini',
    }
    if model_name in legacy:
        return OPENAI_DEFAULT_MODEL
    if not (model_name.startswith('gpt-5') or model_name.startswith('o')):
        return OPENAI_DEFAULT_MODEL
    return raw


def _selected_gemini_interactive_model(settings: dict) -> str:
    return (settings.get('gemini_interactive_model') or GEMINI_INTERACTIVE_MODEL).strip() or GEMINI_INTERACTIVE_MODEL


def _selected_gemini_bulk_model(settings: dict) -> str:
    return (settings.get('gemini_bulk_model') or GEMINI_BULK_MODEL).strip() or GEMINI_BULK_MODEL


def _selected_gemini_detail_mode(settings: dict) -> str:
    raw = (settings.get('gemini_detail_mode') or 'detailed').strip().lower()
    return raw if raw in {'fast','detailed'} else 'detailed'


def _selected_claude_model(settings: dict) -> str:
    return (settings.get('claude_model') or CLAUDE_DEFAULT_MODEL).strip() or CLAUDE_DEFAULT_MODEL


def _capture_openai_usage_headers(headers) -> None:
    global _last_openai_usage
    if not headers:
        return
    snap = {
        'limit_requests': headers.get('x-ratelimit-limit-requests') or '',
        'limit_tokens': headers.get('x-ratelimit-limit-tokens') or '',
        'remaining_requests': headers.get('x-ratelimit-remaining-requests') or '',
        'remaining_tokens': headers.get('x-ratelimit-remaining-tokens') or '',
        'reset_requests': headers.get('x-ratelimit-reset-requests') or '',
        'reset_tokens': headers.get('x-ratelimit-reset-tokens') or '',
    }
    if any(v for v in snap.values()):
        _last_openai_usage = snap


def _capture_gemini_status(*, model: str, ok: bool, error: str = '') -> None:
    global _last_gemini_status
    _last_gemini_status = {
        'model': model,
        'ok': ok,
        'error': error[:400] if error else '',
        'quota_hit': 'quota' in (error or '').lower() or 'resource exhausted' in (error or '').lower(),
    }


def _capture_claude_status(*, model: str, ok: bool, error: str = '') -> None:
    global _last_claude_status
    _last_claude_status = {
        'model': model,
        'ok': ok,
        'error': error[:400] if error else '',
        'quota_hit': 'rate limit' in (error or '').lower() or 'quota' in (error or '').lower(),
    }


def _gemini_generate_json(prompt: str, api_key: str, *, use_search: bool = True, model: str = GEMINI_INTERACTIVE_MODEL) -> tuple[dict, list[str], str]:
    if not api_key:
        raise ValueError('Google API key not configured')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.1, 'topP': 0.9, 'maxOutputTokens': 2048},
    }
    if use_search:
        payload['tools'] = [{'google_search': {}}]
    resp = requests.post(url, headers={'x-goog-api-key': api_key, 'Content-Type': 'application/json'}, json=payload, timeout=60)
    try:
        resp.raise_for_status()
    except Exception as e:
        detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
        _capture_gemini_status(model=model, ok=False, error=detail)
        raise
    _capture_gemini_status(model=model, ok=True)
    data = resp.json()
    candidates = data.get('candidates') or []
    parts = (((candidates[0] if candidates else {}).get('content') or {}).get('parts') or [])
    text_out = ''.join(part.get('text','') for part in parts if isinstance(part, dict))
    parsed = _extract_json_object(text_out)
    sources = []
    gm = (candidates[0].get('groundingMetadata') if candidates else None) or {}
    for chunk in gm.get('groundingChunks') or []:
        web = (chunk or {}).get('web') or {}
        uri = web.get('uri') or web.get('url')
        if uri and uri not in sources:
            sources.append(uri)
    return parsed, sources, text_out






def _extract_openai_response_text_and_sources(data: dict) -> tuple[str, list[str]]:
    text_out = ''
    sources: list[str] = []
    seen: set[str] = set()

    def add_source(url: str) -> None:
        clean = (url or '').strip()
        if clean and clean not in seen:
            seen.add(clean)
            sources.append(clean)

    if isinstance(data.get('output_text'), str) and data.get('output_text').strip():
        text_out = data.get('output_text').strip()

    for item in data.get('output') or []:
        if not isinstance(item, dict):
            continue
        if item.get('type') == 'web_search_call':
            action = item.get('action') or {}
            for src in action.get('sources') or []:
                if isinstance(src, dict):
                    add_source(src.get('url') or src.get('source_url') or '')
        if item.get('type') == 'message':
            for part in item.get('content') or []:
                if not isinstance(part, dict):
                    continue
                if part.get('type') in {'output_text', 'text'}:
                    part_text = part.get('text') or ''
                    if part_text:
                        text_out += part_text
                    for ann in part.get('annotations') or []:
                        if not isinstance(ann, dict):
                            continue
                        add_source(ann.get('url') or ((ann.get('url_citation') or {}).get('url') if isinstance(ann.get('url_citation'), dict) else '') or '')
    return text_out.strip(), sources



def _openai_reasoning_payload(model: str, *, use_search: bool = False) -> Optional[dict]:
    model_name = (model or '').strip().lower()
    if not (model_name.startswith('gpt-5') or model_name.startswith('o')):
        return None
    if model_name.startswith('gpt-5.1'):
        return {'effort': 'low' if use_search else 'none'}
    return {'effort': 'low'}


def _openai_post_responses(payload: dict, headers: dict) -> requests.Response:
    work = copy.deepcopy(payload)
    for _attempt in range(4):
        resp = requests.post('https://api.openai.com/v1/responses', headers=headers, json=work, timeout=120)
        _capture_openai_usage_headers(resp.headers)
        if resp.status_code < 400:
            return resp
        try:
            err = resp.json()
        except Exception:
            err = {}
        message = ((err.get('error') or {}).get('message') or '') if isinstance(err, dict) else ''
        param = ((err.get('error') or {}).get('param') or '') if isinstance(err, dict) else ''
        lower_message = message.lower()
        unsupported_reasoning = (
            ('reasoning.effort' in message) or (param == 'reasoning.effort') or ("Unsupported parameter: 'reasoning" in message)
        )
        if unsupported_reasoning and 'reasoning' in work:
            work.pop('reasoning', None)
            continue
        unsupported_verbosity = (param == 'text.verbosity') or ('text.verbosity' in lower_message and 'supported values' in lower_message)
        if unsupported_verbosity and isinstance(work.get('text'), dict):
            supported = re.findall(r"'(low|medium|high)'", lower_message)
            if 'medium' in supported:
                work['text']['verbosity'] = 'medium'
            elif supported:
                work['text']['verbosity'] = supported[0]
            else:
                work['text'].pop('verbosity', None)
            continue
        if ('web search cannot be used with json mode' in lower_message or param == 'response_format') and isinstance(work.get('text'), dict):
            work['text'].pop('format', None)
            continue
        break
    return resp


def _openai_build_search_memo(original_prompt: str) -> str:
    return f"""Use live web search to research the flight simulator add-on or aircraft described below.
Do NOT return the final JSON object yet.
Instead, return a detailed research memo in plain text for a second-pass writer.

Research memo requirements:
- Identify the best matching add-on or aircraft and mention any ambiguity.
- Prefer official developer pages, official storefronts, official aircraft manufacturer pages, and reputable aviation references.
- Capture as many concrete details as possible: current version, version dates, original release date, list price, currency, store name, compatibility, included content, features, variants, avionics, systems depth, scenery scope, installation notes, and other specifics when available.
- Gather enough detail that a second-pass writer can produce 2 to 3 substantial overview paragraphs and a rich, well-structured features section without needing to search again.
- Preserve exact factual details and units when available.
- Organize the memo with clear headings and bullets where useful.
- End with a short Sources section that lists the most useful source URLs or page titles you found.
- Write the memo in English.

Original extraction request:
{original_prompt}
"""


def _openai_generate_json(prompt: str, api_key: str, *, model: str = OPENAI_DEFAULT_MODEL, use_search: bool = True) -> tuple[dict, list[str], str]:
    if not api_key:
        raise ValueError('OpenAI API key not configured')
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    def single_pass_json_write(write_prompt: str, *, model_name: str = model) -> tuple[dict, list[str], str]:
        system_prompt = (
            'Return only valid JSON matching the requested schema. '
            'Favor completeness over brevity. When the schema asks for purpose_paragraphs, feature_intro, feature_groups, '
            'summary_html, or features_html, provide detailed, specific content rather than terse marketing blurbs. '
            'Preserve concrete product details, included content, systems depth, scenery scope, variants, compatibility, '
            'and implementation notes whenever the prompt asks for them. '
            'Write rich, comprehensive prose when the source material supports it. '
            'Return a single valid JSON object with no markdown fences or commentary before or after the JSON.'
        )
        payload = {
            'model': model_name,
            'input': [
                {'role': 'system', 'content': [{'type': 'input_text', 'text': system_prompt}]},
                {'role': 'user', 'content': [{'type': 'input_text', 'text': write_prompt}]},
            ],
            'max_output_tokens': 9000,
            'text': {
                'format': {
                    'type': 'json_object'
                },
                'verbosity': 'high',
            },
        }
        reasoning = _openai_reasoning_payload(model_name, use_search=False)
        if reasoning:
            payload['reasoning'] = reasoning
        resp = _openai_post_responses(payload, headers)
        resp.raise_for_status()
        data = resp.json()
        text_out, sources = _extract_openai_response_text_and_sources(data)
        parsed = _extract_json_object(text_out)
        return parsed, sources, text_out

    if not use_search:
        return single_pass_json_write(prompt)

    search_payload = {
        'model': model,
        'input': [
            {
                'role': 'system',
                'content': [{
                    'type': 'input_text',
                    'text': 'You are a research assistant for a flight simulator add-on manager. Use web search to gather detailed, current facts from official and reputable sources. Return a detailed plain-text research memo, not JSON.'
                }],
            },
            {
                'role': 'user',
                'content': [{
                    'type': 'input_text',
                    'text': _openai_build_search_memo(prompt)
                }],
            },
        ],
        'max_output_tokens': 6000,
        'text': {
            'verbosity': 'high'
        },
        'tools': [{
            'type': 'web_search',
            'search_context_size': 'high',
            'user_location': {
                'type': 'approximate',
                'country': 'US',
                'region': 'Florida',
                'timezone': 'America/New_York',
            },
        }],
        'tool_choice': 'auto',
        'include': ['web_search_call.action.sources'],
    }
    reasoning = _openai_reasoning_payload(model, use_search=True)
    if reasoning:
        search_payload['reasoning'] = reasoning
    search_resp = _openai_post_responses(search_payload, headers)
    search_resp.raise_for_status()
    search_data = search_resp.json()
    research_memo, sources = _extract_openai_response_text_and_sources(search_data)
    sources_block = '\n'.join(f'- {u}' for u in sources[:12]) if sources else '- (no cited URLs returned)'
    write_prompt = f"""{prompt}

Use ONLY the research memo and source list below as your source material for the final JSON object.
Do not compress the content more than necessary. If the memo contains enough detail for multiple substantial overview paragraphs and a rich feature breakdown, preserve that detail in the JSON fields.
Make purpose_paragraphs polished and substantial. Make feature_groups detailed and specific. When helpful, use feature_intro, notes, compatibility, and installation_notes to keep structured detail instead of collapsing everything into summary_html.

Research memo from first-pass web search:
{research_memo}

Source URLs from first-pass web search:
{sources_block}
"""
    parsed, _unused_sources, text_out = single_pass_json_write(write_prompt, model_name=model)
    return parsed, sources, text_out


def _claude_generate_json(prompt: str, api_key: str, *, model: str = CLAUDE_DEFAULT_MODEL) -> tuple[dict, list[str], str]:
    if not api_key:
        raise ValueError('Claude API key not configured')
    payload = {
        'model': model,
        'max_tokens': 2500,
        'temperature': 0.1,
        'system': 'Return only valid JSON matching the requested schema.',
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
    }
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=payload,
        timeout=90,
    )
    try:
        resp.raise_for_status()
    except Exception as e:
        detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
        _capture_claude_status(model=model, ok=False, error=detail)
        raise
    _capture_claude_status(model=model, ok=True)
    data = resp.json()
    parts = data.get('content') or []
    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get('type') == 'text':
            texts.append(part.get('text') or '')
    text_out = ''.join(texts)
    parsed = _extract_json_object(text_out)
    return parsed, [], text_out


def _provider_generate_json(provider: str, prompt: str, settings: dict, *, use_search: bool = True, gemini_model: Optional[str] = None, openai_model: Optional[str] = None, claude_model: Optional[str] = None) -> tuple[dict, list[str], str]:
    provider = (provider or '').lower().strip()
    if provider == 'gemini':
        return _gemini_generate_json(
            prompt,
            settings.get('google_api_key',''),
            use_search=use_search,
            model=(gemini_model or _selected_gemini_interactive_model(settings)),
        )
    if provider == 'claude':
        return _claude_generate_json(prompt, settings.get('claude_api_key',''), model=(claude_model or _selected_claude_model(settings)))
    return _openai_generate_json(prompt, settings.get('openai_key',''), model=(openai_model or _selected_openai_model(settings)), use_search=use_search)


def _normalize_html_fragment(html: str) -> str:
    raw = (html or '').strip()
    if not raw:
        return ''
    raw = re.sub(r'(?i)\sstyle\s*=\s*"[^"]*"', '', raw)
    raw = re.sub(r"(?i)\sstyle\s*=\s*'[^']*'", '', raw)
    raw = raw.replace('\r', '')
    return raw.strip()


def _html_to_text(html: str) -> str:
    raw = (html or '').strip()
    if not raw:
        return ''
    try:
        txt = BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True)
    except Exception:
        txt = re.sub(r'<[^>]+>', ' ', raw)
    txt = unescape(txt)
    return re.sub(r'\s+', ' ', txt).strip()


def _is_generic_overview_summary(html: str, addon=None) -> bool:
    txt = _html_to_text(html).lower()
    if not txt:
        return False
    compact = re.sub(r'\s+', ' ', txt)
    title = ((getattr(addon, 'title', '') or '').strip().lower()) if addon is not None else ''
    publisher = ((getattr(addon, 'publisher', '') or '').strip().lower()) if addon is not None else ''
    addon_type = ((getattr(addon, 'type', '') or '').strip().lower()) if addon is not None else ''
    if re.search(r'<<\s*type\s*>>\s+addon\s+by\s+<<\s*publisher\s*>>', compact, re.I):
        return True
    if '<<type>>' in compact or '<<publisher>>' in compact:
        return True
    simple = {'addon by'}
    if publisher:
        simple.update({f'addon by {publisher}', f'this addon by {publisher}'})
        if addon_type:
            simple.update({f'{addon_type} addon by {publisher}', f'this {addon_type} addon by {publisher}'})
    if compact in simple:
        return True
    if title and publisher and len(compact) < 120 and 'addon by' in compact and title in compact:
        return True
    if len(compact) < 60 and 'addon by' in compact:
        return True
    return False


def _has_meaningful_existing_html(html: str, *, field: str, addon=None) -> bool:
    txt = _html_to_text(html)
    if not txt:
        return False
    if field == 'overview' and _is_generic_overview_summary(html, addon):
        return False
    return True


def _addon_sim_label(settings: dict) -> str:
    sim_name = (settings.get('flight_sim_name') or 'MSFS').strip()
    sim_version = (settings.get('flight_sim_version') or '').strip()
    return (' '.join(x for x in [sim_name, sim_version] if x)).strip()


def _preferred_language(settings: dict) -> str:
    return (settings.get('language') or 'English').strip() or 'English'

def _guess_subtype_for_addon(addon, *, category: str = '', title: str = '') -> str | None:
    addon_type = ((getattr(addon, 'type', '') or '')).strip()
    pieces = [
        str(title or getattr(addon, 'title', '') or ''),
        str(getattr(addon, 'publisher', '') or ''),
        str(category or ''),
        str(getattr(getattr(addon, 'rw', None), 'manufacturer_full_name', '') or ''),
        str(getattr(getattr(addon, 'rw', None), 'mfr', '') or ''),
        str(getattr(getattr(addon, 'rw', None), 'model', '') or ''),
    ]
    hay = ' '.join(pieces).lower()
    if addon_type == 'Aircraft':
        for subtype, keywords in SUBTYPE_MAP.items():
            if any(k in hay for k in keywords):
                return subtype
        category_map = {
            'airliner': 'Airliner',
            'airline': 'Airliner',
            'regional': 'Regional',
            'business jet': 'Business Jet',
            'bizjet': 'Business Jet',
            'helicopter': 'Helicopter',
            'rotorcraft': 'Helicopter',
            'military': 'Military',
            'fighter': 'Military',
            'general aviation': 'General Aviation',
            'ga': 'General Aviation',
        }
        for key, value in category_map.items():
            if key in hay:
                return value
        return 'General Aviation'
    if addon_type == 'Airport':
        mapping = [
            ('heliport', 'Heliport'),
            ('seaplane', 'Seaplane Base'),
            ('closed', 'Closed'),
            ('large', 'Large Commercial'),
            ('international', 'Large Commercial'),
            ('medium', 'Medium Commercial'),
            ('regional', 'Medium Commercial'),
            ('general aviation', 'General Aviation'),
        ]
        for key, value in mapping:
            if key in hay:
                return value
    if addon_type == 'Scenery':
        mapping = [('city', 'City'), ('region', 'Region'), ('mesh', 'Mesh'), ('landmark', 'Landmark'), ('airport', 'Airport scenery')]
        for key, value in mapping:
            if key in hay:
                return value
    if addon_type == 'Utility':
        mapping = [('weather', 'Weather'), ('mission', 'Mission'), ('navigation', 'Navigation'), ('tool', 'Tool')]
        for key, value in mapping:
            if key in hay:
                return value
    if addon_type == 'Vehicles':
        mapping = [('truck', 'Truck'), ('offroad', 'Offroad'), ('car', 'Car')]
        for key, value in mapping:
            if key in hay:
                return value
    if addon_type == 'Boats':
        mapping = [('military', 'Military'), ('cargo', 'Cargo'), ('pleasure', 'Pleasure')]
        for key, value in mapping:
            if key in hay:
                return value
    if addon_type == 'Mod':
        mapping = [('livery', 'Livery'), ('enhancement', 'Enhancement')]
        for key, value in mapping:
            if key in hay:
                return value
    return None


def _cleanup_name_bits(value: str) -> str:
    txt = re.sub(r'[_]+', ' ', value or '')
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def _addon_query_candidates(addon) -> list[str]:
    pub = _cleanup_name_bits(getattr(addon, 'publisher', '') or '')
    title = _cleanup_name_bits(getattr(addon, 'title', '') or '')
    base = f'{pub} {title}'.strip()
    variants = [base, title, f'{pub} {title.replace(" Series", "")}'.strip(), title.replace(' Series', '').strip()]
    swap = title.replace(' DA40', ' DA-40').replace(' DA42', ' DA-42').replace(' DA62', ' DA-62')
    if swap != title:
        variants.extend([f'{pub} {swap}'.strip(), swap])
    for needle, repl in [('  ', ' '), ('Series', ''), (' 2020', ''), (' 2024', '')]:
        alt = f'{pub} {title}'.replace(needle, repl).strip()
        if alt:
            variants.append(alt)
    out = []
    seen = set()
    for item in variants:
        item = re.sub(r'\s+', ' ', item or '').strip(' -')
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out[:6]


def _aircraft_query_candidates(mfr: str, model: str, fallback_title: str = '') -> list[tuple[str, str]]:
    mfr = _cleanup_name_bits(mfr)
    model = _cleanup_name_bits(model or fallback_title)
    combos = [(mfr, model)]
    hy_model = model.replace(' DA40', ' DA-40').replace(' DA42', ' DA-42').replace(' DA62', ' DA-62')
    if hy_model != model:
        combos.append((mfr, hy_model))
    if model.endswith(' Series'):
        combos.append((mfr, model.replace(' Series', '').strip()))
    if fallback_title and fallback_title.strip() and fallback_title.strip() != model:
        combos.append((mfr, _cleanup_name_bits(fallback_title)))
    out = []
    seen = set()
    for mmfr, mmodel in combos:
        key = (mmfr.lower(), mmodel.lower())
        if mmfr and mmodel and key not in seen:
            seen.add(key)
            out.append((mmfr, mmodel))
    return out[:5]


def _range_nm_from_any(text_value, range_nm):
    rn = _int_or_none(range_nm)
    if rn is not None:
        return rn
    raw = str(text_value or '').lower()
    m = re.search(r'([\d,]+(?:\.\d+)?)\s*(nm|nmi|nautical miles|mi|miles|km)', raw)
    if not m:
        return None
    num = float(m.group(1).replace(',', ''))
    unit = m.group(2)
    if unit in {'nm', 'nmi', 'nautical miles'}:
        nm = num
    elif unit in {'mi', 'miles'}:
        nm = num * 0.868976
    else:
        nm = num * 0.539957
    return int(round(nm))


def _clean_provider_source_label(value: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return raw
    low = raw.lower()
    if 'vertexaisearch.cloud.google.com' in low:
        return 'vertexaisearch.cloud.google.com'
    try:
        parsed = urlparse(raw)
        if parsed.scheme and parsed.netloc:
            return parsed.netloc
    except Exception:
        pass
    return raw


def _source_summary_label(sources: list[str] | tuple[str, ...] | None, provider_name: str = '', *, fallback: str = '') -> str:
    labels = []
    for item in list(sources or []):
        label = _clean_provider_source_label(item)
        if not label:
            continue
        if label not in labels:
            labels.append(label)
    if labels:
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} + {labels[1]}"
        return f"{labels[0]} + {labels[1]} + {len(labels)-2} more"
    return fallback or provider_name


def _product_content_is_thin(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return True
    purpose = _coerce_text_list(parsed.get('purpose_paragraphs') or parsed.get('summary_paragraphs') or parsed.get('overview_paragraphs'))
    feature_intro = _coerce_text_list(parsed.get('feature_intro') or parsed.get('feature_paragraphs') or parsed.get('features_paragraphs'))
    groups = parsed.get('feature_groups') or []
    summary_html = str(parsed.get('summary_html') or '')
    features_html = str(parsed.get('features_html') or '')
    purpose_chars = sum(len(p) for p in purpose)
    bullets = 0
    for g in groups if isinstance(groups, list) else []:
        bullets += len(_coerce_text_list((g or {}).get('bullets')))
    feature_chars = sum(len(p) for p in feature_intro) + len(features_html)
    return (len(purpose) < 2 or purpose_chars < 450 or len(groups) < 3 or bullets < 8 or feature_chars < 700 or len(summary_html) < 350)


def _coerce_text_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip(' -•\t') for p in re.split(r'[\n\r]+', value) if p.strip()]
        return [p for p in parts if p]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                txt = item.strip(' -•\t')
                if txt:
                    out.append(txt)
            elif isinstance(item, dict):
                txt = str(item.get('text') or item.get('title') or item.get('value') or '').strip(' -•\t')
                if txt:
                    out.append(txt)
            elif item is not None:
                txt = str(item).strip(' -•\t')
                if txt:
                    out.append(txt)
        return out
    return [str(value).strip()] if str(value).strip() else []

def _normalize_feature_groups(value) -> list[dict]:
    groups = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                heading = str(item.get('heading') or item.get('title') or item.get('name') or '').strip()
                bullets = _coerce_text_list(item.get('bullets') or item.get('items') or item.get('points'))
                if heading or bullets:
                    groups.append({'heading': heading or 'Highlights', 'bullets': bullets})
            elif isinstance(item, str):
                txt = item.strip()
                if txt:
                    groups.append({'heading': 'Highlights', 'bullets': [txt]})
    elif isinstance(value, dict):
        for heading, bullets in value.items():
            rows = _coerce_text_list(bullets)
            if rows:
                groups.append({'heading': str(heading).strip() or 'Highlights', 'bullets': rows})
    return groups


def _html_escape(value: str) -> str:
    return escape(str(value or '').strip(), quote=False)



def _text_canonical(value: str) -> str:
    value = re.sub(r'<[^>]+>', ' ', str(value or ''))
    value = value.replace('&nbsp;', ' ')
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower())
    return re.sub(r'\s+', ' ', value).strip()


def _text_repeats(candidate: str, seen: list[str]) -> bool:
    cand = _text_canonical(candidate)
    if not cand:
        return True
    for item in seen or []:
        base = _text_canonical(item)
        if not base:
            continue
        if cand == base:
            return True
        if len(cand) >= 28 and cand in base:
            return True
        if len(base) >= 28 and base in cand:
            return True
    return False


def _dedupe_text_list_against(items, seen=None):
    kept = []
    seen_items = list(seen or [])
    for item in _coerce_text_list(items):
        if _text_repeats(item, seen_items):
            continue
        kept.append(item)
        seen_items.append(item)
    return kept


def _render_ai_overview_html(parsed: dict, addon) -> str:
    paras = _dedupe_text_list_against(parsed.get('purpose_paragraphs') or parsed.get('summary_paragraphs') or parsed.get('overview_paragraphs'))
    if len(paras) < 2 and parsed.get('summary_html'):
        return _normalize_html_fragment(parsed.get('summary_html'))
    title = str(parsed.get('summary_title') or '').strip()
    selling_points = _dedupe_text_list_against(parsed.get('key_selling_points') or parsed.get('selling_points') or parsed.get('highlights'), paras)
    notes = _dedupe_text_list_against(parsed.get('notes'), paras + selling_points)
    compatibility = _dedupe_text_list_against(parsed.get('compatibility'), paras + selling_points + notes)
    installation = _dedupe_text_list_against(parsed.get('installation_notes'), paras + selling_points + notes + compatibility)
    parts = []
    if title:
        parts.append(f'<h3>{_html_escape(title)}</h3>')
    for para in paras[:3]:
        parts.append(f'<p>{_html_escape(para)}</p>')
    if selling_points:
        parts.append('<h3>Key Selling Points</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in selling_points[:8]) + '</ul>')
    if compatibility:
        parts.append('<h3>Compatibility</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in compatibility[:6]) + '</ul>')
    if installation:
        parts.append('<h3>Installation Notes</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in installation[:6]) + '</ul>')
    if notes:
        parts.append('<h3>Notes</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in notes[:6]) + '</ul>')
    return ''.join(parts).strip()


def _render_ai_features_html(parsed: dict, addon) -> str:
    overview_seen = _coerce_text_list(parsed.get('purpose_paragraphs') or parsed.get('summary_paragraphs') or parsed.get('overview_paragraphs'))
    overview_seen += _coerce_text_list(parsed.get('key_selling_points') or parsed.get('selling_points') or parsed.get('highlights'))
    overview_seen += _coerce_text_list(parsed.get('compatibility'))
    intro_paras = _dedupe_text_list_against(parsed.get('feature_intro') or parsed.get('feature_paragraphs') or parsed.get('features_paragraphs'), overview_seen)
    groups = _normalize_feature_groups(parsed.get('feature_groups'))
    notes = _dedupe_text_list_against(parsed.get('notes'), overview_seen + intro_paras)
    installation = _dedupe_text_list_against(parsed.get('installation_notes'), overview_seen + intro_paras + notes)
    if not intro_paras and not groups and parsed.get('features_html'):
        return _normalize_html_fragment(parsed.get('features_html'))
    seen = list(overview_seen) + list(intro_paras)
    parts = []
    for para in intro_paras[:2]:
        parts.append(f'<p>{_html_escape(para)}</p>')
    for group in groups[:8]:
        bullets = []
        for item in group.get('bullets') or []:
            if _text_repeats(item, seen):
                continue
            bullets.append(item)
            seen.append(item)
        if not bullets:
            continue
        parts.append(f'<h3>{_html_escape(group.get("heading") or "Highlights")}</h3>')
        parts.append('<ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in bullets[:10]) + '</ul>')
    if installation:
        parts.append('<h3>Installation Notes</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in installation[:6]) + '</ul>')
    if notes:
        parts.append('<h3>Notes</h3><ul>' + ''.join(f'<li>{_html_escape(item)}</li>' for item in notes[:6]) + '</ul>')
    return ''.join(parts).strip()


def _gemini_log_context(kind: str, addon_title: str, candidate: str, attempt: int, model: str):
    log.info('Gemini %s attempt=%s model=%s addon=%s candidate=%s', kind, attempt, model, addon_title, candidate)


def _build_product_prompt(addon, sim_label: str, include_overview: bool = True, include_features: bool = True, *, search_term: Optional[str] = None, response_language: str = 'English', detail_mode: str = 'detailed') -> str:
    lookup = (search_term or f"{(addon.publisher or '').strip()} {(addon.title or '').strip()}").strip()
    addon_type = (getattr(addon, 'type', '') or '').strip() or 'Addon'
    feature_guidance = "general addon capability categories"
    if addon_type == 'Aircraft':
        feature_guidance = 'feature categories such as avionics, systems depth, flight model, sounds, visuals, cabin or cockpit detail, performance options, included variants, and compatibility'
    elif addon_type == 'Airport':
        feature_guidance = 'feature categories such as scenery scope, terminals and buildings, ground textures, lighting, landside detail, terrain, custom objects, and compatibility'
    elif addon_type == 'Scenery':
        feature_guidance = 'feature categories such as coverage area, landmarks, photogrammetry or textures, terrain, lighting, included points of interest, and compatibility'
    paragraph_range = '3 or 4' if detail_mode == 'detailed' else '2 or 3'
    sentence_range = '4 to 7' if detail_mode == 'detailed' else '3 to 5'
    selling_points_range = '6 to 10' if detail_mode == 'detailed' else '4 to 6'
    feature_intro_range = '2 or 3' if detail_mode == 'detailed' else '1 or 2'
    feature_groups_range = '4 to 8' if detail_mode == 'detailed' else '3 to 5'
    feature_bullets_range = '4 to 10' if detail_mode == 'detailed' else '3 to 6'
    summary_html_guidance = 'at least three paragraphs with real descriptive substance' if detail_mode == 'detailed' else 'at least two substantial paragraphs'
    verbosity_note = 'Favor depth and specificity over brevity. If the evidence supports a richer write-up, return the fuller version instead of a compressed summary.' if detail_mode == 'detailed' else 'Keep the write-up concise but still specific and grounded.'
    return f"""Use grounded web search to find product metadata for the flight simulator add-on '{lookup}' for '{sim_label}'.
Return ONLY one valid JSON object with these exact keys:
latest_current_version, latest_version_date, release_date, list_price, currency, store_name, summary_title, purpose_paragraphs, key_selling_points, feature_intro, feature_groups, notes, compatibility, installation_notes, summary_html, features_html.
Rules:
- Focus on the product page for the addon itself, not unrelated videos, forum chatter, or generic vendor home pages.
- Prefer official storefronts, official developer pages, and reputable product listings.
- All prose must be written in {response_language}.
- latest_version_date should be the date the current/latest version became available when known.
- release_date should be the add-on's original/first public release date when known.
- list_price must be numeric when possible, otherwise null.
- summary_title should be a concise headline for the addon.
- purpose_paragraphs should be an array with {paragraph_range} substantial paragraphs describing the addon purpose, scope, immersion, and what it adds to the simulator. Each paragraph should usually be {sentence_range} sentences and should read like polished website copy, not bullet notes. Do not turn these paragraphs into a feature list.
- key_selling_points should be an array of {selling_points_range} short, specific bullets when enough evidence exists.
- feature_intro should be {feature_intro_range} short introductory paragraphs for a detailed features section and must not repeat the same ideas already used in purpose_paragraphs.
- feature_groups should be an array of {feature_groups_range} objects with heading and bullets keys when enough evidence exists. Each group should usually have {feature_bullets_range} detailed bullets. The grouped bullets should cover {feature_guidance}.
- When the official product page has a Features, Details, Included, or Specifications section, mirror that detail and specificity in feature_groups instead of generic marketing phrasing.
- Prefer concrete implementation details from the product page such as modeled systems, included airports or variants, avionics packages, terminal/building scope, custom objects, textures, lighting, sounds, flight model notes, performance options, and included extras.
- notes, compatibility, and installation_notes should each be arrays of short strings when useful, otherwise empty arrays.
- compatibility should be limited to simulator/platform compatibility and should not be repeated inside feature_intro or feature_groups.
- summary_html and features_html should be rich, readable HTML fallbacks that preserve the same level of detail as the structured fields. summary_html should normally be {summary_html_guidance}. features_html should normally include a short intro plus multiple grouped lists or sections when supported by the source material.
- Do not use generic filler such as '<<Type>> addon by <<publisher>>'.
- {verbosity_note}
- Do not include markdown or code fences.
- If unknown, use empty strings, empty arrays, or null for list_price."""




def _sanitize_aircraft_cost(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    low = raw.lower()
    bad_terms = ('addon', 'marketplace', 'msfs', 'simulator', 'store page', 'flight sim')
    if any(term in low for term in bad_terms):
        return ''
    m = re.search(r'([€£$])\s*([0-9][0-9,]*(?:\.[0-9]+)?)', raw)
    if m:
        try:
            amount = float(m.group(2).replace(',', ''))
            if amount < 1000:
                return ''
        except Exception:
            pass
    return raw
def _build_aircraft_prompt(mfr: str, model: str, *, response_language: str = 'English') -> str:
    return f"""Use Google Search grounding to find real-world aircraft specifications for the aircraft '{mfr} {model}'.
Return ONLY one valid JSON object with these exact keys: manufacturer_full_name, model, category, engine, engine_type, max_speed, cruise_speed, range, range_nm, ceiling, passenger_capacity, mtow, fuel_capacity, wingspan, length, height, avionics, variants, in_production, aircraft_cost, country_of_origin, date_introduced, summary_html.
Rules:
- Do not include markdown or code fences.
- range_nm must be an integer number of nautical miles when available, converted from any other published unit if needed.
- Keep units inside max_speed, cruise_speed, range, ceiling, mtow as readable strings.
- fuel_capacity should be a string with units if known.
- wingspan, length, and height should be strings with units if known.
- avionics should be a readable multi-line style string or semicolon-separated string describing notable avionics packages/cockpit options used on this aircraft.
- variants should be a readable multi-line style string or semicolon-separated string listing notable variants or sub-models.
- in_production should be 'Yes' or 'No' when known.
- aircraft_cost should be the real-world aircraft acquisition cost only when known. Never include addon, marketplace, simulator, or DLC pricing. If uncertain, return an empty string.
- country_of_origin should be the aircraft's country of origin when known.
- summary_html should be concise readable HTML for sim pilots written in {response_language}.
- If unknown, use empty strings or null only for range_nm.
- Prefer official manufacturer, reputable aviation references, and Wikipedia when they agree."""


def _merge_product_into_addon(addon, parsed: dict, sources: list[str], *, include_overview: bool = True, include_features: bool = True, override_existing: bool = False):
    addon.pr.latest_ver = parsed.get('latest_current_version') or addon.pr.latest_ver
    addon.pr.latest_ver_date = parsed.get('latest_version_date') or addon.pr.latest_ver_date
    addon.pr.released = parsed.get('release_date') or addon.pr.released
    price = _num_or_none(parsed.get('list_price'))
    if price is not None:
        addon.pr.price = price
    if parsed.get('store_name'):
        addon.pr.source_store = _clean_provider_source_label(parsed.get('store_name'))

    if include_overview:
        incoming_summary = _normalize_html_fragment(_render_ai_overview_html(parsed, addon) or parsed.get('summary_html'))
        existing_summary = addon.summary or ''
        existing_summary_is_meaningful = _has_meaningful_existing_html(existing_summary, field='overview', addon=addon)
        existing_summary_is_generic = bool(existing_summary) and not existing_summary_is_meaningful
        if incoming_summary and (override_existing or not existing_summary_is_meaningful):
            addon.summary = incoming_summary
        elif override_existing and existing_summary_is_generic:
            addon.summary = ''

    if include_features:
        incoming_features = _normalize_html_fragment(_render_ai_features_html(parsed, addon) or parsed.get('features_html'))
        existing_features = addon.usr.features or ''
        existing_features_is_meaningful = _has_meaningful_existing_html(existing_features, field='features', addon=addon)
        if incoming_features and (override_existing or not existing_features_is_meaningful):
            addon.usr.features = incoming_features

    if sources:
        addon.rw.source = ' / '.join(sources[:2])
    return addon


def _merge_aircraft_into_addon(addon, parsed: dict, sources: list[str]):
    rw = addon.rw
    rw.manufacturer_full_name = parsed.get('manufacturer_full_name') or rw.manufacturer_full_name
    rw.model = parsed.get('model') or rw.model
    rw.category = parsed.get('category') or rw.category
    rw.engine = parsed.get('engine') or rw.engine
    rw.engine_type = parsed.get('engine_type') or rw.engine_type
    rw.max_speed = parsed.get('max_speed') or rw.max_speed
    rw.cruise = parsed.get('cruise_speed') or rw.cruise
    rw.range = parsed.get('range') or rw.range
    rn = _range_nm_from_any(parsed.get('range'), parsed.get('range_nm'))
    if rn is not None:
        rw.range_nm = rn
        rw.range = f'{rn} nm'
    rw.ceiling = parsed.get('ceiling') or rw.ceiling
    rw.seats = parsed.get('passenger_capacity') or rw.seats
    rw.mtow = parsed.get('mtow') or rw.mtow
    rw.fuel_capacity = parsed.get('fuel_capacity') or rw.fuel_capacity
    rw.wingspan = parsed.get('wingspan') or rw.wingspan
    rw.length = parsed.get('length') or rw.length
    rw.height = parsed.get('height') or rw.height
    rw.avionics = parsed.get('avionics') or rw.avionics
    rw.variants = parsed.get('variants') or rw.variants
    rw.in_production = parsed.get('in_production') or rw.in_production
    rw.aircraft_cost = parsed.get('aircraft_cost') or rw.aircraft_cost
    rw.country_of_origin = parsed.get('country_of_origin') or rw.country_of_origin
    rw.introduced = parsed.get('date_introduced') or rw.introduced
    if parsed.get('summary_html') and not _has_meaningful_existing_html(addon.summary or '', field='overview', addon=addon):
        addon.summary = _normalize_html_fragment(parsed.get('summary_html'))
    rw.source = _clean_provider_source_label(' / '.join(sources[:2])) if sources else _clean_provider_source_label(rw.source or '')
    return addon


def _extract_json_pairs_fallback(text: str, keys: list[str]) -> dict:
    raw = (text or '').strip()
    out = {}
    for key in keys:
        m = re.search(r'"%s"\s*:\s*"((?:\\.|[^"\\])*)"' % re.escape(key), raw)
        if m:
            try:
                out[key] = bytes(m.group(1), 'utf-8').decode('unicode_escape')
            except Exception:
                out[key] = m.group(1)
            continue
        m = re.search(r'"%s"\s*:\s*(-?\d+(?:\.\d+)?)' % re.escape(key), raw)
        if m:
            num = m.group(1)
            out[key] = int(num) if re.fullmatch(r'-?\d+', num) else float(num)
            continue
        m = re.search(r'"%s"\s*:\s*(null|true|false)' % re.escape(key), raw, re.I)
        if m:
            val = m.group(1).lower()
            out[key] = None if val == 'null' else (val == 'true')
    return out

def _num_or_none(v):
    try:
        if v is None or v == '':
            return None
        return float(v)
    except Exception:
        return None


def _int_or_none(v):
    try:
        if v is None or v == '':
            return None
        return int(str(v).strip())
    except Exception:
        return None


class GeminiAircraftRequest(BaseModel):
    manufacturer: str = ''
    manufacturer_full_name: Optional[str] = None
    model: str
    provider: Optional[str] = None
    screen: Optional[str] = None
    action: Optional[str] = None


async def _run_gemini_aircraft_lookup(settings: dict, lookup_mfr: str, model: str, *, fallback_title: str = '', gemini_model: Optional[str] = None):
    api_key = settings.get('google_api_key', '')
    response_language = _preferred_language(settings)
    attempts = []
    last_error = None
    for idx, (cand_mfr, cand_model) in enumerate(_aircraft_query_candidates(lookup_mfr, model, fallback_title), start=1):
        prompt = _build_aircraft_prompt(cand_mfr, cand_model, response_language=response_language)
        active_model = gemini_model or _selected_gemini_interactive_model(settings)
        _gemini_log_context('aircraft', fallback_title or model, f'{cand_mfr} {cand_model}', idx, active_model)
        try:
            parsed, sources, raw = await asyncio.to_thread(lambda p=prompt, m=active_model: _gemini_generate_json(p, api_key, use_search=True, model=m))
            if not parsed:
                parsed = _extract_json_pairs_fallback(raw, ['manufacturer_full_name','model','category','engine','engine_type','max_speed','cruise_speed','range','range_nm','ceiling','passenger_capacity','mtow','fuel_capacity','wingspan','length','height','avionics','variants','in_production','aircraft_cost','country_of_origin','date_introduced','summary_html'])
            if parsed:
                log.info('Gemini aircraft success addon=%s candidate=%s sources=%s', fallback_title or model, f'{cand_mfr} {cand_model}', len(sources))
                return parsed, sources, {'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx}
            attempts.append({'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx, 'error': f'No structured data: {raw[:180]}'})
        except Exception as e:
            detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
            attempts.append({'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx, 'error': detail})
            last_error = detail
            log.warning('Gemini aircraft attempt failed addon=%s candidate=%s error=%s', fallback_title or model, f'{cand_mfr} {cand_model}', detail)
    raise HTTPException(502, f'Gemini aircraft lookup failed after {len(attempts)} attempts. Last error: {last_error or "No structured data"}')


async def _run_gemini_product_lookup(addon, settings: dict, *, model: str = GEMINI_INTERACTIVE_MODEL):
    api_key = settings.get('google_api_key', '')
    response_language = _preferred_language(settings)
    detail_mode = _selected_gemini_detail_mode(settings)
    attempts = []
    last_error = None
    for idx, candidate in enumerate(_addon_query_candidates(addon), start=1):
        prompt = _build_product_prompt(addon, _addon_sim_label(settings), include_overview=True, include_features=True, search_term=candidate, response_language=response_language, detail_mode=detail_mode)
        _gemini_log_context('product', addon.title, candidate, idx, model)
        try:
            parsed, sources, raw = await asyncio.to_thread(lambda p=prompt, m=model: _gemini_generate_json(p, api_key, use_search=True, model=m))
            if not parsed:
                parsed = _extract_json_pairs_fallback(raw, ['latest_current_version','latest_version_date','release_date','list_price','currency','store_name','summary_html','features_html'])
            if detail_mode == 'detailed' and parsed and _product_content_is_thin(parsed):
                try:
                    expansion_prompt = (
                        prompt
                        + "\n\nThe first draft was too thin. Search again and return the same JSON keys, but make the overview and features materially fuller and more specific based on the best grounded product sources."
                    )
                    parsed2, sources2, raw2 = await asyncio.to_thread(lambda p=expansion_prompt, m=model: _gemini_generate_json(p, api_key, use_search=True, model=m))
                    if not parsed2:
                        parsed2 = _extract_json_pairs_fallback(raw2, ['latest_current_version','latest_version_date','release_date','list_price','currency','store_name','summary_html','features_html'])
                    if parsed2 and not _product_content_is_thin(parsed2):
                        parsed, sources = parsed2, (sources2 or sources)
                except Exception as expand_err:
                    log.warning('Gemini product expansion attempt failed addon=%s candidate=%s error=%s', addon.title, candidate, str(expand_err))
            if parsed:
                log.info('Gemini product success addon=%s candidate=%s sources=%s', addon.title, candidate, len(sources))
                return parsed, sources, {'candidate': candidate, 'attempt': idx}
            attempts.append({'candidate': candidate, 'attempt': idx, 'error': f'No structured data: {raw[:180]}'})
        except Exception as e:
            detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
            attempts.append({'candidate': candidate, 'attempt': idx, 'error': detail})
            last_error = detail
            log.warning('Gemini product attempt failed addon=%s candidate=%s error=%s', addon.title, candidate, detail)
    raise HTTPException(502, f'Gemini product lookup failed after {len(attempts)} attempts. Last error: {last_error or "No structured data"}')



def _lookup_aircraft_source_sync(manufacturer: str, model: str, fallback_title: str = '') -> dict:
    """Find a likely public web page for an aircraft lookup.

    Gemini can return grounded source URLs directly. OpenAI and Claude do not
    in this app's lower-cost path, so we do a lightweight search ourselves and
    keep only the best matching page URL/title. That value is stored as the
    aircraft Web Data Source so the user sees where the facts most likely came
    from instead of only seeing the AI provider name.
    """

    query = ' '.join([manufacturer or '', model or fallback_title or '']).strip()
    if not query:
        return {}
    variants = [
        f'"{query}" aircraft',
        f'{query} aircraft specifications',
        f'{query} performance range ceiling',
        f'site:wikipedia.org {query}',
    ]
    merged = []
    seen = set()
    bad_hosts = {'youtube.com','www.youtube.com','bing.com','www.bing.com','duckduckgo.com','html.duckduckgo.com','lite.duckduckgo.com','google.com','www.google.com'}
    for variant in variants:
        for fn in (lambda v=variant: _search_google(v, 10, 'research'), lambda v=variant: _search_duckduckgo(v, 'research')):
            try:
                for r in fn() or []:
                    url = _clean_result_url(r.get('url') or '')
                    host = (urlparse(url).netloc or '').lower()
                    if not url or url in seen or host in bad_hosts:
                        continue
                    seen.add(url)
                    merged.append({**r, 'url': url})
            except Exception:
                continue
    ranked = _rank_results(query, merged, 'research')[:5] if merged else []
    if not ranked:
        return {}
    best = ranked[0]
    return {'source_url': best.get('url') or '', 'source_title': best.get('title') or ''}


async def _run_provider_aircraft_lookup(provider: str, settings: dict, lookup_mfr: str, model: str, *, fallback_title: str = '', gemini_model: Optional[str] = None, openai_model: Optional[str] = None, claude_model: Optional[str] = None):
    provider = (provider or 'gemini').lower().strip()
    if provider == 'gemini':
        return await _run_gemini_aircraft_lookup(settings, lookup_mfr, model, fallback_title=fallback_title, gemini_model=(gemini_model or _selected_gemini_interactive_model(settings)))

    # OpenAI/Claude do not return grounded source links in this app's low-cost
    # path, so we gather a lightweight evidence page ourselves and prepend that
    # URL to the source list whenever we can identify a likely aircraft page.
    evidence = await asyncio.to_thread(_lookup_aircraft_source_sync, lookup_mfr, model, fallback_title)
    attempts = []
    last_error = ''
    for idx, (cand_mfr, cand_model) in enumerate(_aircraft_query_candidates(lookup_mfr, model, fallback_title=fallback_title), start=1):
        prompt = _build_aircraft_prompt(cand_mfr, cand_model, response_language=_preferred_language(settings))
        if evidence:
            prompt += "\n\nCurrent web lookup evidence (use it when filling fields if helpful):\n" + json.dumps(evidence, ensure_ascii=False)
        try:
            parsed, sources, raw = await asyncio.to_thread(lambda p=prompt, prv=provider: _provider_generate_json(prv, p, settings, use_search=False, openai_model=(openai_model or _selected_openai_model(settings)), claude_model=(claude_model or _selected_claude_model(settings))))
            if not parsed:
                parsed = _extract_json_pairs_fallback(raw, ['manufacturer_full_name','model','category','engine','engine_type','max_speed','cruise_speed','range','range_nm','ceiling','passenger_capacity','mtow','fuel_capacity','wingspan','length','height','avionics','variants','in_production','aircraft_cost','country_of_origin','date_introduced','summary_html'])
            if evidence and parsed is not None:
                src = evidence.get('source_url')
                if src and src not in (sources or []):
                    sources = [src] + list(sources or [])
            if parsed:
                return parsed, sources, {'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx}
            attempts.append({'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx, 'error': f'No structured data: {raw[:180]}'} )
        except Exception as e:
            detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
            attempts.append({'candidate': f'{cand_mfr} {cand_model}', 'attempt': idx, 'error': detail})
            last_error = detail
    label = 'OpenAI' if provider == 'openai' else 'Claude'
    raise HTTPException(502, f'{label} aircraft lookup failed after {len(attempts)} attempts. Last error: {last_error or "No structured data"}')



async def _run_provider_product_lookup(addon, settings: dict, *, provider: Optional[str] = None, gemini_model: Optional[str] = None, openai_model: Optional[str] = None, claude_model: Optional[str] = None):
    provider = (provider or _selected_ai_provider(settings)).lower().strip()
    if provider == 'gemini':
        return await _run_gemini_product_lookup(addon, settings, model=(gemini_model or _selected_gemini_interactive_model(settings)))
    attempts = []
    last_error = ''
    evidence = _lookup_addon_product_meta_sync(addon.publisher or '', addon.title or '')
    for idx, candidate in enumerate(_addon_query_candidates(addon), start=1):
        prompt = _build_product_prompt(
            addon,
            _addon_sim_label(settings),
            include_overview=True,
            include_features=True,
            search_term=candidate,
            response_language=_preferred_language(settings),
        )
        if evidence:
            prompt += "\n\nCurrent web lookup evidence (use it when filling version/release/list_price/store_name if helpful):\n" + json.dumps(evidence, ensure_ascii=False)
        try:
            parsed, sources, raw = await asyncio.to_thread(
                lambda p=prompt, prv=provider: _provider_generate_json(
                    prv,
                    p,
                    settings,
                    use_search=(provider == 'openai'),
                    openai_model=(openai_model or _selected_openai_model(settings)),
                    claude_model=(claude_model or _selected_claude_model(settings)),
                )
            )
            if not parsed:
                parsed = _extract_json_pairs_fallback(raw, ['latest_current_version','latest_version_date','release_date','list_price','currency','store_name','summary_html','features_html'])
            if evidence and parsed is not None:
                parsed = {**{k: v for k, v in {
                    'latest_current_version': evidence.get('version'),
                    'latest_version_date': evidence.get('latest_version_date'),
                    'release_date': evidence.get('released'),
                    'list_price': evidence.get('price'),
                    'store_name': evidence.get('source_title'),
                }.items() if v not in (None, '')}, **(parsed or {})}
                src = evidence.get('source_url')
                if src and src not in sources:
                    sources = [src] + list(sources or [])
            if parsed:
                return parsed, sources, {'candidate': candidate, 'attempt': idx}
            attempts.append({'candidate': candidate, 'attempt': idx, 'error': f'No structured data: {raw[:180]}'})
        except Exception as e:
            detail = e.response.text[:400] if isinstance(e, requests.HTTPError) and e.response is not None else str(e)
            attempts.append({'candidate': candidate, 'attempt': idx, 'error': detail})
            last_error = detail
    label = 'OpenAI' if provider == 'openai' else 'Claude'
    raise HTTPException(502, f'{label} product lookup failed after {len(attempts)} attempts. Last error: {last_error or "No structured data"}')






@app.get('/api/airport/package-layout/{addon_id}')
async def get_airport_package_layout(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(status_code=404, detail='Add-on not found.')
    layout = await asyncio.to_thread(_parse_airport_layout_from_package_xml, addon)
    if not layout:
        return {'ok': False, 'layout': None, 'detail': 'No readable airport XML layout was found in the add-on package.'}
    return {'ok': True, 'layout': layout}


@app.post('/api/airport/export-layout')
async def export_airport_layout(body: LayoutExportRequest):
    code = (body.icao or body.title or 'airport').strip() or 'airport'
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', code)
    ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    export_dir = LOG_DIR / 'airport_layout_exports'
    out_path = export_dir / f'{safe}_layout_{ts}.json'
    latest_path = export_dir / f'{safe}_layout_latest.json'
    payload = {
        'addon_id': body.addon_id,
        'title': body.title or '',
        'icao': body.icao or '',
        'point': body.point or None,
        'layout': body.layout or {},
        'exported_at': datetime.utcnow().isoformat() + 'Z',
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(serialized, encoding='utf-8')
    try:
        latest_path.write_text(serialized, encoding='utf-8')
    except Exception:
        pass
    return {'ok': True, 'path': str(out_path), 'filename': out_path.name, 'latest_path': str(latest_path)}

@app.get('/api/weather/airport')
async def get_airport_weather(lat: float, lon: float, provider: str = 'aviationweather', icao: str = ''):
    settings = await storage.get_all_settings()
    provider_key = (provider or 'aviationweather').strip().lower()
    units = _openweather_units_from_setting('imperial' if (settings.get('language') or '').strip().lower() == 'english' else 'metric')
    if provider_key == 'aviationweather':
        station = (icao or '').strip().upper()
        if not station:
            raise HTTPException(status_code=400, detail='An ICAO airport code is required for AviationWeather METAR.')
        try:
            payload = await asyncio.to_thread(_fetch_aviationweather_metar, station)
            if not payload:
                raise HTTPException(status_code=404, detail='No METAR data available for this airport right now.')
            return _normalize_aviationweather_payload(payload, icao=station)
        except HTTPException:
            raise
        except requests.HTTPError as exc:
            detail = exc.response.text[:400] if exc.response is not None else str(exc)
            raise HTTPException(status_code=502, detail=f'AviationWeather request failed: {detail}')
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f'AviationWeather request failed: {exc}')
    if provider_key != 'openweather':
        raise HTTPException(status_code=400, detail='Unsupported airport weather provider.')
    api_key = (settings.get('openweather_key') or '').strip()
    if not api_key:
        raise HTTPException(status_code=400, detail='OpenWeather API key is not configured in Settings.')
    try:
        payload = await asyncio.to_thread(_fetch_openweather_current, lat, lon, api_key, units)
        return _normalize_openweather_payload(payload, provider='openweather_current', units=units)
    except requests.HTTPError as exc:
        detail = exc.response.text[:400] if exc.response is not None else str(exc)
        try:
            payload = await asyncio.to_thread(_fetch_openweather_onecall, lat, lon, api_key, units)
            return _normalize_openweather_payload(payload, provider='openweather_onecall', units=units)
        except Exception:
            raise HTTPException(status_code=502, detail=f'OpenWeather request failed: {detail}')
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'OpenWeather request failed: {exc}')

@app.get('/api/ai/usage-status')
async def ai_usage_status():
    settings = await storage.get_all_settings()
    return {
        'selected_provider': _selected_ai_provider(settings),
        'openai_model': _selected_openai_model(settings),
        'claude_model': _selected_claude_model(settings),
        'gemini_interactive_model': _selected_gemini_interactive_model(settings),
        'gemini_bulk_model': _selected_gemini_bulk_model(settings),
        'gemini_detail_mode': _selected_gemini_detail_mode(settings),
        'openai_rate_limits': _last_openai_usage,
        'gemini_status': _last_gemini_status,
        'claude_status': _last_claude_status,
        'gemini_note': 'Gemini remaining quota is not exposed to this app as live remaining headers. Check AI Studio for active rate limits.',
        'gemini_reset_note': 'Gemini free-tier daily request quotas reset at midnight Pacific time.',
        'claude_note': 'Claude remaining quota is not exposed to this app as a live remaining balance. Check the Anthropic Console for usage and limits.',
    }


@app.post('/api/ai/populate-aircraft')
async def ai_populate_aircraft(body: GeminiAircraftRequest):
    settings = await storage.get_all_settings()
    provider = (body.provider or _selected_ai_provider(settings) or '').strip().lower() or _selected_ai_provider(settings)
    if provider == 'gemini' and not settings.get('google_api_key'):
        raise HTTPException(400, 'Google API key not configured in Settings')
    if provider == 'openai' and not settings.get('openai_key'):
        raise HTTPException(400, 'OpenAI API key not configured in Settings')
    if provider == 'claude' and not settings.get('claude_api_key'):
        raise HTTPException(400, 'Claude API key not configured in Settings')
    lookup_mfr = (body.manufacturer_full_name or body.manufacturer or '').strip()
    model = (body.model or '').strip()
    if not lookup_mfr or not model:
        raise HTTPException(400, 'Manufacturer Full Name and Model are required')
    provider_name = ('Gemini Flash-Lite + Google Search' if provider == 'gemini' else (f'OpenAI ({_selected_openai_model(settings)} + two-pass web search)' if provider == 'openai' else f'Claude ({_selected_claude_model(settings)})'))
    model_name = (_selected_gemini_interactive_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings)))
    started_at = datetime.now()
    status = 'success'
    error_message = ''
    try:
        parsed, sources, meta = await _run_provider_aircraft_lookup(provider, settings, lookup_mfr, model, fallback_title=body.model)
        range_nm = _range_nm_from_any(parsed.get('range'), parsed.get('range_nm'))
        return {
            'provider': provider,
            'provider_name': provider_name,
            'manufacturer_full_name': parsed.get('manufacturer_full_name') or lookup_mfr,
            'manufacturer': body.manufacturer or lookup_mfr,
            'model': parsed.get('model') or model,
            'category': parsed.get('category') or '',
            'engine': parsed.get('engine') or '',
            'engine_type': parsed.get('engine_type') or '',
            'max_speed': parsed.get('max_speed') or '',
            'cruise': parsed.get('cruise_speed') or '',
            'range': (f"{range_nm} nm" if range_nm is not None else (parsed.get('range') or '')),
            'range_nm': range_nm,
            'ceiling': parsed.get('ceiling') or '',
            'seats': parsed.get('passenger_capacity') or '',
            'mtow': parsed.get('mtow') or '',
            'fuel_capacity': parsed.get('fuel_capacity') or '',
            'wingspan': parsed.get('wingspan') or '',
            'length': parsed.get('length') or '',
            'height': parsed.get('height') or '',
            'avionics': parsed.get('avionics') or '',
            'variants': parsed.get('variants') or '',
            'in_production': parsed.get('in_production') or '',
            'aircraft_cost': _sanitize_aircraft_cost(parsed.get('aircraft_cost') or ''),
            'country_of_origin': parsed.get('country_of_origin') or '',
            'introduced': parsed.get('date_introduced') or '',
            'source': _source_summary_label(sources, provider_name, fallback=('Grounded web search + title parsing' if provider == 'gemini' else provider_name)),
            'sources': sources,
            'search_candidate': meta.get('candidate'),
            'summary_html': parsed.get('summary_html') or '',
        }
    except Exception as e:
        status = 'error'
        error_message = str(getattr(e, 'detail', '') or e)
        raise
    finally:
        ended_at = datetime.now()
        await _record_ai_log(action=(body.action or 'populate_aircraft_data'), screen=(body.screen or 'detail_aircraft_data'), provider=provider, provider_name=provider_name, model=model_name, addon_title=(body.model or ''), status=status, started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=error_message, details={'requested_provider': body.provider or '', 'resolved_provider': provider, 'manufacturer': lookup_mfr, 'model': model})


@app.post('/api/ai/populate-product/{addon_id}')
async def ai_populate_product(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    settings = await storage.get_all_settings()
    provider = _selected_ai_provider(settings)
    if provider == 'gemini' and not settings.get('google_api_key'):
        raise HTTPException(400, 'Google API key not configured in Settings')
    if provider == 'openai' and not settings.get('openai_key'):
        raise HTTPException(400, 'OpenAI API key not configured in Settings')
    if provider == 'claude' and not settings.get('claude_api_key'):
        raise HTTPException(400, 'Claude API key not configured in Settings')
    provider_name = ('Gemini Flash-Lite + Google Search' if provider == 'gemini' else (f'OpenAI ({_selected_openai_model(settings)} + two-pass web search)' if provider == 'openai' else f'Claude ({_selected_claude_model(settings)})'))
    model_name = (_selected_gemini_interactive_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings)))
    started_at = datetime.now()
    status = 'success'
    error_message = ''
    try:
        parsed, sources, meta = await _run_provider_product_lookup(addon, settings, provider=provider)
        addon = _merge_product_into_addon(addon, parsed, sources, include_overview=True, include_features=True, override_existing=True)
        await storage.upsert_addon(addon)
        return {
            'provider': provider,
            'provider_name': provider_name,
            'latest_version': addon.pr.latest_ver or '',
            'latest_version_date': addon.pr.latest_ver_date or '',
            'released': addon.pr.released or '',
            'price': addon.pr.price,
            'currency': parsed.get('currency') or '',
            'store_name': addon.pr.source_store or '',
            'update_notes_html': addon.pr.update_notes_html or '',
            'sources': sources,
            'source_url': sources[0] if sources else '',
            'source': provider_name,
            'search_candidate': meta.get('candidate'),
            'summary_html': addon.summary or '',
            'features_html': addon.usr.features or '',
        }
    except Exception as e:
        status = 'error'
        error_message = str(getattr(e, 'detail', '') or e)
        raise
    finally:
        ended_at = datetime.now()
        await _record_ai_log(action='populate_product_full', screen='detail_overview', provider=provider, provider_name=provider_name, model=model_name, addon_id=addon_id, addon_title=(addon.title if addon else ''), status=status, started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=error_message)


async def _populate_addon_with_selected_ai(addon, settings: dict, *, provider: Optional[str] = None, use_bulk_model: bool = True, override_existing: bool = True, include_overview: bool = True, include_features: bool = True, include_aircraft_data: bool = True):
    provider = (provider or _selected_ai_provider(settings)).lower().strip()
    gemini_model = _selected_gemini_bulk_model(settings) if use_bulk_model else _selected_gemini_interactive_model(settings)
    openai_model = _selected_openai_model(settings)
    claude_model = _selected_claude_model(settings)
    parsed = {}
    sources = []
    meta = {}
    aircraft_meta = None
    parsed, sources, meta = await _run_provider_product_lookup(addon, settings, provider=provider, gemini_model=gemini_model, openai_model=openai_model, claude_model=claude_model)
    addon = _merge_product_into_addon(addon, parsed, sources, include_overview=include_overview, include_features=include_features, override_existing=override_existing)
    if include_aircraft_data and addon.type == 'Aircraft':
        try:
            lookup_mfr = (addon.rw.manufacturer_full_name or addon.rw.mfr or addon.pr.manufacturer or addon.publisher or '').strip()
            model_name = (addon.rw.model or addon.title or '').strip()
            if lookup_mfr and model_name:
                ap, asources, ameta = await _run_provider_aircraft_lookup(provider, settings, lookup_mfr, model_name, fallback_title=addon.title, gemini_model=gemini_model, openai_model=openai_model, claude_model=claude_model)
                addon = _merge_aircraft_into_addon(addon, ap, asources)
                aircraft_meta = {'candidate': ameta.get('candidate'), 'sources': asources}
        except Exception as e:
            log.warning('AI aircraft follow-up failed addon=%s error=%s', addon.title, e)
    airport_meta = None
    if addon.type == 'Airport':
        try:
            addon, airport_meta = await _enrich_airport_addon_with_lookup(addon, settings, provider)
        except Exception as e:
            log.warning('Airport enrichment failed addon=%s error=%s', addon.title, e)
    guessed_sub = _guess_subtype_for_addon(addon, category=(addon.rw.category or addon.rw.airport_type or ''), title=(addon.title or ''))
    if guessed_sub:
        addon.sub = guessed_sub
    await storage.upsert_addon(addon)
    return addon, {'provider': provider, 'provider_name': ('Gemini Flash-Lite' if provider == 'gemini' else (f'OpenAI ({openai_model} + two-pass web search)' if provider == 'openai' else f'Claude ({claude_model})')), 'search_candidate': meta.get('candidate'), 'product_sources': sources, 'product_source': _source_summary_label(sources, '', fallback=''), 'aircraft_meta': aircraft_meta, 'aircraft_sources': list((aircraft_meta or {}).get('sources') or []), 'aircraft_source': _source_summary_label(list((aircraft_meta or {}).get('sources') or []), '', fallback=(addon.rw.source or '')), 'airport_meta': airport_meta, 'airport_sources': list((airport_meta or {}).get('sources') or []), 'airport_source': _source_summary_label(list((airport_meta or {}).get('sources') or []), '', fallback=(addon.rw.source or ''))}


@app.post('/api/ai/populate-lite/{addon_id}')
async def ai_populate_product_lite(addon_id: str, body: Optional[PopulateLiteOptions] = None):
    """Populate the selected add-on from the right sidebar using the low-cost path."""

    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    settings = await storage.get_all_settings()
    options = body or PopulateLiteOptions()
    provider = (options.provider or _selected_ai_provider(settings)).lower().strip()
    if provider == 'gemini' and not settings.get('google_api_key'):
        raise HTTPException(400, 'Google API key not configured in Settings')
    if provider == 'openai' and not settings.get('openai_key'):
        raise HTTPException(400, 'OpenAI API key not configured in Settings')
    if provider == 'claude' and not settings.get('claude_api_key'):
        raise HTTPException(400, 'Claude API key not configured in Settings')

    provider_name = ('Gemini Flash-Lite + Google Search' if provider == 'gemini' else (f'OpenAI ({_selected_openai_model(settings)} + two-pass web search)' if provider == 'openai' else f'Claude ({_selected_claude_model(settings)})'))
    model_name = (_selected_gemini_bulk_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings)))
    started_at = datetime.now()
    status = 'success'
    error_message = ''
    try:
        addon, info = await _populate_addon_with_selected_ai(addon, settings, provider=provider, use_bulk_model=(False if (options.screen or '') == 'library_selected_addon' else True), override_existing=options.override_existing, include_overview=options.include_overview, include_features=options.include_features, include_aircraft_data=options.include_aircraft_data)
        return {
            'ok': True,
            'addon_id': addon_id,
            'provider': info['provider'],
            'provider_name': info['provider_name'],
            'search_candidate': info.get('search_candidate'),
            'sources': info.get('product_sources') or [],
            'product_sources': info.get('product_sources') or [],
            'product_source': info.get('product_source') or '',
            'aircraft_meta': info.get('aircraft_meta'),
            'aircraft_sources': info.get('aircraft_sources') or [],
            'aircraft_source': info.get('aircraft_source') or '',
            'airport_meta': info.get('airport_meta'),
            'airport_sources': info.get('airport_sources') or [],
            'airport_source': info.get('airport_source') or '',
            'subtype': addon.sub or '',
            'latest_version': addon.pr.latest_ver or '',
            'latest_version_date': addon.pr.latest_ver_date or '',
            'released': addon.pr.released or '',
            'price': addon.pr.price,
            'store_name': addon.pr.source_store or '',
            'update_notes_html': addon.pr.update_notes_html or '',
            'summary_html': addon.summary or '',
            'features_html': addon.usr.features or '',
            'manufacturer': addon.rw.mfr or addon.pr.manufacturer or '',
            'manufacturer_full_name': addon.rw.manufacturer_full_name or addon.rw.mfr or '',
            'model': addon.rw.model or '',
            'category': addon.rw.category or '',
            'engine': addon.rw.engine or '',
            'engine_type': addon.rw.engine_type or '',
            'max_speed': addon.rw.max_speed or '',
            'cruise': addon.rw.cruise or '',
            'range_nm': addon.rw.range_nm,
            'ceiling': addon.rw.ceiling or '',
            'seats': addon.rw.seats or '',
            'mtow': addon.rw.mtow or '',
            'fuel_capacity': addon.rw.fuel_capacity or '',
            'wingspan': addon.rw.wingspan or '',
            'length': addon.rw.length or '',
            'height': addon.rw.height or '',
            'avionics': addon.rw.avionics or '',
            'variants': addon.rw.variants or '',
            'in_production': addon.rw.in_production or '',
            'aircraft_cost': addon.rw.aircraft_cost or '',
            'country_of_origin': addon.rw.country_of_origin or '',
            'introduced': addon.rw.introduced or '',
            'source': addon.rw.source or info.get('product_source') or info['provider_name'],
            'aircraft_source_raw': addon.rw.source or '',
            'wiki_summary': addon.rw.wiki_summary or '',
            'icao': addon.rw.icao or '',
            'faa_id': getattr(addon.rw, 'faa_id', None) or '',
            'name': addon.rw.name or '',
            'city': addon.rw.city or '',
            'municipality': addon.rw.municipality or '',
            'country': addon.rw.country or '',
            'state': addon.rw.state or '',
            'province': addon.rw.province or '',
            'region': addon.rw.region or '',
            'continent': addon.rw.continent or '',
            'elev': addon.rw.elev or '',
            'lat': addon.rw.lat,
            'lon': addon.rw.lon,
            'scheduled': addon.rw.scheduled or '',
            'airport_type': addon.rw.airport_type or '',
            'home_link': addon.rw.home_link or '',
            'wiki_url': addon.rw.wiki_url or '',
            'first_opened': addon.rw.first_opened or '',
            'passenger_count': addon.rw.passenger_count or '',
            'cargo_count': addon.rw.cargo_count or '',
            'us_rank': addon.rw.us_rank or '',
            'world_rank': addon.rw.world_rank or '',
            'hub_airlines': addon.rw.hub_airlines or '',
        }
    except Exception as e:
        status = 'error'
        error_message = str(getattr(e, 'detail', '') or e)
        raise
    finally:
        ended_at = datetime.now()
        await _record_ai_log(action=(options.action or 'populate_selected_addon'), screen=(options.screen or 'library_selected_addon'), provider=provider, provider_name=provider_name, model=model_name, addon_id=addon_id, addon_title=(addon.title if addon else ''), status=status, started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=error_message, details={'requested_provider': options.provider or '', 'resolved_provider': provider, 'include_overview': bool(options.include_overview), 'include_features': bool(options.include_features), 'include_aircraft_data': bool(options.include_aircraft_data), 'override_existing': bool(options.override_existing)})


@app.post('/api/gemini/populate-aircraft')
@app.post('/api/gemini/populate-aircraft')
async def gemini_populate_aircraft(body: GeminiAircraftRequest):
    return await ai_populate_aircraft(body)


@app.post('/api/gemini/populate-product/{addon_id}')
async def gemini_populate_product(addon_id: str):
    return await ai_populate_product(addon_id)


@app.post('/api/gemini/populate-lite/{addon_id}')
async def gemini_populate_product_lite(addon_id: str):
    return await ai_populate_product_lite(addon_id)



async def _enrich_airport_addon_with_lookup(addon, settings: dict, provider: str):
    icao = (addon.rw.icao or '').strip().upper()
    faa_id = (getattr(addon.rw, 'faa_id', None) or '').strip().upper()
    title = (addon.rw.name or addon.title or '').strip()
    merged = _fetch_airport_data_sync(icao=icao, faa_id=faa_id, title=('' if (icao or faa_id) else title))
    sources = []
    try:
        if (provider == 'gemini' and settings.get('google_api_key')) or (provider == 'openai' and settings.get('openai_key')) or (provider == 'claude' and settings.get('claude_api_key')):
            parsed, sources, _raw = await _run_provider_airport_lookup(provider, settings, icao, faa_id, ('' if (icao or faa_id) else (title or merged.get('name') or '')))
            if parsed:
                merged['airport_type'] = parsed.get('airport_type') or merged.get('airport_type')
                merged['municipality'] = parsed.get('municipality') or merged.get('municipality') or merged.get('city')
                merged['city'] = parsed.get('city') or merged.get('city')
                merged['country'] = parsed.get('country') or merged.get('country')
                merged['state'] = parsed.get('state') or merged.get('state')
                merged['province'] = parsed.get('province') or merged.get('province')
                merged['region'] = parsed.get('region') or merged.get('region')
                merged['continent'] = parsed.get('continent') or merged.get('continent')
                merged['first_opened'] = parsed.get('first_opened') or merged.get('first_opened')
                merged['passenger_count'] = parsed.get('passenger_count') or merged.get('passenger_count')
                merged['passenger_year'] = parsed.get('passenger_year') or merged.get('passenger_year')
                merged['cargo_count'] = parsed.get('cargo_count') or merged.get('cargo_count')
                merged['hub_airlines'] = parsed.get('hub_airlines') or merged.get('hub_airlines')
                merged['world_rank'] = parsed.get('world_rank') or merged.get('world_rank')
                merged['us_rank'] = parsed.get('us_rank') or merged.get('us_rank')
                merged['commercial'] = parsed.get('commercial') or merged.get('commercial')
                if parsed.get('summary_html'):
                    merged['wiki_summary'] = parsed.get('summary_html')
                src = parsed.get('source_name') or provider.title()
                if sources:
                    src += ' + ' + ', '.join(sources[:3])
                merged['source'] = src
    except Exception as exc:
        log.warning('Airport AI enrich failed icao=%s faa_id=%s title=%s error=%s', icao, faa_id, title, exc)
    merged = _normalize_airport_region_fields(merged)
    addon.rw.icao = merged.get('icao') or addon.rw.icao
    addon.rw.faa_id = merged.get('faa_id') or getattr(addon.rw, 'faa_id', None)
    _current_code = str((addon.rw.icao or getattr(addon.rw, 'faa_id', None) or '')).strip().upper()
    _returned_code = str((merged.get('icao') or merged.get('faa_id') or '')).strip().upper()
    if (not addon.rw.name) or (_current_code and _returned_code and _current_code == _returned_code):
        addon.rw.name = merged.get('name') or addon.rw.name
    addon.rw.city = merged.get('city') or addon.rw.city
    addon.rw.municipality = merged.get('municipality') or merged.get('city') or addon.rw.municipality
    addon.rw.country = merged.get('country') or addon.rw.country
    addon.rw.state = merged.get('state') or addon.rw.state
    addon.rw.province = merged.get('province') or addon.rw.province
    addon.rw.region = merged.get('region') or addon.rw.region
    addon.rw.continent = merged.get('continent') or addon.rw.continent
    addon.rw.elev = merged.get('elev') or addon.rw.elev
    addon.rw.lat = merged.get('lat') if merged.get('lat') is not None else addon.rw.lat
    addon.rw.lon = merged.get('lon') if merged.get('lon') is not None else addon.rw.lon
    addon.rw.scheduled = merged.get('scheduled') or addon.rw.scheduled
    addon.rw.airport_type = merged.get('airport_type') or addon.rw.airport_type
    addon.rw.home_link = merged.get('home_link') or addon.rw.home_link
    addon.rw.wiki_url = merged.get('wiki_url') or addon.rw.wiki_url
    addon.rw.first_opened = merged.get('first_opened') or addon.rw.first_opened
    addon.rw.passenger_count = merged.get('passenger_count') or addon.rw.passenger_count
    addon.rw.passenger_year = merged.get('passenger_year') or getattr(addon.rw, 'passenger_year', None)
    addon.rw.cargo_count = merged.get('cargo_count') or addon.rw.cargo_count
    addon.rw.us_rank = merged.get('us_rank') or addon.rw.us_rank
    addon.rw.world_rank = merged.get('world_rank') or addon.rw.world_rank
    addon.rw.hub_airlines = merged.get('hub_airlines') or addon.rw.hub_airlines
    addon.rw.commercial = merged.get('commercial') or getattr(addon.rw, 'commercial', None)
    addon.rw.wiki_summary = merged.get('wiki_summary') or getattr(addon.rw, 'wiki_summary', None)
    addon.rw.source = merged.get('source') or addon.rw.source
    if merged.get('airport_type'):
        addon.sub = merged.get('airport_type')
    return addon, {'candidate': title or merged.get('name') or '', 'sources': list(sources or []), 'source': addon.rw.source or ''}


@app.post("/api/addons/{addon_id}/overview-lookup")
async def addon_overview_lookup(addon_id: str):
    addon = await storage.get_addon(addon_id)
    if not addon:
        raise HTTPException(404)
    payload = await asyncio.to_thread(_lookup_addon_product_meta_sync, addon.publisher or '', addon.title or '')
    return payload


class DeleteLogsRequest(BaseModel):
    category: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None


class AIRequest(BaseModel):
    provider: str = 'gemini'
    mode: str = 'enrich'
    prompt: Optional[str] = None
    addon_id: Optional[str] = None
    screen: Optional[str] = None

@app.post('/api/ai/enrich')
async def ai_enrich(body: AIRequest):
    settings = await storage.get_all_settings()
    addon = await storage.get_addon(body.addon_id) if body.addon_id else None
    addon_ctx = ''
    if addon:
        addon_ctx = f"Addon: {addon.title} by {addon.publisher}. Type: {addon.type}/{addon.sub or ''}. ICAO: {addon.rw.icao or ''}. Manufacturer: {addon.rw.mfr or ''}. Country: {addon.rw.country or ''}."
    custom = (body.prompt or '').strip()
    if body.mode == 'prompt' and custom:
        prompt = custom + "\n\nUse this addon context: " + addon_ctx + "\n\nReturn ONLY one valid JSON object with keys: answer_title, answer_text, answer_html, bullets, sources_text, bodyHtml, featuresHtml. answer_text, sources_text, bodyHtml, and featuresHtml must be plain strings or HTML strings. bullets may be an array of short strings. Do not return nested objects. Answer the user's question directly instead of generating a generic addon brief."
    else:
        prompt = f"You are an expert flight simulator addon curator. For the addon '{addon.title if addon else 'Addon'}' by '{addon.publisher if addon else ''}', return ONLY one valid JSON object with keys: headline, description, realWorldInfo, highlights, pilotBriefing, bestFor, compatibility, suggestedTags, verdict, bodyHtml, featuresHtml. All fields except highlights and suggestedTags must be plain strings or HTML strings, not nested objects. {addon_ctx} Rules: bodyHtml and featuresHtml should be rich readable HTML fragments if useful. Do not include markdown fences."
    provider = (body.provider or 'gemini').strip().lower()
    provider_name = ('Gemini Flash-Lite + Google Search' if provider == 'gemini' else (f'OpenAI ({_selected_openai_model(settings)} + two-pass web search)' if provider == 'openai' else f'Claude ({_selected_claude_model(settings)})'))
    model_name = (_selected_gemini_interactive_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings)))
    started_at = datetime.now()
    try:
        parsed, sources, raw = await asyncio.to_thread(lambda: _provider_generate_json(provider, prompt, settings, use_search=(provider=='gemini'), claude_model=_selected_claude_model(settings)))
    except requests.HTTPError as e:
        msg = f'AI request failed: {e.response.text[:400] if e.response is not None else e}'
        ended_at = datetime.now()
        await _record_ai_log(action=('execute_prompt' if body.mode=='prompt' else 'generate_ai_brief'), screen=(body.screen or 'ai_tab'), provider=provider, provider_name=provider_name, model=model_name, addon_id=(body.addon_id or ''), addon_title=(addon.title if addon else ''), status='error', started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=msg, prompt_preview=custom, details={'requested_provider': body.provider or '', 'resolved_provider': provider, 'mode': body.mode})
        raise HTTPException(502, msg)
    except Exception as e:
        msg = f'AI request failed: {e}'
        ended_at = datetime.now()
        await _record_ai_log(action=('execute_prompt' if body.mode=='prompt' else 'generate_ai_brief'), screen=(body.screen or 'ai_tab'), provider=provider, provider_name=provider_name, model=model_name, addon_id=(body.addon_id or ''), addon_title=(addon.title if addon else ''), status='error', started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=msg, prompt_preview=custom, details={'requested_provider': body.provider or '', 'resolved_provider': provider, 'mode': body.mode})
        raise HTTPException(502, msg)
    if not parsed:
        fallback_keys = ['headline','description','realWorldInfo','pilotBriefing','bestFor','compatibility','verdict','bodyHtml','featuresHtml','answer_title','answer_text','answer_html','sources_text']
        parsed = _extract_json_pairs_fallback(raw, fallback_keys)
    if not parsed:
        msg = f'AI returned no structured data: {raw[:300]}'
        ended_at = datetime.now()
        await _record_ai_log(action=('execute_prompt' if body.mode=='prompt' else 'generate_ai_brief'), screen=(body.screen or 'ai_tab'), provider=provider, provider_name=provider_name, model=model_name, addon_id=(body.addon_id or ''), addon_title=(addon.title if addon else ''), status='error', started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), error_message=msg, prompt_preview=custom, details={'requested_provider': body.provider or '', 'resolved_provider': provider, 'mode': body.mode})
        raise HTTPException(502, msg)
    parsed['sources'] = sources
    parsed['mode'] = body.mode
    ended_at = datetime.now()
    await _record_ai_log(action=('execute_prompt' if body.mode=='prompt' else 'generate_ai_brief'), screen=(body.screen or 'ai_tab'), provider=provider, provider_name=provider_name, model=model_name, addon_id=(body.addon_id or ''), addon_title=(addon.title if addon else ''), status='success', started_at=started_at, ended_at=ended_at, duration_seconds=(ended_at-started_at).total_seconds(), prompt_preview=custom, details={'requested_provider': body.provider or '', 'resolved_provider': provider, 'mode': body.mode, 'sources': len(sources or [])})
    return parsed

class LibraryPopulateRequest(BaseModel):
    include_overview: bool = True
    include_features: bool = True
    include_aircraft_data: bool = True
    override_existing: bool = False
    provider: Optional[str] = None
    addon_ids: Optional[list[str]] = None


class PopulateLiteOptions(BaseModel):
    include_overview: bool = True
    include_features: bool = True
    include_aircraft_data: bool = True
    override_existing: bool = True
    provider: Optional[str] = None
    screen: Optional[str] = None
    action: Optional[str] = None


class SubtypePopulateRequest(BaseModel):
    addon_type: str = ''
    all_types: bool = False
    provider: Optional[str] = None


def _canonical_subtype_match(value: str, allowed: list[str]) -> str | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    for item in allowed or []:
        if raw.lower() == str(item).strip().lower():
            return item
    return None


def _subtype_prompt_for_addon(addon: Addon, allowed: list[str], addon_type: str) -> str:
    rw = getattr(addon, 'rw', None)
    pr = getattr(addon, 'pr', None)
    usr = getattr(addon, 'usr', None)
    context = {
        'title': addon.title,
        'publisher': addon.publisher,
        'type': addon_type,
        'current_subtype': addon.sub or '',
        'summary_text': _html_to_text(addon.summary or '')[:1200],
        'features_text': _html_to_text((usr.features if usr else '') or '')[:1800],
        'package_name': addon.package_name or (pr.package_name if pr else '') or '',
        'manufacturer': (rw.mfr if rw else '') or (pr.manufacturer if pr else '') or '',
        'manufacturer_full_name': (rw.manufacturer_full_name if rw else '') or '',
        'model': (rw.model if rw else '') or '',
        'category': (rw.category if rw else '') or '',
        'airport_type': (rw.airport_type if rw else '') or '',
        'icao': (rw.icao if rw else '') or '',
        'source_store': (pr.source_store if pr else '') or (usr.source_store if usr else '') or '',
    }
    return (
        "You classify Microsoft Flight Simulator library items into subtypes. "
        "Return ONLY one JSON object with keys subtype, suggested_new_subtype, reason. "
        f"The add-on type is '{addon_type}'. Allowed existing subtypes for this type are: {json.dumps(allowed, ensure_ascii=False)}. "
        "Choose one of the allowed subtypes whenever possible. Only use suggested_new_subtype when none of the allowed values fit well. "
        "Keep reason short. Here is the add-on context as JSON: " + json.dumps(context, ensure_ascii=False)
    )


async def _ai_pick_subtype(addon: Addon, addon_type: str, allowed: list[str], settings: dict, *, provider: str) -> tuple[str | None, str | None, str]:
    prompt = _subtype_prompt_for_addon(addon, allowed, addon_type)
    gemini_model = _selected_gemini_bulk_model(settings)
    openai_model = _selected_openai_model(settings)
    claude_model = _selected_claude_model(settings)
    parsed, _sources, raw = await asyncio.to_thread(lambda: _provider_generate_json(provider, prompt, settings, use_search=False, gemini_model=gemini_model, openai_model=openai_model, claude_model=claude_model))
    if not parsed:
        parsed = _extract_json_pairs_fallback(raw, ['subtype','suggested_new_subtype','reason'])
    chosen = _canonical_subtype_match(parsed.get('subtype') if isinstance(parsed, dict) else '', allowed)
    suggested = str((parsed.get('suggested_new_subtype') if isinstance(parsed, dict) else '') or '').strip()
    return chosen, suggested, raw[:400]


@app.get('/api/ai/populate-subtypes/status')
async def populate_subtypes_status():
    return _subtype_enrich_progress


@app.post('/api/ai/populate-subtypes/start')
async def populate_subtypes_start(body: SubtypePopulateRequest):
    global _subtype_enrich_running, _subtype_enrich_progress
    if _subtype_enrich_running:
        raise HTTPException(400, 'Subtype populate already running')
    settings = await storage.get_all_settings()
    provider = (body.provider or _selected_ai_provider(settings)).lower().strip()
    if provider == 'gemini' and not settings.get('google_api_key'):
        raise HTTPException(400, 'Google API key not configured in Settings')
    if provider == 'openai' and not settings.get('openai_key'):
        raise HTTPException(400, 'OpenAI API key not configured in Settings')
    if provider == 'claude' and not settings.get('claude_api_key'):
        raise HTTPException(400, 'Claude API key not configured in Settings')

    data_options = _merged_data_options(settings)
    subtype_map = json.loads(json.dumps(data_options.get('subtypes') or {}))
    all_types = [t for t in subtype_map.keys() if t and t != 'External Tool']
    target_types = all_types if body.all_types else [str(body.addon_type or '').strip()]
    target_types = [t for t in target_types if t in all_types]
    if not target_types:
        raise HTTPException(400, 'Choose a valid add-on type or enable All Types.')

    addons = [a for a in (await storage.get_addons()) if getattr(a, 'entry_kind', 'addon') != 'tool' and (a.type in target_types)]
    total = len(addons)
    if total == 0:
        raise HTTPException(400, 'No add-ons found for the selected type scope.')

    _subtype_enrich_running = True
    _subtype_enrich_progress = {
        'running': True,
        'pct': 0,
        'current': 'Preparing…',
        'done': 0,
        'total': total,
        'message': 'Reviewing add-ons and assigning the best subtype from Data Management.',
        'type': 'running',
        'provider': provider,
        'updated': 0,
        'added_subtypes': [],
        'types': target_types,
    }

    async def runner():
        global _subtype_enrich_running, _subtype_enrich_progress
        done = 0
        updated_count = 0
        failures = []
        added_subtypes = []
        try:
            for addon in addons:
                addon_type = addon.type
                allowed = list(subtype_map.get(addon_type) or [])
                _subtype_enrich_progress.update({'current': addon.title, 'done': done, 'pct': int((done/max(total,1))*100)})
                try:
                    chosen, suggested, raw = await _ai_pick_subtype(addon, addon_type, allowed, settings, provider=provider)
                    final_subtype = chosen
                    if not final_subtype and suggested:
                        final_subtype = suggested
                        subtype_map.setdefault(addon_type, [])
                        if not any(final_subtype.lower() == str(x).strip().lower() for x in subtype_map[addon_type]):
                            subtype_map[addon_type].append(final_subtype)
                            subtype_map[addon_type] = sorted([str(x).strip() for x in subtype_map[addon_type] if str(x).strip()], key=lambda s: s.lower())
                            allowed = list(subtype_map[addon_type])
                            added_subtypes.append({'type': addon_type, 'subtype': final_subtype})
                    if final_subtype and (addon.sub or '').strip() != final_subtype:
                        addon.sub = final_subtype
                        await storage.upsert_addon(addon)
                        updated_count += 1
                except Exception as e:
                    failures.append({'addon': addon.title, 'error': str(e)})
                    log.error('Subtype populate failed addon=%s error=%s', addon.title, e, exc_info=True)
                done += 1
                _subtype_enrich_progress.update({'done': done, 'pct': int((done/max(total,1))*100), 'updated': updated_count, 'added_subtypes': added_subtypes})
            await storage.set_json_setting('data_options_subtypes', subtype_map)
            msg = f'Subtype populate complete. Updated {updated_count} add-on(s).'
            if added_subtypes:
                msg += f' Added {len(added_subtypes)} new subtype option(s) to Data Management.'
            if failures:
                msg += f' {len(failures)} add-on(s) had errors. Check the log for details.'
            _subtype_enrich_progress.update({'running': False, 'pct': 100, 'message': msg, 'type': 'done', 'updated': updated_count, 'failures': failures, 'added_subtypes': added_subtypes})
        finally:
            _subtype_enrich_running = False

    asyncio.create_task(runner())
    return {'ok': True, 'provider': provider, 'total': total, 'types': target_types}

@app.get('/api/gemini/populate-library/status')
async def populate_library_status():
    return _enrich_progress

@app.post('/api/gemini/populate-library/start')
async def populate_library_start(body: LibraryPopulateRequest):
    global _enrich_running, _enrich_progress
    if _enrich_running:
        raise HTTPException(400, 'Library populate already running')
    settings = await storage.get_all_settings()
    provider = (body.provider or _selected_ai_provider(settings)).lower()
    gemini_model = _selected_gemini_bulk_model(settings)
    openai_model = _selected_openai_model(settings)
    claude_model = _selected_claude_model(settings)
    if provider == 'gemini' and not settings.get('google_api_key'):
        raise HTTPException(400, 'Google API key not configured in Settings')
    if provider == 'openai' and not settings.get('openai_key'):
        raise HTTPException(400, 'OpenAI API key not configured in Settings')
    if provider == 'claude' and not settings.get('claude_api_key'):
        raise HTTPException(400, 'Claude API key not configured in Settings')
    addons = list((await storage.get_all_addons()).values())
    if body.addon_ids:
        wanted = set(body.addon_ids)
        addons = [a for a in addons if a.id in wanted]
    total = len(addons)
    try:
        await storage.add_event_log({
            'id': uuid.uuid4().hex,
            'category': 'library',
            'action': 'batch_populate_start',
            'screen': 'library_batch_populate',
            'status': 'running',
            'started_at': datetime.now().isoformat(timespec='seconds'),
            'details': {'provider': provider, 'total': total, 'override_existing': bool(body.override_existing), 'include_overview': bool(body.include_overview), 'include_features': bool(body.include_features), 'include_aircraft_data': bool(body.include_aircraft_data)}
        })
    except Exception:
        pass

    _enrich_running = True
    _enrich_progress = {
        'running': True,
        'pct': 0,
        'current': 'Preparing...',
        'done': 0,
        'total': total,
        'message': (
            'Bulk populate will use Gemini Flash-Lite. Existing overview/features are preserved unless Override Existing is enabled.'
            if provider == 'gemini'
            else (
                f'Bulk populate will use OpenAI {openai_model} with two-pass web search. Existing overview/features are preserved unless Override Existing is enabled.'
                if provider == 'openai'
                else f'Bulk populate will use Claude {claude_model}. Existing overview/features are preserved unless Override Existing is enabled.'
            )
        ),
        'type': 'running',
        'provider': provider,
        'model': gemini_model if provider == 'gemini' else (openai_model if provider == 'openai' else claude_model),
    }
    async def runner():
        global _enrich_running, _enrich_progress
        done = 0
        failures = []
        try:
            for addon in addons:
                _enrich_progress.update({'current': addon.title, 'done': done, 'pct': int((done/max(total,1))*100)})
                try:
                    addon, info = await _populate_addon_with_selected_ai(
                        addon,
                        settings,
                        provider=provider,
                        use_bulk_model=True,
                        override_existing=body.override_existing,
                        include_overview=body.include_overview,
                        include_features=body.include_features,
                        include_aircraft_data=body.include_aircraft_data,
                    )
                    if info.get('search_candidate'):
                        log.info('Bulk populate product addon=%s candidate=%s', addon.title, info.get('search_candidate'))
                except Exception as e:
                    failures.append({'addon': addon.title, 'error': str(e)})
                    log.error('Bulk populate failed addon=%s error=%s', addon.title, e, exc_info=True)
                done += 1
                _enrich_progress.update({'done': done, 'pct': int((done/max(total,1))*100)})
            msg = ('Populate complete using Gemini Flash-Lite.' if provider == 'gemini' else (f'Populate complete using OpenAI {openai_model} with two-pass web search.' if provider == 'openai' else f'Populate complete using Claude {claude_model}.'))
            if failures:
                msg += f' {len(failures)} addon(s) had errors. Check the log for details.'
            _enrich_progress.update({'running': False, 'pct': 100, 'message': msg, 'type': 'done', 'failures': failures})
            try:
                await storage.add_event_log({
                    'id': uuid.uuid4().hex,
                    'category': 'library',
                    'action': 'batch_populate_complete',
                    'screen': 'library_batch_populate',
                    'status': 'error' if failures else 'success',
                    'started_at': datetime.now().isoformat(timespec='seconds'),
                    'details': {'provider': provider, 'total': total, 'failures': len(failures), 'message': msg}
                })
            except Exception:
                pass
        finally:
            _enrich_running = False
    asyncio.create_task(runner())
    return {'ok': True, 'provider': provider, 'model': gemini_model if provider == 'gemini' else (openai_model if provider == 'openai' else claude_model)}

@app.get("/api/research/search")
async def research_search(
    q: str = Query(..., min_length=2),
    context: str = Query('web'),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=20),
):
    query = (q or '').strip()
    context = (context or 'web').lower()
    if not query:
        return {"query": "", "results": [], "engine": "Web", "errors": [], 'page': 1, 'total_pages': 1, 'total_results': 0}

    cached = _search_cache_get(query, context)
    if cached is None:
        variants = _search_variants(query, context)
        errors = []
        engine_hits: dict[str, list[dict]] = {}

        async def run_provider(label: str, fn):
            try:
                hits = await asyncio.to_thread(fn)
                return label, hits or []
            except Exception as e:
                return label, e

        tasks = []
        for variant in variants:
            tasks.append(run_provider('Google', lambda v=variant: _search_google(v, 24, context)))
            tasks.append(run_provider('DuckDuckGo', lambda v=variant: _search_duckduckgo(v, context)))
            if context not in {'video'}:
                tasks.append(run_provider('Wikipedia', lambda v=variant: _search_wikipedia(v, context)))

        done = await asyncio.gather(*tasks)
        for label, value in done:
            if isinstance(value, Exception):
                errors.append(f"{label}: {value}")
            elif value:
                engine_hits.setdefault(label, []).extend(value)

        merged = []
        for label in ['Google', 'DuckDuckGo', 'Wikipedia']:
            merged.extend(engine_hits.get(label, []))
        auto_open_url = _youtube_search_url(query) if _youtube_mode(query, context) else ''
        ranked = _rank_results(query, merged, context)
        if _youtube_mode(query, context):
            ranked = [r for r in ranked if ('youtube.com' in (urlparse(r.get('url') or '').netloc.lower()) or 'youtu.be' in (urlparse(r.get('url') or '').netloc.lower()))]
        if not ranked and merged:
            # fallback: keep English/raw unique results instead of returning an empty list
            raw_seen = set(); fallback = []
            for r in merged:
                url = _clean_result_url(r.get('url') or '')
                title = r.get('title') or ''
                snippet = r.get('snippet') or ''
                if not url or url in raw_seen:
                    continue
                if _youtube_mode(query, context) and not any(dom in urlparse(url).netloc.lower() for dom in ['youtube.com','youtu.be']):
                    continue
                if not _is_probably_english_result(title, url, snippet):
                    continue
                raw_seen.add(url)
                fallback.append({**r, 'url': url, 'display_url': _display_result_url(url), 'score': _score_result(query, title, url, snippet, context)})
            fallback.sort(key=lambda r: (-r.get('score',0), len(r.get('title') or '')))
            ranked = fallback
        engine = ' + '.join(engine_hits.keys()) if engine_hits else ('Offline' if errors else 'Web')
        cached = {'ts': time.time(), 'results_all': ranked, 'engine': engine, 'errors': errors[:3], 'auto_open_url': auto_open_url}
        _search_cache_set(query, context, cached)

    all_results = cached.get('results_all') or []
    total_results = len(all_results)
    total_pages = max(1, (total_results + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start_i = (page - 1) * page_size
    end_i = start_i + page_size
    return {
        'query': query,
        'results': all_results[start_i:end_i],
        'engine': cached.get('engine') or 'Web',
        'errors': cached.get('errors') or [],
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'total_results': total_results,
        'auto_open_url': cached.get('auto_open_url') or '',
    }


@app.get("/api/research/searchpage")
async def research_searchpage(
    q: str = Query(..., min_length=2),
    context: str = Query('web'),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=20),
):
    data = await research_search(q=q, context=context, page=page, page_size=page_size)
    return HTMLResponse(_simple_results_html(data.get("engine") or "Web", q, data.get("results") or [], data.get('page') or 1, data.get('total_pages') or 1, data.get('total_results') or 0))


def _framed_page(url: str) -> str:
    return f"<html><head><meta charset='utf-8'>{_postmessage_script(url)}<style>html,body{{margin:0;height:100%;background:#fff}}iframe{{width:100%;height:100%;border:0}}</style></head><body><iframe src='{escape(url, quote=True)}' referrerpolicy='no-referrer-when-downgrade' allow='clipboard-read; clipboard-write'></iframe></body></html>"


@app.get("/api/research/open")
async def research_open(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "Only http/https URLs are allowed")
    try:
        host = parsed.netloc.lower()
        if any(dom in host for dom in ["skyvector.com", "microsoft.com", "youtube.com", "youtu.be"]):
            return HTMLResponse(_framed_page(url))
        html = _proxy_html(url)
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<html><body><h3>Could not open page</h3><p>{escape(str(e))}</p><p><a href='{escape(url)}'>{escape(url)}</a></p></body></html>", status_code=502)


@app.get("/api/research/google")
async def research_google(q: str = Query(..., min_length=2)):
    return await research_searchpage(q)


@app.get("/api/research/title")
async def research_title(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "Only http/https URLs are allowed")
    try:
        html, _ = _fetch_url(url)
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else urlparse(url).netloc
        return {"title": title or url}
    except Exception:
        return {"title": urlparse(url).netloc or url}


def _readable_article_html(url: str) -> tuple[str, str]:
    html, _ = _fetch_url(url, timeout=20)
    soup = BeautifulSoup(html, 'html.parser')
    title = (soup.title.string or '').strip() if soup.title and soup.title.string else urlparse(url).netloc

    def _meta(*, prop: str = '', name: str = '') -> str:
        tag = None
        if prop:
            tag = soup.find('meta', attrs={'property': prop})
        if not tag and name:
            tag = soup.find('meta', attrs={'name': name})
        return (tag.get('content') or '').strip() if tag else ''

    og_title = _meta(prop='og:title')
    og_desc = _meta(prop='og:description') or _meta(name='description') or _meta(name='twitter:description')
    if og_title and len(og_title) > len(title):
        title = og_title

    for bad in soup(['script','noscript','style','meta','link','svg','canvas','iframe','form','nav','footer','header','aside']):
        bad.decompose()
    root = soup.select_one('article') or soup.select_one('main') or soup.select_one('[role=main]')
    if not root:
        candidates = sorted([n for n in soup.find_all(['div','section']) if len(n.find_all('p')) >= 2], key=lambda n: len(n.get_text(' ', strip=True)), reverse=True)
        root = candidates[0] if candidates else (soup.body or soup)
    keep_tags = {'h1','h2','h3','h4','p','ul','ol','li','blockquote','table','thead','tbody','tr','th','td','img','figure','figcaption','a','strong','em','b','i','hr'}
    cleaned = BeautifulSoup('<div class="article-body"></div>', 'html.parser')
    dest = cleaned.div
    h = cleaned.new_tag('h2')
    h.string = title or url
    dest.append(h)
    if og_desc:
        lead = cleaned.new_tag('p')
        lead['style'] = 'font-size:1.02em;opacity:.92'
        lead.string = og_desc
        dest.append(lead)

    count = 0
    seen_text = set()
    for node in root.find_all(list(keep_tags)):
        clone = BeautifulSoup(str(node), 'html.parser').find(node.name)
        if clone is None:
            continue
        text_key = clone.get_text(' ', strip=True)[:240]
        if text_key and text_key in seen_text:
            continue
        if text_key:
            seen_text.add(text_key)
        for tag in clone.find_all(True):
            attrs = {}
            if tag.name == 'a' and tag.get('href'):
                attrs['href'] = urljoin(url, tag.get('href'))
                attrs['target'] = '_blank'
                attrs['rel'] = 'noreferrer'
            if tag.name == 'img' and tag.get('src'):
                attrs['src'] = urljoin(url, tag.get('src'))
                attrs['alt'] = tag.get('alt','')
            tag.attrs = attrs
        if clone.name == 'img' and clone.get('src'):
            clone['src'] = urljoin(url, clone.get('src'))
        dest.append(clone)
        count += 1
        if count >= 120:
            break

    if len(dest.get_text(' ', strip=True)) < 180:
        extras = []
        for sel in ['h1', '[itemprop="description"]', '.product-description', '.description', '.summary', '.content', '.product-details']:
            for n in soup.select(sel):
                txt = n.get_text(' ', strip=True)
                if txt and txt not in extras and len(txt) > 30:
                    extras.append(txt)
                if len(extras) >= 5:
                    break
            if len(extras) >= 5:
                break
        for txt in extras:
            p = cleaned.new_tag('p')
            p.string = txt
            dest.append(p)

    style = "<style>body{font-family:Segoe UI,Arial,sans-serif;line-height:1.6} img{max-width:100%;height:auto;border-radius:8px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #cbd5e1;padding:6px 8px} a{color:#2563eb}</style>"
    return title, style + str(dest)


@app.get('/api/research/readable')
async def research_readable(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {'http','https'}:
        raise HTTPException(400, 'Only http/https URLs are allowed')
    try:
        title, html = _readable_article_html(url)
        return {'title': title, 'url': url, 'html': html}
    except Exception as e:
        raise HTTPException(502, f'Could not read article: {e}')



async def _record_scan_log(*, result, addons_root: str, selected_paths: list[str], populate_new_ai: bool, ai_provider: str | None, ai_populated: int, duration_seconds: float, cancelled: bool = False, error_message: str = ''):
    try:
        entry = {
            'id': uuid.uuid4().hex,
            'scan_log_path': str(SCAN_LOG_FILE),
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'addons_root': addons_root or '',
            'selected_paths': selected_paths or [],
            'populate_new_ai': bool(populate_new_ai),
            'ai_provider': ai_provider or '',
            'ai_populated': int(ai_populated or 0),
            'duration_seconds': round(float(duration_seconds or 0.0), 1),
            'cancelled': bool(cancelled),
            'error_message': error_message or '',
            'summary': {
                'added': len(getattr(result, 'added', []) or []),
                'updated': len(getattr(result, 'updated', []) or []),
                'removed': len(getattr(result, 'removed', []) or []),
                'ignored': int(getattr(result, 'skipped_ignored', 0) or 0),
                'version_updates': len(getattr(result, 'version_updates', []) or []),
            },
            'added_items': [
                {
                    'title': a.title,
                    'publisher': a.publisher,
                    'type': a.type,
                    'version': a.pr.ver or '',
                    'path': a.addon_path,
                }
                for a in (getattr(result, 'added', []) or [])
            ][:500],
            'version_updates': list(getattr(result, 'version_updates', []) or [])[:500],
        }
        scan_lines = [f"[{entry['timestamp']}] Scan root={addons_root or ''}"]
        for item in entry['added_items']:
            scan_lines.append(f"  ADDED   {item.get('title') or 'Untitled'} | package={item.get('path') or ''} | version={item.get('version') or ''}")
        for item in entry['version_updates']:
            scan_lines.append(f"  UPDATED {item.get('title') or 'Untitled'} | {item.get('from_version') or 'Unknown'} -> {item.get('to_version') or 'Unknown'}")
        if error_message:
            scan_lines.append(f"  ERROR   {error_message}")
        _append_scan_log_lines(scan_lines)
        logs = await storage.get_json_setting('scan_logs', [])
        if not isinstance(logs, list):
            logs = []
        logs = [entry] + logs[:49]
        await storage.set_json_setting('scan_logs', logs)
        await storage.add_event_log({
            'id': entry['id'],
            'category': 'scan',
            'action': 'library_scan',
            'started_at': entry['timestamp'],
            'ended_at': entry['timestamp'],
            'duration_seconds': entry['duration_seconds'],
            'screen': 'library_scan',
            'status': 'cancelled' if entry['cancelled'] else ('error' if entry['error_message'] else 'success'),
            'error_message': entry['error_message'],
            'details': {
                'addons_root': entry['addons_root'],
                'selected_paths': entry['selected_paths'],
                'populate_new_ai': entry['populate_new_ai'],
                'ai_provider': entry['ai_provider'],
                'ai_populated': entry['ai_populated'],
                'cancelled': entry['cancelled'],
                'added_items': entry['added_items'],
                'version_updates': entry['version_updates'],
            },
            'summary': entry['summary'],
        })
    except Exception as e:
        log.warning('Could not record scan log: %s', e)


async def _record_ai_log(*, action: str, screen: str, provider: str, provider_name: str = '', model: str = '', addon_id: str = '', addon_title: str = '', status: str = 'success', started_at: Optional[datetime] = None, ended_at: Optional[datetime] = None, duration_seconds: float = 0.0, error_message: str = '', prompt_preview: str = '', details: Optional[dict] = None):
    try:
        started_at = started_at or datetime.now()
        ended_at = ended_at or datetime.now()
        entry = {
            'id': uuid.uuid4().hex,
            'scan_log_path': str(AI_LOG_FILE),
            'action': action or '',
            'screen': screen or '',
            'provider': provider or '',
            'provider_name': provider_name or provider or '',
            'model': model or '',
            'addon_id': addon_id or '',
            'addon_title': addon_title or '',
            'status': status or 'success',
            'started_at': started_at.isoformat(timespec='seconds'),
            'ended_at': ended_at.isoformat(timespec='seconds'),
            'duration_seconds': round(float(duration_seconds or 0.0), 1),
            'error_message': (error_message or '')[:1200],
            'prompt_preview': (prompt_preview or '')[:240],
            'details': details or {},
        }
        ai_lines = [f"[{entry['started_at']}] {entry['status'].upper()} {entry['action']} | provider={entry['provider_name'] or entry['provider']} | model={entry['model'] or ''} | addon={entry['addon_title'] or entry['addon_id'] or ''}"]
        if entry['error_message']:
            ai_lines.append(f"  ERROR   {entry['error_message']}")
        if entry['prompt_preview']:
            ai_lines.append(f"  PROMPT  {entry['prompt_preview']}")
        _append_ai_log_lines(ai_lines)
        logs = await storage.get_json_setting('ai_logs', [])
        if not isinstance(logs, list):
            logs = []
        logs = [entry] + logs[:199]
        await storage.set_json_setting('ai_logs', logs)
        await storage.add_event_log({'category':'ai', **entry})
    except Exception as e:
        log.warning('Could not record AI log: %s', e)



async def _record_library_event(action: str, *, screen: str = '', addon_id: str = '', addon_title: str = '', status: str = 'success', details: Optional[dict] = None, summary: Optional[dict] = None):
    try:
        ts = datetime.now().isoformat(timespec='seconds')
        entry = {
            'id': str(uuid.uuid4()),
            'category': 'library',
            'action': str(action or ''),
            'started_at': ts,
            'ended_at': ts,
            'duration_seconds': 0.0,
            'screen': str(screen or ''),
            'addon_id': str(addon_id or ''),
            'addon_title': str(addon_title or ''),
            'status': str(status or 'success'),
            'details': details or {},
            'summary': summary or {},
        }
        await storage.add_event_log(entry)
    except Exception as e:
        log.warning('Could not record library event: %s', e)

@app.get('/api/logs/scan')
async def get_scan_logs():
    logs = await storage.list_event_logs('scan', limit=120)
    if logs:
        items = []
        for item in logs:
            details = item.get('details') or {}
            items.append({
                'id': item.get('id'),
                'timestamp': item.get('started_at') or item.get('created_at') or '',
                'duration_seconds': item.get('duration_seconds') or 0,
                'selected_paths': details.get('selected_paths') or [],
                'summary': item.get('summary') or {},
                'populate_new_ai': bool(details.get('populate_new_ai')),
                'ai_provider': details.get('ai_provider') or '',
                'ai_populated': details.get('ai_populated') or 0,
                'cancelled': bool(details.get('cancelled')),
                'error_message': item.get('error_message') or '',
                'added_items': details.get('added_items') or [],
                'version_updates': details.get('version_updates') or [],
            })
        return {'items': items}
    logs = await storage.get_json_setting('scan_logs', [])
    if not isinstance(logs, list):
        logs = []
    return {'items': logs}


@app.get('/api/logs/ai')
async def get_ai_logs():
    items = []
    seen = set()
    for item in await storage.list_event_logs('ai', limit=250):
        row = {
            'id': item.get('id'),
            'action': item.get('action') or '',
            'screen': item.get('screen') or '',
            'provider': item.get('provider') or '',
            'provider_name': item.get('provider_name') or item.get('provider') or '',
            'model': item.get('model') or '',
            'addon_id': item.get('addon_id') or '',
            'addon_title': item.get('addon_title') or '',
            'status': item.get('status') or '',
            'started_at': item.get('started_at') or item.get('created_at') or '',
            'ended_at': item.get('ended_at') or item.get('created_at') or '',
            'duration_seconds': item.get('duration_seconds') or 0,
            'error_message': item.get('error_message') or '',
            'prompt_preview': item.get('prompt_preview') or '',
            'details': item.get('details') or {},
        }
        key = str(row.get('id') or '') or f"{row.get('started_at','')}|{row.get('action','')}|{row.get('addon_title','')}"
        if key in seen:
            continue
        seen.add(key)
        items.append(row)
    logs = await storage.get_json_setting('ai_logs', [])
    if isinstance(logs, list):
        for item in logs:
            row = {
                'id': item.get('id'),
                'action': item.get('action') or '',
                'screen': item.get('screen') or '',
                'provider': item.get('provider') or '',
                'provider_name': item.get('provider_name') or item.get('provider') or '',
                'model': item.get('model') or '',
                'addon_id': item.get('addon_id') or '',
                'addon_title': item.get('addon_title') or '',
                'status': item.get('status') or '',
                'started_at': item.get('started_at') or '',
                'ended_at': item.get('ended_at') or '',
                'duration_seconds': item.get('duration_seconds') or 0,
                'error_message': item.get('error_message') or '',
                'prompt_preview': item.get('prompt_preview') or '',
                'details': item.get('details') or {},
            }
            key = str(row.get('id') or '') or f"{row.get('started_at','')}|{row.get('action','')}|{row.get('addon_title','')}"
            if key in seen:
                continue
            seen.add(key)
            items.append(row)
    items.sort(key=lambda x: str(x.get('started_at') or x.get('ended_at') or ''), reverse=True)
    return {'items': items[:250]}


@app.get('/api/logs/events')
async def get_event_logs(category: Optional[str] = None, limit: int = 250):
    return {'items': await storage.list_event_logs(category, limit=limit)}


@app.post('/api/logs/delete-range')
async def delete_logs_range(body: DeleteLogsRequest):
    result = await storage.delete_event_logs_range(category=(body.category or None), start_at=(body.start_at or None), end_at=(body.end_at or None))
    return {'ok': True, **result}


@app.websocket("/ws/scan")
async def websocket_scan(ws: WebSocket):
    global _scan_cancel, _scan_running
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")
            if action == "stop":
                if _scan_cancel:
                    _scan_cancel.set()
                await ws.send_json({"type": "stopping"})
                continue
            if action != "start":
                continue
            if _scan_running:
                await ws.send_json({"type": "error", "message": "Scan already in progress"})
                continue
            addons_root = await storage.get_setting("addons_root")
            community = await storage.get_setting("community_dir")
            selected_paths = msg.get("selected_paths")
            if not isinstance(selected_paths, list):
                selected_paths = await storage.get_json_setting("scan_selected_paths", [])
            populate_new_ai = bool(msg.get('populate_new_ai'))
            if not addons_root:
                await ws.send_json({"type": "error", "message": "Set Addons Root in Settings first."})
                continue
            _scan_cancel = asyncio.Event()
            _scan_running = True
            scan_started = time.time()
            result = scan_module.ScanResult()
            ai_populated = 0
            provider = ''
            try:
                existing = await storage.get_all_addons(include_removed=True)
                ignored_rules = await storage.list_ignored_addons()
                async def progress_cb(m: dict):
                    if m.get('type') == 'done':
                        return
                    await ws.send_json(m)
                activated_only = (await storage.get_setting("scan_activated_only", "0")) == "1"
                result = await scan_module.scan_addons(addons_root, community, existing, progress_cb, _scan_cancel, selected_paths=selected_paths, activated_only=activated_only, ignored_rules=ignored_rules)
                if result.added or result.updated:
                    await storage.upsert_many(result.added + result.updated)
                if result.removed:
                    await storage.mark_removed(result.removed)
                if populate_new_ai and result.added:
                    settings = await storage.get_all_settings()
                    provider = _selected_ai_provider(settings)
                    provider_ok = (provider == 'gemini' and settings.get('google_api_key')) or (provider == 'openai' and settings.get('openai_key')) or (provider == 'claude' and settings.get('claude_api_key'))
                    provider_name = ('Gemini Flash-Lite + Google Search' if provider == 'gemini' else (f'OpenAI ({_selected_openai_model(settings)} + two-pass web search)' if provider == 'openai' else f'Claude ({_selected_claude_model(settings)})'))
                    if provider_ok:
                        total_new = len(result.added)
                        await ws.send_json({'type':'ai-progress','current':'Preparing AI populate','pct':0,'done':0,'total':total_new,'provider_name':provider_name,'message':'Populate new add-ons with AI is running after the manifest scan. This can take a while, and you can keep using the app, but the system may feel slower until it finishes.'})
                        for idx, addon in enumerate(result.added, start=1):
                            if _scan_cancel.is_set():
                                break
                            await ws.send_json({'type':'ai-progress','current':addon.title,'pct':round((idx-1)/max(total_new,1)*100,1),'done':idx-1,'total':total_new,'provider_name':provider_name,'message':'Running selected-AI populate for new add-ons. Rich overview/features generation can take a while.'})
                            ai_started = datetime.now()
                            try:
                                await _populate_addon_with_selected_ai(addon, settings, provider=provider, use_bulk_model=True, override_existing=True, include_overview=True, include_features=True, include_aircraft_data=True)
                                ai_populated += 1
                                ai_ended = datetime.now()
                                await _record_ai_log(action='scan_populate_new_addon', screen='scan_followup_ai', provider=provider, provider_name=provider_name, model=(_selected_gemini_bulk_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings))), addon_id=addon.id, addon_title=addon.title, status='success', started_at=ai_started, ended_at=ai_ended, duration_seconds=(ai_ended-ai_started).total_seconds(), details={'requested_provider': provider, 'resolved_provider': provider})
                            except Exception as e:
                                ai_ended = datetime.now()
                                await _record_ai_log(action='scan_populate_new_addon', screen='scan_followup_ai', provider=provider, provider_name=provider_name, model=(_selected_gemini_bulk_model(settings) if provider == 'gemini' else (_selected_openai_model(settings) if provider == 'openai' else _selected_claude_model(settings))), addon_id=addon.id, addon_title=addon.title, status='error', started_at=ai_started, ended_at=ai_ended, duration_seconds=(ai_ended-ai_started).total_seconds(), error_message=str(e), details={'requested_provider': provider, 'resolved_provider': provider})
                                log.warning('Scan follow-up AI populate failed addon=%s error=%s', addon.title, e)
                        await ws.send_json({'type':'ai-progress','current':'Complete','pct':100,'done':ai_populated,'total':total_new,'provider_name':provider_name,'message':'Selected-AI populate finished for new add-ons.'})
                duration_seconds = time.time() - scan_started
                await _record_scan_log(result=result, addons_root=addons_root, selected_paths=selected_paths or [], populate_new_ai=populate_new_ai, ai_provider=provider, ai_populated=ai_populated, duration_seconds=duration_seconds, cancelled=_scan_cancel.is_set())
                await ws.send_json({'type':'done','scanned':result.skipped_ignored + len(result.added) + len(result.updated),'total':result.skipped_ignored + len(result.added) + len(result.updated),'added':len(result.added),'updated':len(result.updated),'removed':len(result.removed),'ignored':result.skipped_ignored,'ai_populated':ai_populated,'version_updates':len(result.version_updates)})
            except Exception as e:
                log.error("Scan failed: %s", e, exc_info=True)
                await _record_scan_log(result=result, addons_root=addons_root, selected_paths=selected_paths or [], populate_new_ai=populate_new_ai, ai_provider=provider, ai_populated=ai_populated, duration_seconds=(time.time()-scan_started if 'scan_started' in locals() else 0), cancelled=_scan_cancel.is_set() if _scan_cancel else False, error_message=str(e))
                await ws.send_json({"type": "error", "message": str(e)})
            finally:
                _scan_running = False
                _scan_cancel = None
    except WebSocketDisconnect:
        if _scan_cancel:
            _scan_cancel.set()
        _scan_running = False

@app.get("/api/scan/status")
async def scan_status():
    return {"running": _scan_running}


@app.get("/api/browser/state")
async def browser_state():
    return {**_browser_state, 'shell_mode': os.environ.get('HANGAR_SHELL_MODE', 'browser')}

@app.post("/api/browser/script")
async def browser_script(body: BrowserScriptRequest):
    _update_browser_state(requested_script=body.script, script_id=(body.script_id or time.time_ns()))
    return {"ok": True, "script_id": _browser_state.get('script_id', 0)}

@app.post("/api/browser/open")
async def browser_open(body: BrowserOpenRequest):
    parsed = urlparse(body.url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "Only http/https URLs are allowed")
    log.info('Browser open requested title=%s url=%s', str(body.title or body.url)[:160], str(body.url)[:1000])
    try:
        q = parse_qs(parsed.query or '').get('q', [''])[0]
        logger = get_logger('frontend')
        logger.info('BROWSER URL — url=%s search=%s', str(body.url)[:1500], q)
        if q or body.title:
            await _record_library_event('web_search', screen='browser', details={'url': body.url, 'title': body.title or '', 'search_query': q})
    except Exception:
        pass
    _update_browser_state(requested_url=body.url, requested_title=body.title or body.url, request_id=(body.request_id or time.time_ns()), visible=True, minimal_controls=bool(body.minimal_controls), panel_kind=(body.panel_kind or ''))
    return {"ok": True, "url": body.url, "request_id": _browser_state.get('request_id', 0)}

@app.post("/api/browser/update")
async def browser_update(body: BrowserUpdateRequest):
    _update_browser_state(current_url=body.current_url, current_title=body.current_title, visible=body.visible)
    return {"ok": True}

@app.post("/api/browser/close")
async def browser_close():
    _update_browser_state(
        visible=False,
        requested_url="",
        requested_title="",
        current_url="",
        current_title="",
        minimal_controls=False,
        panel_kind="",
        requested_script="",
        script_id=0,
    )
    return {"ok": True}

@app.get("/api/flight/status")
async def flight_status():
    settings = await storage.get_json_setting('flight_tracker_settings', {'poll_interval': 1.0})
    status = _flight_tracker.status()
    status['config'] = {'poll_interval': float((settings or {}).get('poll_interval', 1.0) or 1.0)}
    return status


@app.post("/api/flight/connect")
async def flight_connect(request: Request):
    payload = {}
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    raw_interval = payload.get('poll_interval', 1.0)
    try:
        poll_interval = max(0.4, min(5.0, float(raw_interval or 1.0)))
    except Exception:
        poll_interval = 1.0
    _simconnect_endpoint_log('info', 'API /api/flight/connect entered. poll_interval=%.2fs payload=%s', poll_interval, str(payload)[:500])
    await storage.set_json_setting('flight_tracker_settings', {'poll_interval': poll_interval})
    configured = _flight_tracker.configure(poll_interval=poll_interval)
    _simconnect_endpoint_log('info', 'API /api/flight/connect configured state=%s available=%s', str(configured.get('state') or ''), bool(configured.get('available')))
    status = _flight_tracker.connect()
    _simconnect_endpoint_log('info', 'API /api/flight/connect returning. state=%s connected=%s available=%s error=%s', str(status.get('state') or ''), bool(status.get('connected')), bool(status.get('available')), str(status.get('last_error') or ''))
    return status


@app.post("/api/flight/disconnect")
async def flight_disconnect():
    _simconnect_endpoint_log('info', 'API /api/flight/disconnect entered.')
    status = _flight_tracker.disconnect()
    _simconnect_endpoint_log('info', 'API /api/flight/disconnect returning. state=%s connected=%s', str(status.get('state') or ''), bool(status.get('connected')))
    return status





class FlightCommandRequest(BaseModel):
    command: str = ''


class FlightRepositionRequest(BaseModel):
    lat: float
    lon: float
    altitude_ft: float | None = None
    heading_deg: float | None = None
    speed_kt: float | None = None


class FlightRouteControllerRequest(BaseModel):
    points: list[dict] = []
    altitude_ft: float | None = None
    speed_kt: float | None = None
    heading_deg: float | None = None
    loop: bool = False
    control_mode: str | None = None


class FlightRouteJumpRequest(BaseModel):
    waypoint_index: int = 0

@app.post('/api/flight/command')
async def flight_command(body: FlightCommandRequest):
    cmd = str(body.command or '').strip().lower()
    result = _flight_tracker.command(cmd)
    _simconnect_endpoint_log('info', 'API /api/flight/command command=%s result=%s', cmd, str(result)[:500])
    return result


@app.post('/api/flight/reposition')
async def flight_reposition(body: FlightRepositionRequest):
    result = _flight_tracker.reposition(lat=body.lat, lon=body.lon, altitude_ft=body.altitude_ft, heading_deg=body.heading_deg, speed_kt=body.speed_kt)
    _simconnect_endpoint_log('info', 'API /api/flight/reposition result=%s', str(result)[:500])
    return result


@app.post('/api/flight/route/start')
async def flight_route_start(body: FlightRouteControllerRequest):
    result = _flight_tracker.start_route_controller(points=body.points, altitude_ft=body.altitude_ft, speed_kt=body.speed_kt, heading_deg=body.heading_deg, loop=body.loop, control_mode=body.control_mode or 'virtual-direct')
    _simconnect_endpoint_log('info', 'API /api/flight/route/start result=%s', str(result)[:500])
    return result


@app.post('/api/flight/route/stop')
async def flight_route_stop():
    result = _flight_tracker.stop_route_controller()
    _simconnect_endpoint_log('info', 'API /api/flight/route/stop result=%s', str(result)[:500])
    return result


@app.post('/api/flight/route/jump')
async def flight_route_jump(body: FlightRouteJumpRequest):
    result = _flight_tracker.jump_to_route_waypoint(body.waypoint_index)
    _simconnect_endpoint_log('info', 'API /api/flight/route/jump waypoint_index=%s result=%s', body.waypoint_index, str(result)[:500])
    return result

@app.get('/api/flight/logs')
async def flight_logs():
    try:
        path = USER_DATA_DIR / 'flight_logs.json'
        if not path.exists():
            return {'items': []}
        data = json.loads(path.read_text(encoding='utf-8'))
        return {'items': data if isinstance(data, list) else []}
    except Exception as exc:
        return {'items': [], 'error': str(exc)}

@app.get('/api/pomax/status')
async def pomax_status():
    return get_pomax_status()


@app.post('/api/pomax/start')
async def pomax_start(request: Request):
    mode = request.query_params.get('mode', 'live')
    try:
        body = await request.json()
        if isinstance(body, dict) and body.get('mode'):
            mode = str(body.get('mode'))
    except Exception:
        pass
    return start_pomax(mode=mode)


@app.post('/api/pomax/stop')
async def pomax_stop():
    return stop_pomax()


@app.post('/api/pomax/load-flightplan')
async def pomax_load_flightplan(body: PomaxFlightPlanRequest):
    points = _normalize_route_points(body.points or [])
    if len(points) < 2:
        raise HTTPException(400, 'At least two valid route points are required.')
    status = get_pomax_status()
    if not status.get('ready'):
        raise HTTPException(409, 'Integrated Virtual Pilot is not ready yet.')
    if body.open_panel is not False:
        _update_browser_state(
            requested_url=status.get('web_url') or 'http://127.0.0.1:3300',
            requested_title='Integrated Virtual Pilot',
            request_id=time.time_ns(),
            visible=True,
            minimal_controls=True,
            panel_kind='vp',
        )
    _update_browser_state(requested_script=_build_pomax_load_script(points, str(body.name or 'Hangar Route')), script_id=time.time_ns())
    return {'ok': True, 'count': len(points), 'message': f'Loaded {len(points)} Hangar route waypoints into the integrated Virtual Pilot.'}


@app.post('/api/pomax/route-file/save')
async def pomax_route_file_save(body: PomaxRouteFileRequest):
    try:
        result = _write_vp_route_file(name=str(body.name or 'Hangar Route'), points=body.points or [], file_name=str(body.file_name or ''))
        return {'ok': True, **result, 'message': f"Saved route file {result['file_name']}"}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post('/api/pomax/route-file/load')
async def pomax_route_file_load(body: PomaxRouteFileRequest):
    try:
        result = _read_vp_route_file(name=str(body.name or ''), file_name=str(body.file_name or ''))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    status = get_pomax_status()
    if not status.get('ready'):
        raise HTTPException(409, 'Integrated Virtual Pilot is not ready yet.')
    if body.open_panel is not False:
        _update_browser_state(
            requested_url=status.get('web_url') or 'http://127.0.0.1:3300',
            requested_title='Integrated Virtual Pilot',
            request_id=time.time_ns(),
            visible=True,
            minimal_controls=True,
            panel_kind='vp',
        )
    _update_browser_state(requested_script=_build_pomax_load_script(result['points'], result['name']), script_id=time.time_ns())
    return {'ok': True, **result, 'message': f"Loaded {result['count']} waypoint(s) from {result['file_name']}"}


@app.post('/api/pomax/command')
async def pomax_command(body: PomaxCommandRequest):
    status = get_pomax_status()
    if not status.get('ready'):
        raise HTTPException(409, 'Integrated Virtual Pilot is not ready yet.')
    cmd = str(body.command or '').strip().lower()
    if cmd not in {'pause_on', 'pause_off'}:
        raise HTTPException(400, 'Unsupported Pomax command.')
    _update_browser_state(requested_script=_build_pomax_command_script(cmd), script_id=time.time_ns())
    return {'ok': True, 'command': cmd, 'message': f'Issued {cmd} to the integrated Virtual Pilot.'}


@app.post('/api/pomax/slew-start')
async def pomax_slew_start(body: PomaxSlewRequest):
    status = get_pomax_status()
    if not status.get('ready'):
        raise HTTPException(409, 'Integrated Virtual Pilot is not ready yet.')
    points = _normalize_route_points(body.points)
    if len(points) < 1:
        raise HTTPException(400, 'At least one valid waypoint is required.')
    _update_browser_state(requested_script=_build_pomax_slew_script(points, pause_after=bool(body.pause_after)), script_id=time.time_ns())
    return {'ok': True, 'message': 'Queued slew to route start for the integrated Virtual Pilot.', 'count': len(points)}


@app.get('/api/virtual-pilot/config')
async def virtual_pilot_config():
    return get_virtual_pilot_config()

@app.get("/api/flight/airports")
async def flight_airports(query: str = '', limit: int = 50):
    try:
        from airports import search_airports
        return {"items": search_airports(query=query, limit=limit), "query": query, "limit": max(1, min(int(limit or 50), 200))}
    except Exception as exc:
        return {"items": [], "query": query, "limit": max(1, min(int(limit or 50), 200)), "error": str(exc)}

@app.get("/api/flight/weather")
async def flight_weather(lat: float, lon: float, max_candidates: int = 8):
    try:
        from airports import nearest_airports
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Airport dataset unavailable: {exc}')
    candidates = nearest_airports(lat=lat, lon=lon, limit=max_candidates or 8, require_four_letter_icao=True)
    if not candidates:
        candidates = nearest_airports(lat=lat, lon=lon, limit=max_candidates or 8, require_four_letter_icao=False)
    if not candidates:
        raise HTTPException(status_code=404, detail='No nearby airport candidates were found for weather lookup.')
    last_error = None
    for airport in candidates:
        icao = str(airport.get('icao') or '').strip().upper()
        if not icao:
            continue
        try:
            payload = await asyncio.to_thread(_fetch_aviationweather_metar, icao)
            if not payload:
                continue
            wx = _normalize_aviationweather_payload(payload, icao=icao)
            return {
                'airport': {
                    'icao': icao,
                    'name': airport.get('name') or '',
                    'municipality': airport.get('municipality') or airport.get('city') or '',
                    'distance_nm': round(float(airport.get('distance_nm') or 0.0), 1),
                    'lat': airport.get('lat'),
                    'lon': airport.get('lon'),
                },
                **wx,
            }
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise HTTPException(status_code=502, detail=f'Unable to retrieve nearby METAR data: {last_error}')
    raise HTTPException(status_code=404, detail='No nearby airport with METAR data was found.')

@app.post("/api/flight/settings")
async def flight_settings(request: Request):
    payload = {}
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    raw_interval = payload.get('poll_interval', 1.0)
    try:
        poll_interval = max(0.4, min(5.0, float(raw_interval or 1.0)))
    except Exception:
        poll_interval = 1.0
    _simconnect_endpoint_log('info', 'API /api/flight/settings entered. poll_interval=%.2fs payload=%s', poll_interval, str(payload)[:500])
    await storage.set_json_setting('flight_tracker_settings', {'poll_interval': poll_interval})
    status = _flight_tracker.configure(poll_interval=poll_interval)
    _simconnect_endpoint_log('info', 'API /api/flight/settings returning. state=%s', str(status.get('state') or ''))
    return status

@app.get("/api/app/info")
async def app_info():
    return {
        "user_data_dir": str(USER_DATA_DIR),
        "settings_file": str(SETTINGS_JSON_PATH),
        "db_path": str(DB_PATH),
        "frontend_dir": str(FRONTEND_DIR),
        "shell_mode": os.environ.get('HANGAR_SHELL_MODE', 'browser'),
        "settings_exists": SETTINGS_JSON_PATH.exists(),
        "db_exists": DB_PATH.exists(),
        "settings_file_info": _file_info(SETTINGS_JSON_PATH),
        "db_file_info": _file_info(DB_PATH),
        "window_state": await storage.get_json_setting('window_state', {}),
    }

@app.get("/")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return JSONResponse({"error": "Frontend not found."}, status_code=503)
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"}
    return FileResponse(str(index), headers=headers)
