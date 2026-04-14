from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

@dataclass
class RunwaySegment:
    ident: str = ''
    length_ft: float | None = None
    width_ft: float | None = None
    surface: str = ''
    heading_deg: float | None = None
    threshold_lat: float | None = None
    threshold_lon: float | None = None

@dataclass
class TaxiPath:
    name: str = ''
    points: List[Dict[str, float]] = field(default_factory=list)
    surface: str = ''

@dataclass
class ParkingStand:
    name: str = ''
    type: str = ''
    lat: float | None = None
    lon: float | None = None
    heading_deg: float | None = None

@dataclass
class AirportOverlay:
    airport_id: str
    airport_code: str = ''
    source: str = 'msfs_facility_architecture_stub'
    runways: List[RunwaySegment] = field(default_factory=list)
    taxiways: List[TaxiPath] = field(default_factory=list)
    parking: List[ParkingStand] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def overlay_stub_for_airport(airport_id: str, airport_code: str = '') -> Dict[str, Any]:
    overlay = AirportOverlay(airport_id=airport_id, airport_code=airport_code)
    overlay.metadata = {
        'status': 'stub',
        'note': 'Architecture scaffold for future MSFS 2024 airport overlay rendering from facility/scenery data.',
        'supported_layers': ['runways', 'taxiways', 'parking'],
    }
    return overlay.to_dict()
