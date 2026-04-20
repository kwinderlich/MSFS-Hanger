from __future__ import annotations

import copy
import importlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from logger import get_logger
from paths import USER_DATA_DIR
from we_are_flying import path_heading as waf_path_heading, surface_profile as waf_surface_profile, blend_heading as waf_blend_heading

log = get_logger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _default_status() -> dict[str, Any]:
    return {
        'connected': False,
        'available': False,
        'state': 'unavailable',
        'status_message': '',
        'sim_rate': 1,
        'session_state': 'idle',
        'trail': [],
        'stats': {'elapsed_seconds': 0, 'samples': 0, 'max_ground_speed_kt': 0, 'max_altitude_ft': 0},
        'lat': None, 'lon': None, 'altitude_ft': None, 'ground_speed_kt': None,
        'indicated_airspeed_kt': None, 'heading_deg': None, 'track_deg': None, 'vertical_speed_fpm': None,
        'bank_deg': None, 'pitch_deg': None,
        'actual_altitude_ft': None, 'altitude_agl_ft': None, 'ground_elevation_ft': None, 'true_airspeed_kt': None,
        'ap_selected_altitude_ft': None, 'wind_direction_deg': None, 'wind_speed_kt': None,
        'total_air_temp_c': None, 'static_air_temp_c': None, 'sea_level_pressure_hpa': None, 'visibility_sm': None,
        'fuel_total_gal': None, 'fuel_remaining_percent': None, 'fuel_flow_gph': None, 'endurance_hours': None,
        'range_remaining_nm': None, 'flaps_percent': None, 'gear_percent': None, 'throttle_percent_total': None,
        'throttle_percent_engine1': None, 'throttle_percent_engine2': None, 'throttle_percent_engine3': None,
        'throttle_percent_engine4': None, 'nav_lights': False, 'beacon_lights': False, 'strobe_lights': False,
        'landing_lights': False, 'taxi_lights': False, 'on_ground': None, 'aircraft_title': '', 'aircraft_icao': '',
        'sim_time_utc': '', 'sim_time_local': '', 'last_error': '', 'engine_count': None,
        'has_retractable_gear': None, 'pause_state': None,
        'route_controller': {
            'active': False,
            'mode': 'standby',
            'message': '',
            'current_index': 0,
            'waypoint_count': 0,
            'loop': False,
            'speed_kt': None,
            'altitude_ft': None,
            'phase': 'idle',
            'control_mode': 'virtual-direct',
        },
        'controller_target': {
            'heading_deg': None,
            'speed_kt': None,
            'altitude_ft': None,
        },
    }


