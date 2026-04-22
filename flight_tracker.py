from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlightTracker:
    poll_interval: float = 1.0
    connected: bool = False
    available: bool = False
    state: str = 'idle'
    last_error: str = 'SimConnect worker not bundled in this reconstructed baseline.'
    pause_state: str = 'running'
    route_points: list[dict[str, Any]] = field(default_factory=list)
    route_running: bool = False
    waypoint_index: int = 0
    control_mode: str = 'virtual-direct'

    def configure(self, poll_interval: float = 1.0, **_: Any) -> dict[str, Any]:
        self.poll_interval = float(poll_interval or 1.0)
        if self.state == 'idle':
            self.state = 'ready'
        return self.status()

    def _route_status(self) -> dict[str, Any]:
        return {
            'running': self.route_running,
            'control_mode': self.control_mode,
            'waypoint_index': self.waypoint_index,
            'total_waypoints': len(self.route_points),
            'points': self.route_points,
        }

    def status(self) -> dict[str, Any]:
        return {
            'available': self.available,
            'connected': self.connected,
            'state': self.state,
            'last_error': self.last_error,
            'status_message': self.last_error if not self.available else 'Ready.',
            'pause_state': self.pause_state,
            'route_controller': self._route_status(),
            'telemetry': {
                'lat': None,
                'lon': None,
                'altitude_ft': None,
                'speed_kt': None,
                'heading_deg': None,
                'on_ground': None,
            },
            'aircraft_title': '',
            'aircraft_icao': '',
            'session_state': 'paused' if self.pause_state == 'paused' else 'cruise',
        }

    def connect(self) -> dict[str, Any]:
        self.connected = False
        self.available = False
        self.state = 'unavailable'
        self.last_error = 'SimConnect integration is not active in this reconstructed 236 baseline.'
        return self.status()

    def disconnect(self) -> dict[str, Any]:
        self.connected = False
        self.state = 'ready'
        return self.status()

    def command(self, cmd: str) -> dict[str, Any]:
        c = str(cmd or '').strip().lower()
        if c == 'pause_on':
            self.pause_state = 'paused'
        elif c == 'pause_off':
            self.pause_state = 'running'
        return {'ok': True, 'command': c, 'status': self.status(), 'message': 'Command stored in baseline stub.'}

    def reposition(self, **kwargs: Any) -> dict[str, Any]:
        return {'ok': True, 'status': self.status(), 'request': kwargs, 'message': 'Reposition request accepted by baseline stub.'}

    def start_route_controller(self, points: list[dict] | None = None, altitude_ft: float | None = None, speed_kt: float | None = None, heading_deg: float | None = None, loop: bool = False, control_mode: str = 'virtual-direct', **_: Any) -> dict[str, Any]:
        self.route_points = list(points or [])
        self.route_running = True
        self.waypoint_index = 0
        self.control_mode = control_mode or 'virtual-direct'
        return {
            'ok': True,
            'status': self.status(),
            'route_controller': self._route_status(),
            'message': 'Route controller started in baseline stub.',
            'altitude_ft': altitude_ft,
            'speed_kt': speed_kt,
            'heading_deg': heading_deg,
            'loop': bool(loop),
        }

    def stop_route_controller(self) -> dict[str, Any]:
        self.route_running = False
        return {'ok': True, 'status': self.status(), 'route_controller': self._route_status(), 'message': 'Route controller stopped in baseline stub.'}

    def jump_to_route_waypoint(self, waypoint_index: int = 0) -> dict[str, Any]:
        total = len(self.route_points)
        if total:
            self.waypoint_index = max(0, min(int(waypoint_index or 0), total - 1))
        else:
            self.waypoint_index = 0
        return {'ok': True, 'status': self.status(), 'route_controller': self._route_status(), 'message': 'Waypoint jump stored in baseline stub.'}
