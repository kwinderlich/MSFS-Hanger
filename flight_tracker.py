from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from paths import LOG_DIR, USER_DATA_DIR




def _build_simconnect_logger() -> logging.Logger:
    logger = logging.getLogger("simconnect")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(LOG_DIR / 'simconnect.log'), encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(asctime)s  %(levelname)-8s  %(message)s', '%Y-%m-%d %H:%M:%S'))
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


def _safe_repr(value, limit: int = 220) -> str:
    try:
        out = repr(value)
    except Exception:
        out = '<unrepr-able>'
    return out if len(out) <= limit else out[:limit-3] + '...'


_SIMLOG = _build_simconnect_logger()

def _simlog(level: str, message: str, *args):
    logger = _SIMLOG
    try:
        getattr(logger, level.lower())(message, *args)
    finally:
        for h in list(getattr(logger, 'handlers', []) or []):
            try:
                h.flush()
            except Exception:
                pass


class FlightTracker:
    """Best-effort SimConnect bridge for Phase 1 flight integration.

    This adapter is intentionally conservative: if SimConnect or its Python
    wrapper is not installed, the rest of the app keeps working and the flight
    screen simply reports the issue instead of crashing the library.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._poll_interval = 1.0
        self._backend_name = ''
        self._status: dict[str, Any] = {
            'available': False,
            'connected': False,
            'sim_running': False,
            'backend': '',
            'state': 'starting',
            'status_message': 'Initializing flight integration...',
            'connect_requests': 0,
            'last_error': '',
            'last_update': '',
            'aircraft_title': '',
            'aircraft_icao': '',
            'lat': None,
            'lon': None,
            'altitude_ft': None,
            'ground_speed_kt': None,
            'indicated_airspeed_kt': None,
            'heading_deg': None,
            'track_deg': None,
            'true_airspeed_kt': None,
            'actual_altitude_ft': None,
            'altitude_agl_ft': None,
            'ground_elevation_ft': None,
            'fuel_flow_gph': None,
            'endurance_hours': None,
            'range_remaining_nm': None,
            'session_state': 'idle',
            'sim_rate': None,
            'flaps_percent': None,
            'gear_percent': None,
            'landing_lights': None,
            'nav_lights': None,
            'beacon_lights': None,
            'strobe_lights': None,
            'taxi_lights': None,
            'recognition_lights': None,
            'throttle_percent_engine1': None,
            'throttle_percent_engine2': None,
            'throttle_percent_engine3': None,
            'throttle_percent_engine4': None,
            'throttle_percent_total': None,
            'engine_count': None,
            'has_retractable_gear': None,
            'pause_state': None,
            'fuel_total_gal': None,
            'fuel_total_capacity_gal': None,
            'fuel_remaining_percent': None,
            'wind_direction_deg': None,
            'wind_speed_kt': None,
            'total_air_temp_c': None,
            'static_air_temp_c': None,
            'sea_level_pressure_hpa': None,
            'visibility_sm': None,
            'ap_selected_altitude_ft': None,
            'sim_time_utc': '',
            'sim_time_local': '',
            'on_ground': None,
            'vertical_speed_fpm': None,
            'follow_recommended': True,
            'trail': [],
            'stats': {
                'samples': 0,
                'max_altitude_ft': None,
                'max_ground_speed_kt': None,
                'started_at': '',
                'elapsed_seconds': 0,
            },
        }
        self._sim = None
        self._aq = None
        self._ae = None
        self._session_path = USER_DATA_DIR / 'flight_logs.json'
        self._session_track = []
        _simlog('info', 'FlightTracker cleanup complete.')
        self._started_monotonic = 0.0
        self._poll_counter = 0
        self._sim_rate_override_until = 0.0
        _simlog('info', 'FlightTracker initialized.')
        self._attempt_import()

    def _attempt_import(self) -> None:
        backend = ''
        try:
            from SimConnect import SimConnect as SCSimConnect  # type: ignore
            from SimConnect import AircraftRequests, AircraftEvents  # type: ignore
            self._connector_factory = lambda: (SCSimConnect(), AircraftRequests, AircraftEvents)
            backend = 'SimConnect'
        except Exception:
            self._connector_factory = None
        with self._lock:
            self._backend_name = backend
            self._status['available'] = bool(self._connector_factory)
            self._status['backend'] = backend
            if not backend:
                self._status['state'] = 'unavailable'
                self._status['status_message'] = 'Python SimConnect package not installed. Run install.bat to install requirements.'
                self._status['last_error'] = self._status['status_message']
                _simlog('warning', 'SimConnect Python package import failed; flight integration unavailable.')
            else:
                self._status['state'] = 'ready'
                self._status['status_message'] = 'SimConnect package detected. Ready to connect.'
                _simlog('info', 'SimConnect Python package detected using backend=%s.', backend)

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = dict(self._status)
            status['trail'] = list(self._status.get('trail') or [])
            status['stats'] = dict(self._status.get('stats') or {})
            return status

    def configure(self, poll_interval: float = 1.0) -> dict[str, Any]:
        with self._lock:
            self._poll_interval = max(0.4, min(5.0, float(poll_interval or 1.0)))
            _simlog('info', 'FlightTracker configured: poll_interval=%.2fs', self._poll_interval)
        return self.status()

    def connect(self) -> dict[str, Any]:
        _simlog('info', 'Connect requested. pid=%s thread=%s', os.getpid(), threading.current_thread().name)
        with self._lock:
            self._status['connect_requests'] = int(self._status.get('connect_requests') or 0) + 1
            if not self._connector_factory:
                self._status['available'] = False
                self._status['connected'] = False
                self._status['sim_running'] = False
                self._status['state'] = 'unavailable'
                self._status['status_message'] = 'Python SimConnect package not installed. Run install.bat to install requirements.'
                self._status['last_error'] = self._status['status_message']
                _simlog('error', 'Connect failed: SimConnect package not installed.')
                return self.status()
            if self._thread and self._thread.is_alive():
                self._status['state'] = 'connecting' if not self._status.get('connected') else 'connected'
                self._status['status_message'] = 'Connection attempt already running.' if self._status['state']=='connecting' else 'Already connected.'
                _simlog('info', 'Connect ignored: worker already running.')
                return self.status()
            self._status['connected'] = False
            self._status['sim_running'] = False
            self._status['state'] = 'connecting'
            self._status['status_message'] = 'Connecting to simulator...' 
            self._status['last_error'] = ''
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker, name='hangar-flight-tracker', daemon=True)
            _simlog('info', 'Worker thread object created: %s', self._thread.name)
            self._thread.start()
            _simlog('info', 'FlightTracker worker thread started.')
            return self.status()

    def command(self, command: str) -> dict[str, Any]:
        cmd = str(command or '').strip().lower()
        _simlog('info', 'Command requested: %s', cmd)
        ae = self._ae
        if ae is None:
            return {**self.status(), 'ok': False, 'message': 'AircraftEvents is not available for commands.'}
        current_pause = str(self.status().get('pause_state') or 'running').lower()
        event_map = {
            'sim_rate_increase': [('SIM_RATE_INCR', None), ('SIM_RATE_INCREASE', None), ('SIM_RATE_SET', max(2, int(round(float(self.status().get('sim_rate') or 1))) + 1))],
            'sim_rate_decrease': [('SIM_RATE_DECR', None), ('SIM_RATE_DECREASE', None), ('SIM_RATE_SET', max(1, int(round(float(self.status().get('sim_rate') or 1))) - 1))],
            'sim_rate_reset': [('SIM_RATE_SET', 1), ('SIM_RATE', None), ('SIM_RATE_DECR', None)],
            'pause_toggle': ([('PAUSE_OFF', None), ('PAUSE_SET', 0), ('TOGGLE_PAUSE', None), ('PAUSE_TOGGLE', None), ('PAUSE', None)] if current_pause in ('paused','sim_pause') else [('PAUSE_ON', None), ('PAUSE_SET', 1), ('TOGGLE_PAUSE', None), ('PAUSE_TOGGLE', None), ('PAUSE', None)]),
            'active_pause_toggle': ([('ACTIVE_PAUSE_OFF', None), ('ACTIVE_PAUSE_SET', 0), ('ACTIVE_PAUSE_TOGGLE', None)] if current_pause == 'active_pause' else [('ACTIVE_PAUSE_ON', None), ('ACTIVE_PAUSE_SET', 1), ('ACTIVE_PAUSE_TOGGLE', None)]) + [('TOGGLE_ACTIVE_PAUSE', None), ('ACTIVE_PAUSE', None)],
        }
        candidates = event_map.get(cmd)
        if not candidates:
            return {**self.status(), 'ok': False, 'message': f'Unknown command: {cmd}'}
        last_error = None
        for event_name, arg in candidates:
            try:
                _simlog('info', 'Attempting command=%s event=%s arg=%s pause_state=%s sim_rate=%s', cmd, event_name, arg, current_pause, self.status().get('sim_rate'))
                ev = ae.find(event_name)
                if not ev:
                    _simlog('warning', 'Command event not found: %s', event_name)
                    continue
                if arg is None:
                    try:
                        ev()
                    except TypeError:
                        ev(0)
                else:
                    try:
                        ev(arg)
                    except TypeError:
                        ev()
                _simlog('info', 'Command executed via SimConnect event %s arg=%s', event_name, arg)
                with self._lock:
                    if cmd == 'sim_rate_reset':
                        self._status['sim_rate'] = 1
                        self._sim_rate_override_until = time.monotonic() + 2.5
                    elif cmd == 'sim_rate_increase':
                        self._status['sim_rate'] = max(1, int(round(float(self._status.get('sim_rate') or 1))) + 1)
                        self._sim_rate_override_until = time.monotonic() + 1.5
                    elif cmd == 'sim_rate_decrease':
                        self._status['sim_rate'] = max(1, int(round(float(self._status.get('sim_rate') or 1))) - 1)
                        self._sim_rate_override_until = time.monotonic() + 1.5
                    elif cmd == 'pause_toggle':
                        self._status['pause_state'] = 'running' if event_name in ('PAUSE_OFF',) or arg == 0 else 'paused'
                    elif cmd == 'active_pause_toggle':
                        self._status['pause_state'] = 'running' if event_name in ('ACTIVE_PAUSE_OFF',) or arg == 0 else 'active_pause'
                return {**self.status(), 'ok': True, 'message': f'Executed {event_name}'}
            except Exception as exc:
                last_error = exc
                _simlog('exception', 'Command failed %s: %s', event_name, exc)
        _simlog('error', 'Command exhausted without success: %s last_error=%s', cmd, last_error)
        return {**self.status(), 'ok': False, 'message': str(last_error or 'No matching event found')}

    def disconnect(self) -> dict[str, Any]:
        _simlog('info', 'Disconnect requested.')
        self._stop.set()
        thread = None
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._write_flight_log()
        self._cleanup()
        with self._lock:
            self._status['connected'] = False
            self._status['sim_running'] = False
            self._status['state'] = 'ready' if self._connector_factory else 'unavailable'
            self._status['status_message'] = 'Disconnected.' if self._connector_factory else 'Python SimConnect package not installed. Run install.bat to install requirements.'
            self._status['last_error'] = '' if self._connector_factory else self._status['status_message']
        return self.status()

    def _write_flight_log(self) -> None:
        try:
            status = self.status()
            stats = status.get('stats') or {}
            samples = int(stats.get('samples') or 0)
            if samples <= 0:
                return
            entry = {
                'id': datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'),
                'logged_at': datetime.now(timezone.utc).isoformat(),
                'aircraft_title': status.get('aircraft_title') or '',
                'aircraft_icao': status.get('aircraft_icao') or '',
                'session_state': status.get('session_state') or '',
                'samples': samples,
                'started_at': stats.get('started_at') or '',
                'elapsed_seconds': stats.get('elapsed_seconds') or 0,
                'max_altitude_ft': stats.get('max_altitude_ft'),
                'max_ground_speed_kt': stats.get('max_ground_speed_kt'),
                'last_position': {'lat': status.get('lat'), 'lon': status.get('lon')},
                'track': list(self._session_track[-500:]),
            }
            items = []
            try:
                if self._session_path.exists():
                    raw = json.loads(self._session_path.read_text(encoding='utf-8'))
                    if isinstance(raw, list):
                        items = raw
            except Exception:
                items = []
            items = [entry] + items[:49]
            self._session_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding='utf-8')
            _simlog('info', 'Flight log written with %s samples.', samples)
        except Exception as exc:
            _simlog('warning', 'Could not write flight log: %s', exc)

    def _cleanup(self) -> None:
        try:
            if self._sim is not None:
                exit_fn = getattr(self._sim, 'exit', None)
                if callable(exit_fn):
                    exit_fn()
        except Exception:
            pass
        self._sim = None
        self._aq = None
        self._ae = None
        self._session_path = USER_DATA_DIR / 'flight_logs.json'
        self._session_track = []
        _simlog('info', 'FlightTracker cleanup complete.')
        with self._lock:
            self._thread = None

    def _worker(self) -> None:
        try:
            _simlog('info', 'Worker loop starting.')
            self._open_connection()
            while not self._stop.is_set():
                self._poll_once()
                self._stop.wait(self._poll_interval)
        except Exception as exc:
            _simlog('exception', 'Worker failed: %s', exc)
            with self._lock:
                self._status['connected'] = False
                self._status['sim_running'] = False
                self._status['state'] = 'failed'
                self._status['status_message'] = f'Connection failed: {exc}'
                self._status['last_error'] = str(exc)
        finally:
            self._cleanup()

    def _open_connection(self) -> None:
        if not self._connector_factory:
            raise RuntimeError('SimConnect package is not available.')
        _simlog('info', 'Opening SimConnect connection...')
        sim, aircraft_requests_factory, aircraft_events_factory = self._connector_factory()
        _simlog('info', 'SimConnect object created: %s', type(sim).__name__)
        aq = aircraft_requests_factory(sim, _time=200)
        _simlog('info', 'AircraftRequests created successfully.')
        ae = None
        try:
            ae = aircraft_events_factory(sim)
            _simlog('info', 'AircraftEvents created successfully.')
        except Exception as exc:
            _simlog('warning', 'AircraftEvents create failed: %s', exc)
        self._sim = sim
        self._aq = aq
        self._ae = ae
        self._session_track = []
        self._started_monotonic = time.monotonic()
        with self._lock:
            self._status['connected'] = True
            self._status['sim_running'] = True
            self._status['backend'] = self._backend_name
            self._status['state'] = 'connected'
            self._status['status_message'] = 'Connected to SimConnect.'
            self._status['last_error'] = ''
            self._status['trail'] = []
            self._status['stats'] = {
                'samples': 0,
                'max_altitude_ft': None,
                'max_ground_speed_kt': None,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'elapsed_seconds': 0,
            }
            _simlog('info', 'SimConnect connection opened successfully.')

    def _get(self, name: str, default=None):
        if self._aq is None:
            return default
        try:
            value = self._aq.get(name)
            return default if value is None else value
        except Exception as exc:
            _simlog('warning', 'Data request failed for %s: %s', name, exc)
            return default

    def _get_first(self, names, default=None):
        for name in names:
            value = self._get(name, None)
            if value is not None:
                return value
        return default

    def _poll_once(self) -> None:
        self._poll_counter += 1
        # Prefer the underscore-style SimVar names that match the working TCalc example.
        # Keep older space-separated names as fallbacks. Advanced values must not break the
        # basic lat/lon/altitude/airspeed path if they come back blank.
        lat = self._get_first(['PLANE_LATITUDE', 'PLANE LATITUDE'])
        lon = self._get_first(['PLANE_LONGITUDE', 'PLANE LONGITUDE'])
        altitude_ft = self._get_first(['INDICATED_ALTITUDE', 'INDICATED ALTITUDE', 'PLANE_ALTITUDE', 'PLANE ALTITUDE'])
        actual_altitude_ft = self._get_first(['PLANE_ALTITUDE', 'PLANE ALTITUDE'])
        altitude_agl_ft = self._get_first(['PLANE_ALT_ABOVE_GROUND', 'PLANE ALT ABOVE GROUND'])
        ground_elevation_ft = self._get_first(['GROUND_ALTITUDE', 'GROUND ALTITUDE'])
        heading_deg = self._get_first(['PLANE_HEADING_DEGREES_TRUE', 'PLANE HEADING DEGREES TRUE'])
        track_deg = self._get_first(['GPS_GROUND_TRUE_TRACK', 'GPS GROUND TRUE TRACK', 'GPS_GROUND_MAGNETIC_TRACK'])
        ground_speed_kt = self._get_first(['GROUND_VELOCITY', 'GROUND VELOCITY'])
        indicated_airspeed_kt = self._get_first(['AIRSPEED_INDICATED', 'AIRSPEED INDICATED'])
        true_airspeed_kt = self._get_first(['AIRSPEED_TRUE', 'AIRSPEED TRUE'])
        on_ground = self._get_first(['SIM_ON_GROUND', 'SIM ON GROUND'])
        vertical_speed_fpm = self._get_first(['VERTICAL_SPEED', 'VERTICAL SPEED'])
        fuel_flow_pph = self._get_first(['ESTIMATED_FUEL_FLOW', 'ESTIMATED FUEL FLOW', 'TURB_ENG_FUEL_FLOW_PPH:1', 'TURB ENG FUEL FLOW PPH:1'])
        fuel_total_quantity = self._get_first(['FUEL_TOTAL_QUANTITY', 'FUEL TOTAL QUANTITY'])
        fuel_total_capacity = self._get_first(['FUEL_TOTAL_CAPACITY', 'FUEL TOTAL CAPACITY'])
        total_air_temp_c = self._get_first(['TOTAL_AIR_TEMPERATURE', 'TOTAL AIR TEMPERATURE'])
        static_air_temp_c = self._get_first(['AMBIENT_TEMPERATURE', 'AMBIENT TEMPERATURE'])
        wind_direction_deg = self._get_first(['AMBIENT_WIND_DIRECTION', 'AMBIENT WIND DIRECTION'])
        wind_speed_kt = self._get_first(['AMBIENT_WIND_VELOCITY', 'AMBIENT WIND VELOCITY'])
        sea_level_pressure_hpa = self._get_first(['SEA_LEVEL_PRESSURE', 'SEA LEVEL PRESSURE'])
        visibility_sm = self._get_first(['AMBIENT_VISIBILITY', 'AMBIENT VISIBILITY'])
        ap_selected_altitude_ft = self._get_first(['AUTOPILOT_ALTITUDE_LOCK_VAR', 'AUTOPILOT ALTITUDE LOCK VAR'])
        sim_rate = self._get_first(['SIMULATION_RATE', 'SIMULATION RATE'])
        pause_state_ex1 = self._get_first(['PAUSE_EX1', 'PAUSE EX1', 'PAUSE'])
        flaps_percent = self._get_first(['FLAPS_HANDLE_PERCENT', 'FLAPS HANDLE PERCENT'])
        gear_handle_position = self._get_first(['GEAR_HANDLE_POSITION', 'GEAR HANDLE POSITION'])
        gear_left_position = self._get_first(['GEAR_LEFT_POSITION', 'GEAR LEFT POSITION'])
        gear_center_position = self._get_first(['GEAR_CENTER_POSITION', 'GEAR CENTER POSITION'])
        gear_right_position = self._get_first(['GEAR_RIGHT_POSITION', 'GEAR RIGHT POSITION'])
        gear_percent = self._get_first(['GEAR_POSITION', 'GEAR POSITION'])
        landing_lights = self._get_first(['LIGHT_LANDING', 'LIGHT LANDING'])
        nav_lights = self._get_first(['LIGHT_NAV', 'LIGHT NAV'])
        beacon_lights = self._get_first(['LIGHT_BEACON', 'LIGHT BEACON'])
        strobe_lights = self._get_first(['LIGHT_STROBE', 'LIGHT STROBE'])
        taxi_lights = self._get_first(['LIGHT_TAXI', 'LIGHT TAXI'])
        recognition_lights = self._get_first(['LIGHT_RECOGNITION', 'LIGHT RECOGNITION'])
        throttle1 = self._get_first(['GENERAL_ENG_THROTTLE_LEVER_POSITION:1', 'GENERAL ENG THROTTLE LEVER POSITION:1'])
        throttle2 = self._get_first(['GENERAL_ENG_THROTTLE_LEVER_POSITION:2', 'GENERAL ENG THROTTLE LEVER POSITION:2'])
        throttle3 = self._get_first(['GENERAL_ENG_THROTTLE_LEVER_POSITION:3', 'GENERAL ENG THROTTLE LEVER POSITION:3'])
        throttle4 = self._get_first(['GENERAL_ENG_THROTTLE_LEVER_POSITION:4', 'GENERAL ENG THROTTLE LEVER POSITION:4'])
        zulu_hours = self._get_first(['ZULU_TIME', 'ZULU TIME'])
        local_hours = self._get_first(['LOCAL_TIME', 'LOCAL TIME'])
        aircraft_title = self._get_first(['TITLE'], '')
        aircraft_icao = self._get_first(['ATC_MODEL', 'ATC MODEL'], '')
        engine_count = self._get_first(['NUMBER_OF_ENGINES', 'NUMBER OF ENGINES'])
        retractable_gear = self._get_first(['IS_GEAR_RETRACTABLE', 'IS GEAR RETRACTABLE', 'RETRACTABLE_GEAR', 'RETRACTABLE GEAR'])

        with self._lock:
            self._status['connected'] = True
            self._status['sim_running'] = True
            self._status['state'] = 'connected'
            self._status['status_message'] = 'Receiving live telemetry.'
            self._status['last_error'] = ''
            self._status['last_update'] = datetime.now(timezone.utc).isoformat()
            self._status['aircraft_title'] = _safe_text(aircraft_title)
            self._status['aircraft_icao'] = _safe_text(aircraft_icao)
            self._status['lat'] = _safe_float(lat)
            self._status['lon'] = _safe_float(lon)
            self._status['altitude_ft'] = _choose_value(_safe_float(altitude_ft), self._status.get('altitude_ft'))
            self._status['actual_altitude_ft'] = _choose_value(_safe_float(actual_altitude_ft), self._status.get('actual_altitude_ft'))
            self._status['altitude_agl_ft'] = _choose_value(_safe_float(altitude_agl_ft), self._status.get('altitude_agl_ft'))
            self._status['ground_elevation_ft'] = _choose_value(_safe_float(ground_elevation_ft), self._status.get('ground_elevation_ft'))
            self._status['heading_deg'] = _best_heading(_normalize_heading(_angle_to_degrees(_safe_float(heading_deg))), self._status.get('heading_deg'))
            self._status['track_deg'] = _best_heading(_normalize_heading(_angle_to_degrees(_safe_float(track_deg))), self._status.get('track_deg'))
            self._status['ground_speed_kt'] = _choose_value(_safe_float(ground_speed_kt), self._status.get('ground_speed_kt'))
            self._status['indicated_airspeed_kt'] = _choose_value(_safe_float(indicated_airspeed_kt), self._status.get('indicated_airspeed_kt'))
            self._status['true_airspeed_kt'] = _choose_value(_safe_float(true_airspeed_kt), self._status.get('true_airspeed_kt'))
            self._status['on_ground'] = bool(on_ground) if on_ground is not None else None
            self._status['vertical_speed_fpm'] = _choose_value(_safe_float(vertical_speed_fpm), self._status.get('vertical_speed_fpm'))
            fuel_flow_val = _safe_float(fuel_flow_pph)
            self._status['fuel_flow_gph'] = _choose_value((fuel_flow_val / 6.7) if fuel_flow_val is not None else None, self._status.get('fuel_flow_gph'))
            self._status['fuel_total_gal'] = _choose_value(_safe_float(fuel_total_quantity), self._status.get('fuel_total_gal'))
            self._status['fuel_total_capacity_gal'] = _choose_value(_safe_float(fuel_total_capacity), self._status.get('fuel_total_capacity_gal'))
            if self._status.get('fuel_total_gal') is not None and self._status.get('fuel_total_capacity_gal'):
                try:
                    pct = (float(self._status['fuel_total_gal']) / float(self._status['fuel_total_capacity_gal'])) * 100.0
                except Exception:
                    pct = None
                self._status['fuel_remaining_percent'] = _choose_value(pct, self._status.get('fuel_remaining_percent'))
            self._status['wind_direction_deg'] = _best_heading(_normalize_heading(_angle_to_degrees(_safe_float(wind_direction_deg))), self._status.get('wind_direction_deg'))
            self._status['wind_speed_kt'] = _choose_value(_safe_float(wind_speed_kt), self._status.get('wind_speed_kt'))
            self._status['total_air_temp_c'] = _choose_value(_safe_float(total_air_temp_c), self._status.get('total_air_temp_c'))
            self._status['static_air_temp_c'] = _choose_value(_safe_float(static_air_temp_c), self._status.get('static_air_temp_c'))
            slp = _safe_float(sea_level_pressure_hpa)
            self._status['sea_level_pressure_hpa'] = _choose_value((slp * 33.8639) if slp is not None and slp < 100 else slp, self._status.get('sea_level_pressure_hpa'))
            vis = _safe_float(visibility_sm)
            self._status['visibility_sm'] = _choose_value((vis / 1609.344) if vis is not None and vis > 1000 else vis, self._status.get('visibility_sm'))
            self._status['ap_selected_altitude_ft'] = _choose_value(_safe_float(ap_selected_altitude_ft), self._status.get('ap_selected_altitude_ft'))
            sim_rate_val = _safe_float(sim_rate)
            if time.monotonic() >= getattr(self, '_sim_rate_override_until', 0.0):
                self._status['sim_rate'] = _choose_value((round(sim_rate_val) if sim_rate_val is not None else None), self._status.get('sim_rate'))
            pause_raw = _safe_float(pause_state_ex1)
            if pause_raw is not None:
                try:
                    pflag = int(round(pause_raw))
                except Exception:
                    pflag = None
                if pflag is not None:
                    if pflag & 4:
                        self._status['pause_state'] = 'active_pause'
                    elif pflag & 1 or pflag & 8:
                        self._status['pause_state'] = 'paused'
                    else:
                        self._status['pause_state'] = 'running'
            flaps_val = _safe_float(flaps_percent)
            if flaps_val is not None and flaps_val <= 1.01:
                flaps_val = flaps_val * 100.0
            def _gear_scale(v):
                v = _safe_float(v)
                if v is None:
                    return None
                return (v * 100.0) if v <= 1.01 else v
            gear_candidates = [_gear_scale(gear_left_position), _gear_scale(gear_center_position), _gear_scale(gear_right_position), _gear_scale(gear_percent), _gear_scale(gear_handle_position)]
            gear_vals = [v for v in gear_candidates if v is not None]
            gear_val = max(gear_vals) if gear_vals else None
            if gear_val is None:
                gear_val = self._status.get('gear_percent')
            if self._status.get('on_ground') is True and ((self._status.get('altitude_agl_ft') or 0) < 50):
                if gear_val is None or gear_val <= 1:
                    gear_val = 100.0
            self._status['flaps_percent'] = _choose_value(flaps_val, self._status.get('flaps_percent'))
            self._status['gear_percent'] = _choose_value(gear_val, self._status.get('gear_percent'))
            self._status['landing_lights'] = bool(landing_lights) if landing_lights is not None else self._status.get('landing_lights')
            self._status['nav_lights'] = bool(nav_lights) if nav_lights is not None else self._status.get('nav_lights')
            self._status['beacon_lights'] = bool(beacon_lights) if beacon_lights is not None else self._status.get('beacon_lights')
            self._status['strobe_lights'] = bool(strobe_lights) if strobe_lights is not None else self._status.get('strobe_lights')
            self._status['taxi_lights'] = bool(taxi_lights) if taxi_lights is not None else self._status.get('taxi_lights')
            self._status['recognition_lights'] = bool(recognition_lights) if recognition_lights is not None else self._status.get('recognition_lights')
            eng_count_val = int(round(_safe_float(engine_count))) if _safe_float(engine_count) is not None else None
            raw_throttles = [_safe_float(throttle1), _safe_float(throttle2), _safe_float(throttle3), _safe_float(throttle4)]
            throttle_scaled = []
            for tv in raw_throttles:
                if tv is None:
                    throttle_scaled.append(None)
                else:
                    throttle_scaled.append(tv * 100.0 if tv <= 1.01 else tv)
            if eng_count_val is None or eng_count_val <= 0:
                detected = [v for v in throttle_scaled if v is not None and abs(v) > 0.5]
                eng_count_val = len(detected) if detected else max(1, len([v for v in throttle_scaled if v is not None])) if any(v is not None for v in throttle_scaled) else None
            self._status['engine_count'] = _choose_value(eng_count_val, self._status.get('engine_count'))
            retract_val = retractable_gear
            if retract_val is not None:
                try:
                    retract_val = bool(int(float(retract_val)))
                except Exception:
                    retract_val = bool(retract_val)
            self._status['has_retractable_gear'] = _choose_value(retract_val, self._status.get('has_retractable_gear'))
            self._status['throttle_percent_engine1'] = _choose_value(throttle_scaled[0], self._status.get('throttle_percent_engine1'))
            self._status['throttle_percent_engine2'] = _choose_value(throttle_scaled[1], self._status.get('throttle_percent_engine2'))
            self._status['throttle_percent_engine3'] = _choose_value(throttle_scaled[2], self._status.get('throttle_percent_engine3'))
            self._status['throttle_percent_engine4'] = _choose_value(throttle_scaled[3], self._status.get('throttle_percent_engine4'))
            active_slots = max(0, min(4, int(self._status.get('engine_count') or 0)))
            throttle_vals = [max(0.0, min(100.0, float(v))) for v in [self._status.get('throttle_percent_engine1'), self._status.get('throttle_percent_engine2'), self._status.get('throttle_percent_engine3'), self._status.get('throttle_percent_engine4')][:active_slots or 4] if v is not None]
            self._status['throttle_percent_total'] = (sum(throttle_vals) / len(throttle_vals)) if throttle_vals else self._status.get('throttle_percent_total')
            self._status['sim_time_utc'] = _format_sim_time(zulu_hours)
            self._status['sim_time_local'] = _format_sim_time(local_hours)
            speed_for_range = _safe_float(self._status.get('ground_speed_kt')) or _safe_float(self._status.get('true_airspeed_kt')) or _safe_float(self._status.get('indicated_airspeed_kt'))
            if self._status['fuel_flow_gph'] and speed_for_range and self._status.get('fuel_total_gal') is not None:
                ff = self._status['fuel_flow_gph']
                gs = speed_for_range
                fuel_remaining = _safe_float(self._status.get('fuel_total_gal'))
                endurance = max(0.0, fuel_remaining / ff) if ff > 0 and fuel_remaining is not None else None
                self._status['endurance_hours'] = endurance
                calc_range = max(0.0, endurance * gs) if endurance is not None and gs is not None else None
                self._status['range_remaining_nm'] = _choose_value(calc_range, self._status.get('range_remaining_nm'))
            else:
                self._status['endurance_hours'] = _choose_value(None, self._status.get('endurance_hours'))
                self._status['range_remaining_nm'] = _choose_value(None, self._status.get('range_remaining_nm'))
            trail = list(self._status.get('trail') or [])
            if self._status['lat'] is not None and self._status['lon'] is not None:
                pt = {'lat': self._status['lat'], 'lon': self._status['lon'], 'ts': self._status['last_update']}
                airborne = (self._status.get('on_ground') is False) and ((self._status.get('altitude_agl_ft') or 0) > 80 or (self._status.get('ground_speed_kt') or 0) > 70)
                last = trail[-1] if trail else None
                if airborne:
                    if not last or abs(last['lat'] - pt['lat']) > 0.00001 or abs(last['lon'] - pt['lon']) > 0.00001:
                        trail.append(pt)
                        if len(trail) > 500:
                            trail = trail[-500:]
                    if not self._session_track or abs(self._session_track[-1]['lat'] - pt['lat']) > 0.00002 or abs(self._session_track[-1]['lon'] - pt['lon']) > 0.00002:
                        self._session_track.append({'lat': pt['lat'], 'lon': pt['lon'], 'ts': pt['ts'], 'altitude_ft': self._status.get('altitude_ft'), 'ground_speed_kt': self._status.get('ground_speed_kt'), 'heading_deg': self._status.get('heading_deg')})
                        if len(self._session_track) > 2000:
                            self._session_track = self._session_track[-2000:]
                self._status['trail'] = trail

            stats = dict(self._status.get('stats') or {})
            stats['samples'] = int(stats.get('samples') or 0) + 1
            stats['elapsed_seconds'] = max(0, int(time.monotonic() - self._started_monotonic))
            if self._status['altitude_ft'] is not None:
                cur = float(self._status['altitude_ft'])
                prior = stats.get('max_altitude_ft')
                stats['max_altitude_ft'] = cur if prior is None else max(float(prior), cur)
            if self._status['ground_speed_kt'] is not None:
                cur = float(self._status['ground_speed_kt'])
                prior = stats.get('max_ground_speed_kt')
                stats['max_ground_speed_kt'] = cur if prior is None else max(float(prior), cur)
            self._status['stats'] = stats
            self._status['session_state'] = _derive_session_state(self._status)
            if self._poll_counter == 1 or self._poll_counter % 5 == 0:
                _simlog('info', 'Poll %s: title=%s lat=%s lon=%s alt_ft=%s ias=%s gs=%s hdg=%s track=%s vs=%s on_ground=%s trail_pts=%s', self._poll_counter, _safe_repr(self._status['aircraft_title']), _safe_repr(self._status['lat']), _safe_repr(self._status['lon']), _safe_repr(self._status['altitude_ft']), _safe_repr(self._status['indicated_airspeed_kt']), _safe_repr(self._status['ground_speed_kt']), _safe_repr(self._status['heading_deg']), _safe_repr(self._status['track_deg']), _safe_repr(self._status['vertical_speed_fpm']), _safe_repr(self._status['on_ground']), len(self._status.get('trail') or []))


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None




def _choose_value(value, previous):
    return previous if value is None else value


def _best_heading(value, previous=None):
    if value is None:
        return previous
    try:
        v=float(value) % 360.0
        if previous is not None and abs(v) < 0.001 and abs(float(previous)) > 0.001:
            return float(previous)
        return v
    except Exception:
        return previous

def _format_sim_time(value):
    try:
        if value is None:
            return ''
        total=int(float(value)) % 86400
        h=total//3600
        m=(total%3600)//60
        s=total%60
        return f'{h:02d}:{m:02d}:{s:02d}'
    except Exception:
        return ''



def _safe_text(value):
    try:
        if value is None:
            return ''
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8', 'ignore').strip("\x00 ")
            except Exception:
                return repr(value)
        text = str(value)
        if text.startswith("b'") or text.startswith('b\"'):
            try:
                import ast
                raw = ast.literal_eval(text)
                if isinstance(raw, (bytes, bytearray)):
                    return bytes(raw).decode('utf-8', 'ignore').strip("\x00 ")
            except Exception:
                pass
        return text.strip("\x00 ")
    except Exception:
        return ''

def _angle_to_degrees(value):
    if value is None:
        return None
    try:
        v = float(value)
        if abs(v) <= (6.5):
            return v * 180.0 / 3.141592653589793
        return v
    except Exception:
        return None

def _normalize_heading(value):
    if value is None:
        return None
    try:
        out = float(value) % 360.0
        return out + 360.0 if out < 0 else out
    except Exception:
        return None


def _derive_session_state(status: dict[str, Any]) -> str:
    try:
        on_ground = status.get('on_ground')
        gs = float(status.get('ground_speed_kt') or 0)
        agl = float(status.get('altitude_agl_ft') or 0)
        vs = float(status.get('vertical_speed_fpm') or 0)
        throttle = float(status.get('throttle_percent_total') or 0)
        engine_count = int(status.get('engine_count') or 0)
        prev = str(status.get('session_state') or '').lower()
        if on_ground is None and gs <= 1 and agl <= 5:
            return 'idle'
        if on_ground:
            landing_lights = bool(status.get('landing_lights'))
            taxi_lights = bool(status.get('taxi_lights'))
            beacon = bool(status.get('beacon_lights'))
            if gs < 1.5:
                if throttle >= 8 or landing_lights:
                    return 'takeoff'
                if engine_count > 0 or beacon or taxi_lights:
                    return 'preflight'
                return 'parked/ended'
            if gs < 45:
                return 'taxi'
            return 'takeoff'
        # airborne states
        if agl < 150 and vs < -300 and gs > 50:
            return 'landing'
        if prev in ('takeoff', 'taxi', 'preflight') and agl < 250 and vs > 200 and gs > 50:
            return 'takeoff'
        if agl < 120 and vs > 500 and gs > 60:
            return 'takeoff'
        return 'airborne'
    except Exception:
        return 'idle'
    return 'idle'