def _boolify(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        return bool(int(float(value)))
    except Exception:
        s = str(value).strip().lower()
        if s in {'true', 'yes', 'on'}:
            return True
        if s in {'false', 'no', 'off'}:
            return False
    return None


def _floatify(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except Exception:
        return None


def _deg(v: Any) -> float | None:
    n = _floatify(v)
    if n is None:
        return None
    if abs(n) <= math.tau * 1.25:
        n = math.degrees(n)
    return (n + 360.0) % 360.0


def _meters_to_sm(v: Any) -> float | None:
    n = _floatify(v)
    if n is None:
        return None
    # If it already looks like statute miles, leave it alone.
    if n <= 100:
        return n
    return n / 1609.344


def _seconds_to_hms(v: Any) -> str:
    n = _floatify(v)
    if n is None:
        return ''
    total = int(max(0, n)) % 86400
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f'{h:02d}:{m:02d}:{s:02d}'


def _wrap_heading(value: Any) -> float | None:
    n = _floatify(value)
    if n is None:
        return None
    return (n + 360.0) % 360.0


def _heading_error_deg(current: Any, target: Any) -> float:
    cur = _wrap_heading(current)
    tgt = _wrap_heading(target)
    if cur is None or tgt is None:
        return 0.0
    return ((float(tgt) - float(cur) + 540.0) % 360.0) - 180.0


def _blend_heading(current: Any, target: Any, *, max_step_deg: float = 8.0, blend: float = 0.45) -> float | None:
    cur = _wrap_heading(current)
    tgt = _wrap_heading(target)
    if tgt is None:
        return cur
    if cur is None:
        return tgt
    err = _heading_error_deg(cur, tgt)
    step = max(-abs(max_step_deg), min(abs(max_step_deg), err * max(0.0, min(1.0, blend))))
    return _wrap_heading(float(cur) + step)


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_nm = 3440.065
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r_nm * math.asin(min(1.0, math.sqrt(max(0.0, a))))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_control_mode(value: Any) -> str:
    mode = str(value or '').strip().lower().replace('_', '-').replace(' ', '-')
    if mode in {'ap', 'ap-guidance', 'autopilot', 'route-ap'}:
        return 'ap-guidance'
    if mode in {'virtual-surface', 'surface', 'surface-direct', 'control-surface', 'pid', 'virtual-pid', 'pid-test'}:
        return 'virtual-surface'
    if mode in {'pomax', 'waf', 'we-are-flying', 'we-are-flying-test', 'pomax-law', 'path-policy'}:
        return 'pomax-law'
    if mode in {'virtual', 'virtual-direct', 'direct', 'flight-path', 'path'}:
        return 'virtual-direct'
    return 'virtual-surface'


def _destination_point(lat: float, lon: float, bearing_deg: float, distance_nm: float) -> tuple[float, float]:
    if distance_nm <= 0:
        return lat, lon
    r_nm = 3440.065
    ang = distance_nm / r_nm
    br = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(ang) + math.cos(p1) * math.sin(ang) * math.cos(br))
    l2 = l1 + math.atan2(math.sin(br) * math.sin(ang) * math.cos(p1), math.cos(ang) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), ((math.degrees(l2) + 540.0) % 360.0) - 180.0


def _project_on_leg(lat: float, lon: float, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict[str, float]:
    ref_lat = math.radians((start_lat + end_lat + lat) / 3.0)
    lon_scale = max(1e-6, math.cos(ref_lat) * 60.0)
    ax = 0.0
    ay = 0.0
    bx = (end_lon - start_lon) * lon_scale
    by = (end_lat - start_lat) * 60.0
    px = (lon - start_lon) * lon_scale
    py = (lat - start_lat) * 60.0
    leg_dx = bx - ax
    leg_dy = by - ay
    leg_len_sq = leg_dx * leg_dx + leg_dy * leg_dy
    if leg_len_sq <= 1e-9:
        return {'t': 1.0, 'raw_t': 1.0, 'along_nm': 0.0, 'cross_nm': 0.0, 'leg_nm': 0.0, 'proj_lat': start_lat, 'proj_lon': start_lon}
    raw_t = ((px - ax) * leg_dx + (py - ay) * leg_dy) / leg_len_sq
    t = max(0.0, min(1.0, raw_t))
    proj_x = ax + leg_dx * t
    proj_y = ay + leg_dy * t
    cross = math.hypot(px - proj_x, py - proj_y)
    leg_nm = math.sqrt(leg_len_sq)
    along_nm = leg_nm * t
    proj_lat = start_lat + (proj_y / 60.0)
    proj_lon = start_lon + (proj_x / lon_scale)
    return {'t': t, 'raw_t': raw_t, 'along_nm': along_nm, 'cross_nm': cross, 'leg_nm': leg_nm, 'proj_lat': proj_lat, 'proj_lon': proj_lon}


def _signed_cross_track_nm(lat: float, lon: float, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> float:
    ref_lat = math.radians((start_lat + end_lat + lat) / 3.0)
    lon_scale = max(1e-6, math.cos(ref_lat) * 60.0)
    sx = 0.0
    sy = 0.0
    ex = (end_lon - start_lon) * lon_scale
    ey = (end_lat - start_lat) * 60.0
    px = (lon - start_lon) * lon_scale
    py = (lat - start_lat) * 60.0
    vx = ex - sx
    vy = ey - sy
    wx = px - sx
    wy = py - sy
    leg_len = math.hypot(vx, vy)
    if leg_len <= 1e-9:
        return 0.0
    cross = (vx * wy) - (vy * wx)
    return cross / leg_len


def _target_on_leg(lat: float, lon: float, start_lat: float, start_lon: float, end_lat: float, end_lon: float, *, lookahead_nm: float, on_path_nm: float) -> dict[str, float]:
    proj = _project_on_leg(lat, lon, start_lat, start_lon, end_lat, end_lon)
    leg_nm = max(0.0, float(proj.get('leg_nm') or 0.0))
    if leg_nm <= 1e-6:
        heading = _bearing_deg(lat, lon, end_lat, end_lon)
        return {'lat': end_lat, 'lon': end_lon, 'heading_deg': heading, 'remaining_nm': _haversine_nm(lat, lon, end_lat, end_lon), 'along_nm': 0.0, 'cross_nm': 0.0, 'leg_nm': 0.0}
    effective_lookahead = max(0.03, lookahead_nm)
    if float(proj.get('cross_nm') or 0.0) > max(0.08, on_path_nm * 2.2):
        anchor_lat = float(proj.get('proj_lat') or start_lat)
        anchor_lon = float(proj.get('proj_lon') or start_lon)
    else:
        anchor_lat = lat
        anchor_lon = lon
    along_now = float(proj.get('along_nm') or 0.0)
    target_along = min(leg_nm, along_now + effective_lookahead)
    frac = 1.0 if leg_nm <= 1e-6 else max(0.0, min(1.0, target_along / leg_nm))
    target_lat = _lerp(start_lat, end_lat, frac)
    target_lon = _lerp(start_lon, end_lon, frac)
    heading = _bearing_deg(anchor_lat, anchor_lon, target_lat, target_lon)
    return {'lat': target_lat, 'lon': target_lon, 'heading_deg': heading, 'remaining_nm': max(0.0, leg_nm - along_now), 'along_nm': along_now, 'cross_nm': float(proj.get('cross_nm') or 0.0), 'leg_nm': leg_nm}


def _policy_heading_for_leg(leg_heading: float, signed_cross_nm: float, *, lookahead_nm: float, profile: str = 'pid') -> float:
    lookahead = max(0.04, float(lookahead_nm or 0.04))
    gain = 1.25 if profile == 'pid' else 0.82
    correction = math.degrees(math.atan2(float(signed_cross_nm) * gain, lookahead))
    correction = _clamp(correction, -28.0 if profile == 'pid' else -18.0, 28.0 if profile == 'pid' else 18.0)
    return float(_wrap_heading(float(leg_heading) - correction) or leg_heading)


class FlightTracker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._poll_interval = 1.0
        self._status = _default_status()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._sm = None
        self._aq = None
        self._ae = None
        self._event_cls = None
        self._sim_module = None
        self._connected_at: float | None = None
        self._failed_vars: set[str] = set()
        self._logs_path = USER_DATA_DIR / 'flight_logs.json'
        self._route_stop = threading.Event()
        self._route_worker: threading.Thread | None = None
        self._route_plan: list[dict[str, float]] = []
        self._sim_io_lock = threading.RLock()
        self._last_controller_log_at = 0.0
        self._last_io_error_log_at = 0.0
        self._sim_command_seq = 0
        self._spawn_guard: dict[str, Any] | None = None
        self._route_generation = 0

    def _load_simconnect(self) -> bool:
        if self._sim_module is not None:
            return True
        for mod_name in ('SimConnect', 'simconnect'):
            try:
                mod = importlib.import_module(mod_name)
                self._sim_module = mod
                self._event_cls = getattr(mod, 'Event', None)
                return True
            except Exception:
                continue
        return False

    def configure(self, poll_interval: float | None = None) -> dict[str, Any]:
        with self._lock:
            if poll_interval is not None:
                try:
                    self._poll_interval = max(0.4, min(5.0, float(poll_interval)))
                except Exception:
                    self._poll_interval = 1.0
            self._status['available'] = self._load_simconnect()
            if not self._status['connected']:
                self._status['state'] = 'ready' if self._status['available'] else 'unavailable'
            self._status['config'] = {'poll_interval': self._poll_interval}
            if self._status['available'] and not self._status.get('status_message'):
                self._status['status_message'] = 'SimConnect package detected.'
            elif not self._status['available']:
                self._status['status_message'] = 'SimConnect package not available in this Python environment.'
            return copy.deepcopy(self._status)

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._connected_at:
                self._status['stats']['elapsed_seconds'] = max(0, int(time.time() - self._connected_at))
            self._status['config'] = {'poll_interval': self._poll_interval}
            return copy.deepcopy(self._status)

    def connect(self) -> dict[str, Any]:
        with self._lock:
            self.configure(self._poll_interval)
            if self._status['connected']:
                return copy.deepcopy(self._status)
            if not self._status['available']:
                self._status['last_error'] = 'SimConnect package not available.'
                self._status['state'] = 'failed'
                return copy.deepcopy(self._status)
            try:
                SimConnectClass = getattr(self._sim_module, 'SimConnect')
                AircraftRequests = getattr(self._sim_module, 'AircraftRequests')
                AircraftEvents = getattr(self._sim_module, 'AircraftEvents', None)
                self._sm = SimConnectClass()
                self._aq = AircraftRequests(self._sm, _time=max(0, int(self._poll_interval * 1000)))
                self._ae = AircraftEvents(self._sm) if AircraftEvents else None
                self._failed_vars.clear()
                self._stop.clear()
                self._connected_at = time.time()
                self._status.update({'connected': True, 'state': 'connected', 'status_message': 'Connected to SimConnect.', 'last_error': ''})
                self._worker = threading.Thread(target=self._poll_loop, name='msfs-flight-tracker', daemon=True)
                self._worker.start()
            except Exception as exc:
                self._status.update({'connected': False, 'state': 'failed', 'last_error': str(exc), 'status_message': 'Could not connect to SimConnect.'})
                log.warning('Flight tracker connect failed: %s', exc, exc_info=True)
                self._cleanup_locked()
            return copy.deepcopy(self._status)

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            self._stop.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=2.5)
        with self._lock:
            self._append_log_entry_locked()
            self._cleanup_locked()
            self._status.update({'connected': False, 'state': 'ready' if self._load_simconnect() else 'unavailable', 'status_message': 'Disconnected from SimConnect.'})
            return copy.deepcopy(self._status)

    def command(self, cmd: str) -> dict[str, Any]:
        cmd = str(cmd or '').strip().lower()
        with self._lock:
            if not self._status['connected']:
                return {'ok': False, 'message': 'Flight tracker is not connected.', 'status': self.status()}
            try:
                result = self._execute_command_locked(cmd)
                return {'ok': bool(result), 'message': 'Command sent.' if result else f'Unsupported or unavailable command: {cmd}', 'status': self.status()}
            except Exception as exc:
                log.warning('Flight command failed: %s', exc, exc_info=True)
                self._status['last_error'] = str(exc)
                return {'ok': False, 'message': str(exc), 'status': self.status()}

    def _set_pause_locked(self, paused: bool) -> bool:
        desired = bool(paused)
        actual_paused = _boolify(self._safe_get('IS_PAUSED'))
        current_paused = bool(actual_paused) if actual_paused is not None else (str(self._status.get('pause_state') or '').lower() == 'paused')
        if current_paused == desired:
            self._status['pause_state'] = 'paused' if desired else 'running'
            return True
        attempts = [('PAUSE_ON', None), ('PAUSE_SET', 1)] if desired else [('PAUSE_OFF', None), ('PAUSE_SET', 0)]
        ok = False
        for event_name, value in attempts:
            try:
                ok = self._invoke_event(event_name, value) if value is not None else self._invoke_event(event_name)
            except Exception:
                ok = False
            if not ok:
                continue
            time.sleep(0.14)
            try:
                paused_flag = _boolify(self._safe_get('IS_PAUSED'))
            except Exception:
                paused_flag = None
            if paused_flag is None or bool(paused_flag) == desired:
                ok = True
                break
            ok = False
        if ok:
            self._status['pause_state'] = 'paused' if desired else 'running'
            self._status['session_state'] = 'paused' if desired else (self._status.get('session_state') or 'cruise')
            return True
        return False

    def _log_io_error_locked(self, action: str, exc: Exception) -> None:
        now = time.time()
        if (now - float(self._last_io_error_log_at or 0.0)) >= 1.0:
            self._last_io_error_log_at = now
            log.warning('SimConnect IO error during %s: %s', action, exc)

    def _log_controller_tick_locked(self, label: str, **fields: Any) -> None:
        now = time.time()
        if (now - float(self._last_controller_log_at or 0.0)) < 0.45:
            return
        self._last_controller_log_at = now
        ordered = []
        for key in ['mode','leg','lat','lon','hdg','track','target_hdg','alt','target_alt','speed','target_speed','cross_nm','bank_cmd','aileron','elevator','throttle','step_nm']:
            if key in fields and fields[key] is not None:
                ordered.append(f"{key}={fields[key]}")
        extras = [f"{k}={v}" for k,v in fields.items() if k not in {'mode','leg','lat','lon','hdg','track','target_hdg','alt','target_alt','speed','target_speed','cross_nm','bank_cmd','aileron','elevator','throttle','step_nm'} and v is not None]
        msg = ' | '.join(ordered + extras)
        log.info('%s | %s', label, msg)

    def _apply_virtual_path_guidance_locked(self, *, current_lat: float, current_lon: float, current_heading_deg: float | None, current_altitude_ft: float | None, current_speed_kt: float | None = None, current_bank_deg: float | None = None, current_pitch_deg: float | None = None, current_vs_fpm: float | None = None, current_throttle_pct: float | None = None, target_heading_deg: float, target_altitude_ft: float | None, target_speed_kt: float | None, interval_s: float, cross_track_nm: float = 0.0, profile: str = 'pomax') -> bool:
        """Apply a virtual-pilot style control law without rewriting aircraft position every tick.

        The only direct repositioning should happen once when the route starts (or on an
        explicit waypoint jump). After that we only command surfaces/throttle so the sim
        physics remains in charge of the aircraft motion.
        """
        prof = 'pomax' if str(profile or '').lower().startswith('pomax') else 'pid'
        ok = self._apply_surface_guidance_locked(
            target_heading_deg=target_heading_deg,
            target_altitude_ft=target_altitude_ft,
            target_speed_kt=target_speed_kt,
            cross_track_nm=cross_track_nm,
            profile=prof,
            track_now=current_heading_deg,
            heading_now=current_heading_deg,
            altitude_now=current_altitude_ft,
            airspeed_now=current_speed_kt,
            bank_now=current_bank_deg,
            pitch_now=current_pitch_deg,
            vs_now=current_vs_fpm,
            throttle_pct=current_throttle_pct,
        )
        self._log_controller_tick_locked(
            'virtual-pilot',
            mode=prof,
            lat=f'{current_lat:.5f}',
            lon=f'{current_lon:.5f}',
            hdg=(f'{float(_floatify(current_heading_deg) or 0.0):.1f}' if current_heading_deg is not None else None),
            target_hdg=f'{float(_wrap_heading(target_heading_deg) or 0.0):.1f}',
            alt=(f'{float(_floatify(current_altitude_ft) or 0.0):.0f}' if current_altitude_ft is not None else None),
            target_alt=(f'{float(target_altitude_ft):.0f}' if target_altitude_ft is not None else None),
            speed=(f'{float(_floatify(current_speed_kt) or 0.0):.0f}' if current_speed_kt is not None else None),
            target_speed=(f'{float(target_speed_kt or 0.0):.0f}' if target_speed_kt is not None else None),
            cross_nm=f'{float(cross_track_nm):.3f}',
            ok=ok,
        )
        return ok


    def _route_command_logging_enabled_locked(self) -> bool:
        controller = self._status.get('route_controller') or {}
        return bool(controller.get('active'))

    def _log_sim_command_locked(self, *, kind: str, name: str, value: Any | None = None, ok: bool, extra: str = '') -> None:
        if not self._route_command_logging_enabled_locked():
            return
        self._sim_command_seq += 1
        controller = self._status.get('route_controller') or {}
        mode = controller.get('mode') or controller.get('control_mode') or 'standby'
        phase = controller.get('phase') or 'idle'
        idx = controller.get('current_index') or 0
        cnt = controller.get('waypoint_count') or 0
        payload = ''
        if value is not None:
            payload = f' value={value!r}'
        suffix = f' {extra}' if extra else ''
        log.info('simcmd #%s | mode=%s | phase=%s | leg=%s/%s | %s %s%s | ok=%s%s',
                 self._sim_command_seq, mode, phase, idx, cnt, kind, name, payload, ok, suffix)

    def _execute_command_locked(self, cmd: str) -> bool:
        if cmd == 'sim_rate_reset':
            if self._safe_set('SIMULATION_RATE', 1):
                self._status['sim_rate'] = 1
                return True
            return self._invoke_event('SIM_RATE_SET', 1)
        if cmd == 'pause_on':
            return self._set_pause_locked(True)
        if cmd == 'pause_off':
            return self._set_pause_locked(False)
        if cmd == 'pause_toggle':
            return self._set_pause_locked(str(self._status.get('pause_state') or '').lower() != 'paused')
        mapping = {
            'sim_rate_increase': 'SIM_RATE_INCR',
            'sim_rate_decrease': 'SIM_RATE_DECR',
            'ap_master_toggle': 'AP_MASTER',
            'heading_hold': 'AP_HDG_HOLD',
            'altitude_hold': 'AP_ALT_HOLD',
            'nav_hold': 'AP_NAV1_HOLD',
            'approach_hold': 'AP_APR_HOLD',
        }
        event_name = mapping.get(cmd)
        if not event_name:
            return False
        return self._invoke_event(event_name)

    def _invoke_event(self, event_name: str, value: Any | None = None) -> bool:
        with self._sim_io_lock:
            if self._ae is not None:
                try:
                    event = self._ae.find(event_name)
                    if value is None:
                        event()
                    else:
                        event(value)
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=True, extra='via=AircraftEvents')
                    return True
                except OSError as exc:
                    self._log_io_error_locked(f'event {event_name}', exc)
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=False, extra=f'via=AircraftEvents err={exc}')
                except Exception as exc:
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=False, extra=f'via=AircraftEvents err={exc}')
                    pass
            if self._event_cls is not None and self._sm is not None:
                try:
                    event = self._event_cls(event_name.encode('utf-8'), self._sm)
                    if value is None:
                        event()
                    else:
                        event(value)
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=True, extra='via=EventClass')
                    return True
                except OSError as exc:
                    self._log_io_error_locked(f'event {event_name}', exc)
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=False, extra=f'via=EventClass err={exc}')
                except Exception as exc:
                    self._log_sim_command_locked(kind='event', name=event_name, value=value, ok=False, extra=f'via=EventClass err={exc}')
                    pass
        return False

    def _safe_get(self, *names: str) -> Any:
        if self._aq is None:
            return None
        for name in names:
            if not name or name in self._failed_vars:
                continue
            try:
                with self._sim_io_lock:
                    return self._aq.get(name)
            except OSError as exc:
                # Transient SimConnect COM failures should not permanently blacklist
                # a variable for the rest of the session.
                self._status['last_error'] = str(exc)
                self._log_io_error_locked(f'get {name}', exc)
                return None
            except Exception as exc:
                msg = str(exc).lower()
                # Only blacklist obviously-invalid simvar names. Anything else may be transient.
                if any(tok in msg for tok in ('unknown', 'invalid', 'not found', 'does not exist')):
                    self._failed_vars.add(name)
                self._status['last_error'] = str(exc)
        return None

    def _safe_set(self, name: str, value: Any) -> bool:
        if self._aq is None:
            return False
        try:
            with self._sim_io_lock:
                self._aq.set(name, value)
            self._log_sim_command_locked(kind='set', name=name, value=value, ok=True)
            return True
        except OSError as exc:
            self._status['last_error'] = str(exc)
            self._log_io_error_locked(f'set {name}', exc)
            self._log_sim_command_locked(kind='set', name=name, value=value, ok=False, extra=f'err={exc}')
            return False
        except Exception as exc:
            self._log_sim_command_locked(kind='set', name=name, value=value, ok=False, extra=f'err={exc}')
            return False

    def _safe_set_any(self, names: list[str], value: Any) -> bool:
        for name in names:
            if self._safe_set(name, value):
                return True
        return False

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            started = time.time()
            try:
                snapshot = self._sample_once()
                with self._lock:
                    self._status.update(snapshot)
                    self._status['connected'] = True
                    self._status['available'] = self._load_simconnect()
                    self._status['state'] = 'connected'
                    self._status['status_message'] = 'Connected to SimConnect.'
                    self._status['last_error'] = ''
            except Exception as exc:
                with self._lock:
                    self._status['last_error'] = str(exc)
                    self._status['status_message'] = 'Telemetry polling failed.'
                log.warning('Flight tracker polling error: %s', exc, exc_info=True)
            elapsed = time.time() - started
            delay = max(0.05, self._poll_interval - elapsed)
            self._stop.wait(delay)

    def _sample_once(self) -> dict[str, Any]:
        lat = _floatify(self._safe_get('PLANE_LATITUDE', 'GPS_POSITION_LAT'))
        lon = _floatify(self._safe_get('PLANE_LONGITUDE', 'GPS_POSITION_LON'))
        indicated_alt = _floatify(self._safe_get('INDICATED_ALTITUDE', 'PLANE_ALTITUDE'))
        actual_alt = _floatify(self._safe_get('PLANE_ALTITUDE', 'INDICATED_ALTITUDE'))
        agl = _floatify(self._safe_get('PLANE_ALT_ABOVE_GROUND'))
        ground_alt = _floatify(self._safe_get('GROUND_ALTITUDE'))
        gs = _floatify(self._safe_get('GROUND_VELOCITY'))
        ias = _floatify(self._safe_get('AIRSPEED_INDICATED'))
        tas = _floatify(self._safe_get('AIRSPEED_TRUE'))
        heading = _deg(self._safe_get('PLANE_HEADING_DEGREES_MAGNETIC', 'PLANE_HEADING_DEGREES_TRUE'))
        track = _deg(self._safe_get('GPS_GROUND_TRUE_TRACK', 'GPS_GROUND_MAGNETIC_TRACK'))
        vs = _floatify(self._safe_get('VERTICAL_SPEED'))
        bank = _deg(self._safe_get('PLANE_BANK_DEGREES'))
        pitch_raw = _floatify(self._safe_get('PLANE_PITCH_DEGREES'))
        pitch = math.degrees(pitch_raw) if pitch_raw is not None and abs(pitch_raw) <= math.tau * 1.25 else pitch_raw
        ap_alt = _floatify(self._safe_get('AUTOPILOT_ALTITUDE_LOCK_VAR'))
        wind_dir = _deg(self._safe_get('AMBIENT_WIND_DIRECTION'))
        wind_speed = _floatify(self._safe_get('AMBIENT_WIND_VELOCITY'))
        oat = _floatify(self._safe_get('TOTAL_AIR_TEMPERATURE'))
        sat = _floatify(self._safe_get('AMBIENT_TEMPERATURE'))
        slp = _floatify(self._safe_get('SEA_LEVEL_PRESSURE'))
        vis = _meters_to_sm(self._safe_get('AMBIENT_VISIBILITY'))
        fuel_total = _floatify(self._safe_get('FUEL_TOTAL_QUANTITY'))
        fuel_pct = _floatify(self._safe_get('FUEL_TOTAL_QUANTITY_PERCENT'))
        fuel_flow = _floatify(self._safe_get('ESTIMATED_FUEL_FLOW', 'ENG_FUEL_FLOW_GPH:1'))
        flaps = _floatify(self._safe_get('FLAPS_HANDLE_PERCENT'))
        gear = _floatify(self._safe_get('GEAR_CENTER_POSITION'))
        on_ground = _boolify(self._safe_get('SIM_ON_GROUND'))
        title = self._safe_get('TITLE') or ''
        icao = self._safe_get('ATC_MODEL', 'ATC_TYPE') or ''
        sim_rate = _floatify(self._safe_get('SIMULATION_RATE')) or 1
        engine_count = int(_floatify(self._safe_get('NUMBER_OF_ENGINES')) or 0) or None
        retractable = _boolify(self._safe_get('IS_GEAR_RETRACTABLE'))
        paused = _boolify(self._safe_get('IS_PAUSED'))
        if paused is None:
            paused = str((self._status.get('pause_state') or '')).lower() == 'paused'
        throttle_values = []
        for idx in range(1, 5):
            throttle_values.append(_floatify(self._safe_get(f'GENERAL_ENG_THROTTLE_LEVER_POSITION:{idx}')))
        throttle_clean = [v for v in throttle_values if v is not None]
        total_throttle = (sum(throttle_clean) / len(throttle_clean)) if throttle_clean else None
        endurance = (fuel_total / fuel_flow) if (fuel_total not in (None, 0) and fuel_flow not in (None, 0)) else None
        speed_for_range = tas or gs or ias
        range_nm = (speed_for_range * endurance) if (speed_for_range not in (None, 0) and endurance not in (None, 0)) else None

        now = _utc_now()
        trail = copy.deepcopy(self._status.get('trail') or [])
        if lat is not None and lon is not None:
            trail.append({'lat': lat, 'lon': lon, 'ts': now})
        trail = trail[-360:]

        stats = copy.deepcopy(self._status.get('stats') or {'elapsed_seconds': 0, 'samples': 0, 'max_ground_speed_kt': 0, 'max_altitude_ft': 0})
        stats['samples'] = int(stats.get('samples') or 0) + 1
        stats['elapsed_seconds'] = max(0, int(time.time() - (self._connected_at or time.time())))
        stats['max_ground_speed_kt'] = max(float(stats.get('max_ground_speed_kt') or 0), float(gs or 0))
        stats['max_altitude_ft'] = max(float(stats.get('max_altitude_ft') or 0), float(actual_alt or indicated_alt or 0))

        if paused:
            session_state = 'paused'
        elif on_ground is True and (gs or 0) < 5:
            session_state = 'parked'
        elif on_ground is True:
            session_state = 'ground'
        elif (vs or 0) > 700:
            session_state = 'climb'
        elif (vs or 0) < -700:
            session_state = 'descent'
        else:
            session_state = 'cruise'

        return {
            'lat': lat, 'lon': lon, 'altitude_ft': indicated_alt, 'actual_altitude_ft': actual_alt,
            'altitude_agl_ft': agl, 'ground_elevation_ft': ground_alt, 'ground_speed_kt': gs,
            'indicated_airspeed_kt': ias, 'true_airspeed_kt': tas, 'heading_deg': heading, 'track_deg': track,
            'vertical_speed_fpm': vs, 'bank_deg': bank, 'pitch_deg': pitch, 'ap_selected_altitude_ft': ap_alt, 'wind_direction_deg': wind_dir,
            'wind_speed_kt': wind_speed, 'total_air_temp_c': oat, 'static_air_temp_c': sat,
            'sea_level_pressure_hpa': slp, 'visibility_sm': vis, 'fuel_total_gal': fuel_total,
            'fuel_remaining_percent': fuel_pct, 'fuel_flow_gph': fuel_flow, 'endurance_hours': endurance,
            'range_remaining_nm': range_nm, 'flaps_percent': flaps, 'gear_percent': gear,
            'throttle_percent_total': total_throttle,
            'throttle_percent_engine1': throttle_values[0], 'throttle_percent_engine2': throttle_values[1],
            'throttle_percent_engine3': throttle_values[2], 'throttle_percent_engine4': throttle_values[3],
            'nav_lights': bool(_boolify(self._safe_get('LIGHT_NAV'))), 'beacon_lights': bool(_boolify(self._safe_get('LIGHT_BEACON'))),
            'strobe_lights': bool(_boolify(self._safe_get('LIGHT_STROBE'))), 'landing_lights': bool(_boolify(self._safe_get('LIGHT_LANDING'))),
            'taxi_lights': bool(_boolify(self._safe_get('LIGHT_TAXI'))), 'on_ground': on_ground,
            'aircraft_title': str(title), 'aircraft_icao': str(icao), 'sim_time_utc': _seconds_to_hms(self._safe_get('ZULU_TIME')),
            'sim_time_local': _seconds_to_hms(self._safe_get('LOCAL_TIME')), 'sim_rate': round(float(sim_rate or 1), 2),
            'engine_count': engine_count, 'has_retractable_gear': retractable, 'pause_state': 'paused' if paused else 'running',
            'session_state': session_state, 'trail': trail, 'stats': stats,
        }

    def reposition(self, lat: float, lon: float, altitude_ft: float | None = None, heading_deg: float | None = None, speed_kt: float | None = None) -> dict[str, Any]:
        with self._lock:
            if not self._status['connected']:
                return {'ok': False, 'message': 'Flight tracker is not connected.', 'status': self.status()}
            ok = self._apply_reposition_locked(lat=lat, lon=lon, altitude_ft=altitude_ft, heading_deg=heading_deg, speed_kt=speed_kt)
            return {'ok': ok, 'message': 'Aircraft repositioned.' if ok else 'Could not reposition aircraft through SimConnect.', 'status': self.status()}

    def start_route_controller(self, points: list[dict[str, Any]], altitude_ft: float | None = None, speed_kt: float | None = None, heading_deg: float | None = None, loop: bool = False, control_mode: str = 'virtual-direct') -> dict[str, Any]:
        cleaned: list[dict[str, float]] = []
        for item in points or []:
            lat = _floatify((item or {}).get('lat'))
            lon = _floatify((item or {}).get('lon'))
            if lat is None or lon is None:
                continue
            cleaned.append({'lat': lat, 'lon': lon})
        with self._lock:
            if not self._status['connected']:
                return {'ok': False, 'message': 'Flight tracker is not connected.', 'status': self.status()}
            if len(cleaned) < 2:
                return {'ok': False, 'message': 'At least two route points are required.', 'status': self.status()}
            self.stop_route_controller(wait=False)
            self._neutralize_control_surfaces_locked()
            self._route_plan = cleaned
            start = cleaned[0]
            nxt = cleaned[1]
            auto_heading = _bearing_deg(start['lat'], start['lon'], nxt['lat'], nxt['lon'])
            altitude_value = _floatify(altitude_ft)
            speed_value = _floatify(speed_kt) or 140.0
            target_heading = auto_heading if heading_deg is None else _wrap_heading(heading_deg)
            mode = _normalize_control_mode(control_mode)
            self._apply_reposition_locked(lat=start['lat'], lon=start['lon'], altitude_ft=altitude_value, heading_deg=target_heading, speed_kt=None, bank_deg=0.0, pitch_deg=0.0)
            self._spawn_guard = {
                'until': time.time() + 1.2,
                'lat': start['lat'],
                'lon': start['lon'],
                'altitude_ft': altitude_value,
                'heading_deg': target_heading,
            }
            if mode == 'ap-guidance':
                self._apply_ap_guidance_locked(heading_deg=target_heading, altitude_ft=altitude_value, speed_kt=speed_value)
                message = 'Moved to the first route point and started smooth AP guidance toward the next leg.'
                route_mode = 'route-ap'
            elif mode == 'pomax-law':
                message = 'Moved to the first route point and started the We are-Flying test controller.'
                route_mode = 'pomax-law'
            elif mode == 'virtual-surface':
                message = 'Moved to the first route point and started the PID Test controller.'
                route_mode = 'virtual-surface'
            else:
                message = 'Moved to the first route point and started the virtual direct-flight controller.'
                route_mode = 'virtual-direct'
            controller = copy.deepcopy(self._status.get('route_controller') or {})
            self._route_generation += 1
            controller.update({'active': True, 'mode': route_mode, 'phase': 'settle', 'message': message, 'current_index': 1, 'waypoint_count': len(cleaned), 'loop': bool(loop), 'speed_kt': speed_value, 'altitude_ft': altitude_value, 'control_mode': mode, 'generation': self._route_generation})
            self._status['route_controller'] = controller
            target = copy.deepcopy(self._status.get('controller_target') or {})
            target['heading_deg'] = target_heading
            target['speed_kt'] = speed_value
            if altitude_value is not None:
                target['altitude_ft'] = altitude_value
            self._status['controller_target'] = target
            self._route_stop.clear()
            self._route_worker = threading.Thread(target=self._route_loop, args=(self._route_generation,), name='msfs-route-controller', daemon=True)
            self._route_worker.start()
            self._log_sim_command_locked(kind='controller', name='route-start', value={'mode': mode, 'speed_kt': speed_value, 'altitude_ft': altitude_value, 'heading_deg': target_heading}, ok=True, extra=f'points={len(cleaned)}')
            return {'ok': True, 'message': message, 'status': self.status()}

    def jump_to_route_waypoint(self, waypoint_index: int) -> dict[str, Any]:
        with self._lock:
            if not self._status['connected']:
                return {'ok': False, 'message': 'Flight tracker is not connected.', 'status': self.status()}
            plan = list(self._route_plan)
            if len(plan) < 2:
                return {'ok': False, 'message': 'No active route plan is loaded.', 'status': self.status()}
            try:
                point_index = max(0, min(int(waypoint_index), len(plan) - 1))
            except Exception:
                return {'ok': False, 'message': 'Invalid waypoint index.', 'status': self.status()}
            point = plan[point_index]
            controller = copy.deepcopy(self._status.get('route_controller') or {})
            next_index = point_index + 1 if point_index + 1 < len(plan) else (1 if (bool(controller.get('loop')) and len(plan) > 1) else point_index)
            ref = plan[next_index] if next_index != point_index else (plan[max(0, point_index - 1)] if point_index > 0 else point)
            heading = _bearing_deg(point['lat'], point['lon'], ref['lat'], ref['lon']) if ref is not point else _floatify((self._status.get('controller_target') or {}).get('heading_deg'))
            altitude_value = _floatify(controller.get('altitude_ft')) or _floatify(self._status.get('altitude_ft'))
            self._neutralize_control_surfaces_locked()
            ok = self._apply_reposition_locked(lat=point['lat'], lon=point['lon'], altitude_ft=altitude_value, heading_deg=heading, speed_kt=None, bank_deg=0.0, pitch_deg=0.0)
            self._spawn_guard = {
                'until': time.time() + 1.2,
                'lat': point['lat'],
                'lon': point['lon'],
                'altitude_ft': altitude_value,
                'heading_deg': heading,
            }
            mode = _normalize_control_mode(controller.get('control_mode'))
            next_label = int(next_index + 1) if 0 <= next_index < len(plan) else len(plan)
            if mode == 'ap-guidance':
                self._apply_ap_guidance_locked(heading_deg=heading, altitude_ft=altitude_value, speed_kt=_floatify(controller.get('speed_kt')))
            route_mode = 'route-ap' if mode == 'ap-guidance' else ('pomax-law' if mode == 'pomax-law' else ('virtual-surface' if mode == 'virtual-surface' else 'virtual-direct'))
            controller.update({'active': True, 'mode': route_mode, 'phase': 'settle', 'current_index': max(1, next_index), 'waypoint_count': len(plan), 'control_mode': mode, 'message': f'Jumped to waypoint {point_index + 1}. The next active target is waypoint {next_label}.'})
            self._status['route_controller'] = controller
            return {'ok': ok, 'message': controller['message'], 'status': self.status()}

    def stop_route_controller(self, wait: bool = True) -> dict[str, Any]:
        self._route_generation += 1
        self._route_stop.set()
        worker = self._route_worker
        if wait and worker and worker.is_alive():
            worker.join(timeout=2.0)
        with self._lock:
            self._neutralize_control_surfaces_locked()
            controller = copy.deepcopy(self._status.get('route_controller') or {})
            controller.update({'active': False, 'mode': 'standby', 'phase': 'idle', 'message': 'Route controller stopped.'})
            self._status['route_controller'] = controller
            self._spawn_guard = None
            self._log_sim_command_locked(kind='controller', name='route-stop', value=None, ok=True)
            self._route_worker = None
            self._route_plan = []
            return {'ok': True, 'message': 'Route controller stopped.', 'status': self.status()}

    def _apply_reposition_locked(self, *, lat: float, lon: float, altitude_ft: float | None = None, heading_deg: float | None = None, speed_kt: float | None = None, bank_deg: float | None = None, pitch_deg: float | None = None) -> bool:
        ok = False
        ok = self._safe_set_any(['PLANE_LATITUDE', 'PLANE LATITUDE'], float(lat)) or ok
        ok = self._safe_set_any(['PLANE_LONGITUDE', 'PLANE LONGITUDE'], float(lon)) or ok
        if altitude_ft is not None:
            ok = self._safe_set_any(['PLANE_ALTITUDE', 'PLANE ALTITUDE', 'INDICATED_ALTITUDE'], float(altitude_ft)) or ok
        if heading_deg is not None:
            hdg = float(_wrap_heading(heading_deg) or 0.0)
            ok = self._safe_set_any(['PLANE_HEADING_DEGREES_TRUE', 'PLANE HEADING DEGREES TRUE'], hdg) or ok
        if pitch_deg is not None:
            self._safe_set_any(['PLANE_PITCH_DEGREES', 'PLANE PITCH DEGREES'], float(pitch_deg))
        if bank_deg is not None:
            self._safe_set_any(['PLANE_BANK_DEGREES', 'PLANE BANK DEGREES'], float(bank_deg))
        if speed_kt is not None:
            ok = self._safe_set_any(['AIRSPEED_TRUE', 'AIRSPEED INDICATED'], float(speed_kt)) or ok
        if ok:
            self._status['lat'] = float(lat)
            self._status['lon'] = float(lon)
            if altitude_ft is not None:
                self._status['altitude_ft'] = float(altitude_ft)
                self._status['actual_altitude_ft'] = float(altitude_ft)
            if heading_deg is not None:
                self._status['heading_deg'] = float(_wrap_heading(heading_deg) or 0.0)
                self._status['track_deg'] = float(_wrap_heading(heading_deg) or 0.0)
            if bank_deg is not None:
                self._status['bank_deg'] = float(bank_deg)
            if pitch_deg is not None:
                self._status['pitch_deg'] = float(pitch_deg)
            target = copy.deepcopy(self._status.get('controller_target') or {})
            if altitude_ft is not None:
                target['altitude_ft'] = float(altitude_ft)
            if heading_deg is not None:
                target['heading_deg'] = float(_wrap_heading(heading_deg) or 0.0)
            if speed_kt is not None:
                target['speed_kt'] = float(speed_kt)
            self._status['controller_target'] = target
        return ok

    def _apply_ap_guidance_locked(self, *, heading_deg: float | None = None, altitude_ft: float | None = None, speed_kt: float | None = None) -> bool:
        ok = False
        try:
            ok = self._invoke_event('AUTOPILOT_ON') or ok
        except Exception:
            pass
        try:
            ok = self._invoke_event('AP_MASTER') or ok
        except Exception:
            pass
        if heading_deg is not None:
            hdg = int(round(float(_wrap_heading(heading_deg) or 0.0))) % 360
            ok = self._invoke_event('HEADING_BUG_SET', hdg) or ok
            ok = self._invoke_event('AP_HDG_HOLD_ON') or ok
            self._safe_set_any(['AUTOPILOT HEADING LOCK DIR', 'AUTOPILOT HEADING LOCK DIR:1'], hdg)
        if altitude_ft is not None:
            alt = int(round(float(altitude_ft)))
            ok = self._invoke_event('AP_ALT_VAR_SET_ENGLISH', alt) or ok
            ok = self._invoke_event('AP_ALT_HOLD_ON') or ok
            self._safe_set_any(['AUTOPILOT ALTITUDE LOCK VAR', 'AUTOPILOT ALTITUDE LOCK VAR:1'], alt)
        if speed_kt is not None:
            spd = int(round(float(speed_kt)))
            ok = self._invoke_event('AP_SPD_VAR_SET', spd) or ok
            ok = self._invoke_event('AP_AIRSPEED_ON') or ok
            self._safe_set_any(['AUTOPILOT AIRSPEED HOLD VAR', 'AUTOPILOT AIRSPEED HOLD VAR:1'], spd)
        if ok:
            target = copy.deepcopy(self._status.get('controller_target') or {})
            if heading_deg is not None:
                target['heading_deg'] = float(_wrap_heading(heading_deg) or 0.0)
            if altitude_ft is not None:
                target['altitude_ft'] = float(altitude_ft)
            if speed_kt is not None:
                target['speed_kt'] = float(speed_kt)
            self._status['controller_target'] = target
        return ok


    def _send_axis_event(self, event_name: str, *params: int) -> bool:
        if not event_name:
            return False
        if len(params) <= 1:
            value = params[0] if params else None
            try:
                ok = self._invoke_event(event_name, value) if value is not None else self._invoke_event(event_name)
                self._log_sim_command_locked(kind='axis', name=event_name, value=value, ok=bool(ok), extra='params=single')
                return ok
            except OSError as exc:
                self._log_sim_command_locked(kind='axis', name=event_name, value=value, ok=False, extra=f'params=single err={exc}')
                return False
            except Exception as exc:
                self._log_sim_command_locked(kind='axis', name=event_name, value=value, ok=False, extra=f'params=single err={exc}')
                return False
        if self._event_cls is not None and self._sm is not None:
            try:
                event = self._event_cls(event_name.encode('utf-8'), self._sm)
                event(*params)
                self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=True, extra='params=multi via=EventClass')
                return True
            except OSError as exc:
                self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=False, extra=f'params=multi via=EventClass err={exc}')
                return False
            except Exception as exc:
                self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=False, extra=f'params=multi via=EventClass err={exc}')
                pass
        try:
            ok = self._invoke_event(event_name, params[0])
            self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=bool(ok), extra='params=fallback')
            return ok
        except OSError as exc:
            self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=False, extra=f'params=fallback err={exc}')
            return False
        except Exception as exc:
            self._log_sim_command_locked(kind='axis', name=event_name, value=params, ok=False, extra=f'params=fallback err={exc}')
            return False

    def _neutralize_control_surfaces_locked(self) -> None:
        try:
            self._send_axis_event('AXIS_AILERONS_SET', 0)
        except Exception:
            pass
        try:
            self._send_axis_event('AXIS_ELEVATOR_SET', 0)
        except Exception:
            pass

    def _apply_surface_guidance_locked(self, *, target_heading_deg: float, target_altitude_ft: float | None, target_speed_kt: float | None, cross_track_nm: float = 0.0, profile: str = 'pid', track_now: float | None = None, heading_now: float | None = None, bank_now: float | None = None, pitch_now: float | None = None, vs_now: float | None = None, altitude_now: float | None = None, airspeed_now: float | None = None, throttle_pct: float | None = None) -> bool:
        track_now = _floatify(track_now) if track_now is not None else (_floatify(self._status.get('track_deg')) or _floatify(self._status.get('heading_deg')))
        heading_now = _floatify(heading_now) if heading_now is not None else (_floatify(self._status.get('heading_deg')) or track_now)
        bank_now = _floatify(bank_now) if bank_now is not None else (_floatify(self._status.get('bank_deg')) or 0.0)
        pitch_now = _floatify(pitch_now) if pitch_now is not None else (_floatify(self._status.get('pitch_deg')) or 0.0)
        vs_now = _floatify(vs_now) if vs_now is not None else (_floatify(self._status.get('vertical_speed_fpm')) or 0.0)
        altitude_now = _floatify(altitude_now) if altitude_now is not None else (_floatify(self._status.get('actual_altitude_ft')) or _floatify(self._status.get('altitude_ft')) or 0.0)
        airspeed_now = _floatify(airspeed_now) if airspeed_now is not None else (_floatify(self._status.get('indicated_airspeed_kt')) or _floatify(self._status.get('ground_speed_kt')) or 0.0)
        throttle_pct = _floatify(throttle_pct) if throttle_pct is not None else _floatify(self._status.get('throttle_percent_total'))

        profile = 'pomax' if str(profile or '').lower().startswith('pomax') else 'pid'
        track_error = _heading_error_deg(track_now, target_heading_deg)
        heading_error = _heading_error_deg(heading_now, target_heading_deg)

        if profile == 'pomax':
            profile_cfg = waf_surface_profile()
            speed_factor = 0.55 if airspeed_now < 105.0 else (0.78 if airspeed_now < 135.0 else 1.0)
            desired_bank = _clamp(((track_error * profile_cfg['bank_gain']) - (cross_track_nm * profile_cfg['cross_gain']) - (bank_now * 0.30)) * speed_factor, -profile_cfg['bank_limit_deg'], profile_cfg['bank_limit_deg'])
            aileron_norm = _clamp((((desired_bank - bank_now) / 26.0) + (heading_error * profile_cfg['heading_gain'])) * speed_factor, -profile_cfg['aileron_limit'], profile_cfg['aileron_limit'])
            elevator_scale = int(profile_cfg['elevator_scale'])
            throttle_gain = float(profile_cfg['throttle_gain'])
            pitch_low = float(profile_cfg['pitch_limit_down'])
            pitch_high = float(profile_cfg['pitch_limit_up'])
        else:
            speed_factor = 0.65 if airspeed_now < 100.0 else (0.82 if airspeed_now < 130.0 else 1.0)
            desired_bank = _clamp(((track_error * 0.10) - (cross_track_nm * 4.0) - (bank_now * 0.26)) * speed_factor, -8.0, 8.0)
            aileron_norm = _clamp((((desired_bank - bank_now) / 28.0) + (heading_error / 180.0)) * speed_factor, -0.24, 0.24)
            elevator_scale = 4200
            throttle_gain = 0.34
            pitch_low = -3.0
            pitch_high = 4.0
        if abs(track_error) < 1.2 and abs(cross_track_nm) < 0.02:
            aileron_norm = 0.0
        aileron_cmd = int(round(aileron_norm * 8000))

        if target_altitude_ft is not None:
            altitude_error = float(target_altitude_ft) - altitude_now
            desired_pitch = _clamp((altitude_error / 1200.0) - (vs_now / 1600.0), pitch_low, pitch_high)
        else:
            desired_pitch = 0.0
        pitch_error = desired_pitch - pitch_now
        elevator_cmd = int(round(_clamp(pitch_error / 10.0, -1.0, 1.0) * elevator_scale))

        throttle_cmd = None
        if target_speed_kt is not None:
            speed_error = float(target_speed_kt) - airspeed_now
            desired_throttle_pct = _clamp((throttle_pct if throttle_pct is not None else 58.0) + (speed_error * throttle_gain), 22.0, 96.0)
            if abs(speed_error) >= 2.0:
                throttle_cmd = int(round((desired_throttle_pct / 100.0) * 16383))

        ok = False
        ok = self._send_axis_event('AXIS_AILERONS_SET', aileron_cmd) or self._send_axis_event('AILERON_SET', aileron_cmd) or ok
        ok = self._send_axis_event('AXIS_ELEVATOR_SET', elevator_cmd) or self._send_axis_event('ELEVATOR_SET', elevator_cmd) or ok
        if throttle_cmd is not None:
            ok = self._send_axis_event('AXIS_THROTTLE_SET', int(throttle_cmd)) or ok

        target = copy.deepcopy(self._status.get('controller_target') or {})
        target['heading_deg'] = float(_wrap_heading(target_heading_deg) or 0.0)
        if target_altitude_ft is not None:
            target['altitude_ft'] = float(target_altitude_ft)
        if target_speed_kt is not None:
            target['speed_kt'] = float(target_speed_kt)
        target['bank_cmd_deg'] = float(desired_bank)
        target['cross_track_nm'] = float(cross_track_nm)
        target['control_surface_mode'] = profile
        self._status['controller_target'] = target
        self._log_controller_tick_locked('surface-guidance', mode=profile, hdg=(f'{heading_now:.1f}' if heading_now is not None else None), track=(f'{track_now:.1f}' if track_now is not None else None), target_hdg=f'{float(_wrap_heading(target_heading_deg) or 0.0):.1f}', alt=f'{altitude_now:.0f}', target_alt=(f'{float(target_altitude_ft):.0f}' if target_altitude_ft is not None else None), speed=f'{airspeed_now:.0f}', target_speed=(f'{float(target_speed_kt):.0f}' if target_speed_kt is not None else None), cross_nm=f'{float(cross_track_nm):.3f}', bank_cmd=f'{desired_bank:.1f}', aileron=aileron_cmd, elevator=elevator_cmd, throttle=throttle_cmd, ok=ok)
        return ok


    def _route_loop(self, generation: int) -> None:
        interval_s = 0.35
        while not self._route_stop.is_set():
            try:
                with self._lock:
                    if generation != self._route_generation:
                        break
                    plan = list(self._route_plan)
                    status = copy.deepcopy(self._status)
                if len(plan) < 2:
                    break
                controller = copy.deepcopy(status.get('route_controller') or {})
                loop = bool(controller.get('loop'))
                speed_kt = _floatify(controller.get('speed_kt')) or 140.0
                altitude_ft = _floatify(controller.get('altitude_ft'))
                mode = _normalize_control_mode(controller.get('control_mode'))
                target_idx = int(_floatify(controller.get('current_index')) or 1)
                if target_idx <= 0:
                    target_idx = 1
                current_lat = _floatify(status.get('lat'))
                current_lon = _floatify(status.get('lon'))
                if current_lat is None or current_lon is None:
                    self._route_stop.wait(interval_s)
                    continue
                spawn_guard = copy.deepcopy(self._spawn_guard) if self._spawn_guard else None
                if spawn_guard and float(spawn_guard.get('until') or 0.0) > time.time():
                    sg_lat = _floatify(spawn_guard.get('lat'))
                    sg_lon = _floatify(spawn_guard.get('lon'))
                    if sg_lat is not None and sg_lon is not None:
                        dist_from_spawn = _haversine_nm(current_lat, current_lon, sg_lat, sg_lon)
                        if dist_from_spawn > 0.20:
                            current_lat, current_lon = sg_lat, sg_lon
                    sg_alt = _floatify(spawn_guard.get('altitude_ft'))
                    if sg_alt is not None:
                        live_alt = _floatify(status.get('actual_altitude_ft')) or _floatify(status.get('altitude_ft'))
                        if live_alt is None or abs(live_alt - sg_alt) > 800.0:
                            status['actual_altitude_ft'] = sg_alt
                            status['altitude_ft'] = sg_alt
                    sg_hdg = _floatify(spawn_guard.get('heading_deg'))
                    if sg_hdg is not None:
                        live_hdg = _floatify(status.get('track_deg')) or _floatify(status.get('heading_deg'))
                        if live_hdg is None or abs(_heading_error_deg(live_hdg, sg_hdg)) > 60.0:
                            status['track_deg'] = sg_hdg
                            status['heading_deg'] = sg_hdg
                    with self._lock:
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        now_controller.update({'active': True, 'mode': now_controller.get('mode') or ('pomax-law' if mode == 'pomax-law' else 'virtual-surface'), 'phase': 'settle', 'control_mode': mode, 'current_index': target_idx, 'waypoint_count': len(plan), 'message': f'Settling after reposition at waypoint {target_idx}. Holding heading/alignment before leg capture.'})
                        self._status['route_controller'] = now_controller
                    self._route_stop.wait(interval_s)
                    continue
                if target_idx >= len(plan):
                    if loop:
                        target_idx = 1
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller['current_index'] = target_idx
                            self._status['route_controller'] = now_controller
                    else:
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller.update({'active': False, 'mode': 'standby', 'phase': 'complete', 'message': 'Route complete.', 'current_index': len(plan) - 1})
                            self._status['route_controller'] = now_controller
                        break
                start = plan[target_idx - 1]
                end = plan[target_idx]
                leg_heading = _bearing_deg(start['lat'], start['lon'], end['lat'], end['lon'])
                remaining_nm = _haversine_nm(current_lat, current_lon, end['lat'], end['lon'])
                transition_nm = max(0.015, speed_kt * interval_s / 3600.0 * 0.9)
                lookahead_nm = max(0.035, speed_kt * 0.55 / 3600.0)
                on_path_nm = max(0.03, lookahead_nm * 1.5)
                target = _target_on_leg(current_lat, current_lon, start['lat'], start['lon'], end['lat'], end['lon'], lookahead_nm=lookahead_nm, on_path_nm=on_path_nm)
                leg_proj = _project_on_leg(current_lat, current_lon, start['lat'], start['lon'], end['lat'], end['lon'])
                signed_cross_nm = _signed_cross_track_nm(current_lat, current_lon, start['lat'], start['lon'], end['lat'], end['lon'])
                cross_nm = abs(float(target.get('cross_nm') or 0.0))
                along_nm = float(leg_proj.get('along_nm') or 0.0)
                leg_nm = max(1e-6, float(leg_proj.get('leg_nm') or 0.0))
                raw_t = float(leg_proj.get('raw_t') or leg_proj.get('t') or 0.0)
                path_heading_deg = _floatify(target.get('heading_deg')) or leg_heading
                current_hdg = _floatify(status.get('track_deg')) or _floatify(status.get('heading_deg')) or _floatify((status.get('controller_target') or {}).get('heading_deg')) or leg_heading
                direct_heading = _bearing_deg(current_lat, current_lon, end['lat'], end['lon'])
                reached_waypoint = (remaining_nm <= transition_nm and raw_t >= 0.985) or remaining_nm <= 0.012
                if reached_waypoint:
                    next_idx = target_idx + 1
                    if next_idx >= len(plan):
                        if loop:
                            next_idx = 1
                        else:
                            with self._lock:
                                now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                                now_controller.update({'active': True, 'mode': 'await-extension', 'phase': 'await-extension', 'current_index': target_idx, 'waypoint_count': len(plan), 'control_mode': mode, 'message': f'Waypoint {target_idx + 1} reached. Waiting for more waypoints or Stop.'})
                                self._status['route_controller'] = now_controller
                            self._route_stop.wait(interval_s)
                            continue
                    with self._lock:
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        next_mode = 'route-ap' if mode == 'ap-guidance' else ('pomax-law' if mode == 'pomax-law' else ('virtual-surface' if mode == 'virtual-surface' else 'virtual-direct'))
                        now_controller.update({'active': True, 'mode': next_mode, 'phase': 'tracking', 'current_index': next_idx, 'waypoint_count': len(plan), 'control_mode': mode, 'message': f'Leg {target_idx} complete. Tracking waypoint {next_idx + 1} of {len(plan)}.'})
                        self._status['route_controller'] = now_controller
                    self._route_stop.wait(interval_s)
                    continue
                intercept_deg = _clamp(signed_cross_nm * 45.0, -18.0, 18.0)
                intercept_heading = _wrap_heading(leg_heading - intercept_deg)
                if mode == 'pomax-law':
                    # Hold the active leg longer. Only steer direct-to-waypoint when we are genuinely displaced,
                    # otherwise stay biased to the leg heading so we do not cut the corner toward the next leg early.
                    if cross_nm > 0.18:
                        desired_heading = direct_heading
                    elif cross_nm > 0.05:
                        desired_heading = intercept_heading
                    else:
                        desired_heading = path_heading_deg
                    smooth_heading = waf_blend_heading(current_hdg, desired_heading, max_step_deg=1.1 if cross_nm < 0.05 else 1.8, blend=0.14 if cross_nm < 0.05 else 0.20) or desired_heading
                else:
                    if cross_nm > 0.12:
                        desired_heading = direct_heading
                    elif cross_nm > 0.03:
                        desired_heading = intercept_heading
                    else:
                        desired_heading = leg_heading
                    smooth_heading = _blend_heading(current_hdg, desired_heading, max_step_deg=1.8 if cross_nm < 0.05 else 2.6, blend=0.20 if cross_nm < 0.05 else 0.28) or desired_heading
                if mode == 'ap-guidance':
                    with self._lock:
                        ok = self._apply_ap_guidance_locked(heading_deg=smooth_heading, altitude_ft=altitude_ft, speed_kt=speed_kt)
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        now_controller.update({'active': True, 'mode': 'route-ap', 'phase': 'tracking', 'control_mode': mode, 'current_index': target_idx, 'waypoint_count': len(plan), 'message': f'Flying leg {target_idx} of {len(plan)-1} • targeting waypoint {target_idx + 1} of {len(plan)} • cross-track {cross_nm:.2f} nm'})
                        self._status['route_controller'] = now_controller
                    if not ok:
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller.update({'active': False, 'mode': 'standby', 'phase': 'error', 'message': 'Route controller could not command the autopilot through SimConnect.'})
                            self._status['route_controller'] = now_controller
                        break
                elif mode == 'virtual-surface':
                    with self._lock:
                        ok = self._apply_surface_guidance_locked(target_heading_deg=smooth_heading, target_altitude_ft=altitude_ft, target_speed_kt=speed_kt, cross_track_nm=signed_cross_nm, profile='pid', track_now=_floatify(status.get('track_deg')) or current_hdg, heading_now=_floatify(status.get('heading_deg')) or current_hdg, bank_now=_floatify(status.get('bank_deg')), pitch_now=_floatify(status.get('pitch_deg')), vs_now=_floatify(status.get('vertical_speed_fpm')), altitude_now=_floatify(status.get('actual_altitude_ft')) or _floatify(status.get('altitude_ft')), airspeed_now=_floatify(status.get('indicated_airspeed_kt')) or _floatify(status.get('ground_speed_kt')), throttle_pct=_floatify(status.get('throttle_percent_total')))
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        now_controller.update({'active': True, 'mode': 'virtual-surface', 'phase': 'tracking', 'control_mode': mode, 'current_index': target_idx, 'waypoint_count': len(plan), 'message': f'PID controller on leg {target_idx} of {len(plan)-1} • next waypoint {target_idx + 1} • cross-track {cross_nm:.2f} nm'})
                        self._status['route_controller'] = now_controller
                    if not ok:
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller.update({'active': False, 'mode': 'standby', 'phase': 'error', 'message': 'PID controller could not send control-surface commands through SimConnect.'})
                            self._status['route_controller'] = now_controller
                        break
                elif mode == 'pomax-law':
                    with self._lock:
                        ok = self._apply_virtual_path_guidance_locked(current_lat=current_lat, current_lon=current_lon, current_heading_deg=current_hdg, current_altitude_ft=_floatify(status.get('actual_altitude_ft')) or _floatify(status.get('altitude_ft')), current_speed_kt=_floatify(status.get('indicated_airspeed_kt')) or _floatify(status.get('ground_speed_kt')), current_bank_deg=_floatify(status.get('bank_deg')), current_pitch_deg=_floatify(status.get('pitch_deg')), current_vs_fpm=_floatify(status.get('vertical_speed_fpm')), current_throttle_pct=_floatify(status.get('throttle_percent_total')), target_heading_deg=smooth_heading, target_altitude_ft=altitude_ft, target_speed_kt=speed_kt, interval_s=interval_s, cross_track_nm=signed_cross_nm, profile='pomax')
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        now_controller.update({'active': True, 'mode': 'pomax-law', 'phase': 'tracking', 'control_mode': mode, 'current_index': target_idx, 'waypoint_count': len(plan), 'message': f'We are-Flying controller on leg {target_idx} of {max(1, len(plan)-1)} • next waypoint {target_idx + 1} • remaining {remaining_nm:.2f} nm • cross-track {cross_nm:.2f} nm'})
                        self._status['route_controller'] = now_controller
                    if not ok:
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller.update({'active': False, 'mode': 'standby', 'phase': 'error', 'message': 'We are-Flying controller could not move the virtual pilot through SimConnect.'})
                            self._status['route_controller'] = now_controller
                        break
                else:
                    step_nm = max(0.008, speed_kt * interval_s / 3600.0)
                    move_heading = smooth_heading
                    move_nm = min(step_nm, remaining_nm)
                    next_lat, next_lon = _destination_point(current_lat, current_lon, move_heading, move_nm)
                    with self._lock:
                        ok = self._apply_reposition_locked(lat=next_lat, lon=next_lon, altitude_ft=altitude_ft, heading_deg=move_heading, speed_kt=speed_kt)
                        now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                        now_controller.update({'active': True, 'mode': 'virtual-direct', 'phase': 'tracking', 'control_mode': mode, 'current_index': target_idx, 'waypoint_count': len(plan), 'message': f'Virtual direct flight on leg {target_idx} of {len(plan)-1} • next waypoint {target_idx + 1} • remaining {remaining_nm:.2f} nm'})
                        self._status['route_controller'] = now_controller
                    if not ok:
                        with self._lock:
                            now_controller = copy.deepcopy(self._status.get('route_controller') or {})
                            now_controller.update({'active': False, 'mode': 'standby', 'phase': 'error', 'message': 'Virtual direct-flight controller could not reposition the aircraft through SimConnect.'})
                            self._status['route_controller'] = now_controller
                        break
                self._route_stop.wait(interval_s)
            except Exception as exc:
                log.warning('Route controller error: %s', exc, exc_info=True)
                with self._lock:
                    controller = copy.deepcopy(self._status.get('route_controller') or {})
                    controller.update({'active': False, 'mode': 'standby', 'phase': 'error', 'message': str(exc)})
                    self._status['route_controller'] = controller
                    self._status['last_error'] = str(exc)
                break

    def _append_log_entry_locked(self) -> None:
        try:
            self._logs_path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if self._logs_path.exists():
                existing = json.loads(self._logs_path.read_text(encoding='utf-8'))
                if not isinstance(existing, list):
                    existing = []
            entry = {
                'id': str(int(time.time() * 1000)),
                'logged_at': _utc_now(),
                'aircraft_title': self._status.get('aircraft_title') or 'Unknown Aircraft',
                'session_state': self._status.get('session_state') or 'idle',
                'samples': int((self._status.get('stats') or {}).get('samples') or 0),
                'max_altitude_ft': float((self._status.get('stats') or {}).get('max_altitude_ft') or 0),
            }
            if entry['samples'] > 0:
                existing = [entry] + existing[:99]
                self._logs_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception:
            log.debug('Could not append flight log.', exc_info=True)

    def _cleanup_locked(self) -> None:
        try:
            if self._sm is not None and hasattr(self._sm, 'exit'):
                self._sm.exit()
        except Exception:
            pass
        self._worker = None
        self._sm = None
        self._aq = None
        self._ae = None
        self._connected_at = None
        self._route_stop.set()
        self._route_worker = None
        self._route_plan = []
        self._spawn_guard = None
        self._stop.clear()

