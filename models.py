from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
import uuid

CONTENT_TYPE_MAP = {
    "AIRCRAFT": "Aircraft",
    "SIMOBJECT": "Aircraft",
    "SCENERY": "Scenery",
    "NAVIGATION_DATA": "Utility",
    "LIVERY": "Mod",
    "MISSION": "Utility",
    "UNKNOWN": "Mod",
}

SUBTYPE_MAP = {
    "Airliner": ["a320","a380","a220","b737","b747","b777","b787","a330","a350","a340","crj","e175","e190","q400","atr"],
    "General Aviation": ["cessna","172","182","piper","cirrus","sr22","diamond","da62","da42","tbm","king air","bonanza","comanche"],
    "Business Jet": ["citation","longitude","phenom","global","challenger","gulfstream","learjet","falcon","honda jet"],
    "Helicopter": ["h145","h135","ec135","bell","aw109","robinson","r44","r22","uh60","chinook","cabri"],
    "Military": ["f-16","f/a-18","f-22","f-35","a-10","spitfire","hurricane","p-51","bf109","t-45","hawk"],
}

DOC_EXTENSIONS = {".pdf", ".txt", ".md", ".rtf", ".doc", ".docx", ".html", ".htm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

@dataclass
class Runway:
    id: str = ""
    len: str = ""
    ils: str = "none"

@dataclass
class RealWorld:
    icao: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    municipality: Optional[str] = None
    state: Optional[str] = None
    province: Optional[str] = None
    region: Optional[str] = None
    region_code: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    continent: Optional[str] = None
    elev: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    scheduled: Optional[str] = None
    airport_type: Optional[str] = None
    home_link: Optional[str] = None
    wiki_url: Optional[str] = None
    runways: List[Runway] = field(default_factory=list)
    mfr: Optional[str] = None
    manufacturer_full_name: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    engine: Optional[str] = None
    engine_type: Optional[str] = None
    max_speed: Optional[str] = None
    cruise: Optional[str] = None
    range: Optional[str] = None
    range_nm: Optional[int] = None
    ceiling: Optional[str] = None
    seats: Optional[str] = None
    mtow: Optional[str] = None
    fuel_capacity: Optional[str] = None
    wingspan: Optional[str] = None
    length: Optional[str] = None
    height: Optional[str] = None
    avionics: Optional[str] = None
    variants: Optional[str] = None
    in_production: Optional[str] = None
    aircraft_cost: Optional[str] = None
    country_of_origin: Optional[str] = None
    introduced: Optional[str] = None
    first_opened: Optional[str] = None
    scenery_type: Optional[str] = None
    coverage: Optional[str] = None
    resolution: Optional[str] = None
    util_cat: Optional[str] = None
    compat: Optional[str] = None
    source: Optional[str] = None
    passenger_count: Optional[str] = None
    cargo_count: Optional[str] = None
    us_rank: Optional[str] = None
    world_rank: Optional[str] = None
    hub_airlines: Optional[str] = None

@dataclass
class ProductInfo:
    ver: Optional[str] = None
    latest_ver: Optional[str] = None
    latest_ver_date: Optional[str] = None
    released: Optional[str] = None
    price: Optional[float] = None
    source_store: Optional[str] = None
    size_mb: Optional[float] = None
    package_name: Optional[str] = None
    manufacturer: Optional[str] = None

@dataclass
class UserData:
    fav: bool = False
    rating: int = 0
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    paid: float = 0.0
    source_store: str = ""
    avionics: str = ""
    features: str = ""
    resources: List[Dict] = field(default_factory=list)
    research_resources: List[Dict] = field(default_factory=list)
    data_resources: List[Dict] = field(default_factory=list)
    map_lat: Optional[float] = None
    map_lon: Optional[float] = None
    map_zoom: Optional[int] = None
    map_search_label: str = ""
    map_polygon: List[Dict] = field(default_factory=list)

@dataclass
class Document:
    name: str = ""
    path: str = ""
    url: str = ""
    pages: Optional[int] = None

@dataclass
class Addon:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    type: str = "Mod"
    sub: Optional[str] = None
    title: str = ""
    publisher: str = ""
    summary: str = ""
    entry_kind: str = "addon"
    managed: bool = True
    addon_path: str = ""
    launch_path: Optional[str] = None
    working_dir: Optional[str] = None
    launch_args: Optional[str] = None
    package_name: Optional[str] = None
    manifest_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    gallery_paths: List[str] = field(default_factory=list)
    enabled: bool = False
    has_update: bool = False
    last_scanned: Optional[str] = None
    exists: bool = True
    lat: Optional[float] = None
    lon: Optional[float] = None
    rw: RealWorld = field(default_factory=RealWorld)
    pr: ProductInfo = field(default_factory=ProductInfo)
    usr: UserData = field(default_factory=UserData)
    docs: List[Document] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Addon":
        d = dict(data)
        if isinstance(d.get("rw"), dict):
            rw = d["rw"]
            rw["runways"] = [Runway(**r) for r in (rw.get("runways") or []) if isinstance(r, dict)]
            d["rw"] = RealWorld(**{k: v for k, v in rw.items() if k in RealWorld.__dataclass_fields__})
        if isinstance(d.get("pr"), dict):
            d["pr"] = ProductInfo(**{k: v for k, v in d["pr"].items() if k in ProductInfo.__dataclass_fields__})
        if isinstance(d.get("usr"), dict):
            d["usr"] = UserData(**{k: v for k, v in d["usr"].items() if k in UserData.__dataclass_fields__})
        if isinstance(d.get("docs"), list):
            d["docs"] = [Document(**doc) for doc in d["docs"] if isinstance(doc, dict)]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_frontend_dict(self) -> dict:
        rw = self.rw
        pr = self.pr
        usr = self.usr
        return {
            "id": self.id,
            "type": self.type,
            "sub": self.sub,
            "title": self.title,
            "publisher": self.publisher,
            "summary": self.summary,
            "entry_kind": self.entry_kind,
            "managed": self.managed,
            "enabled": self.enabled,
            "hasUpdate": self.has_update,
            "lat": self.lat,
            "lon": self.lon,
            "addon_path": self.addon_path,
            "launch_path": self.launch_path,
            "working_dir": self.working_dir,
            "launch_args": self.launch_args,
            "package_name": self.package_name,
            "manifest_path": self.manifest_path,
            "thumbnail_path": self.thumbnail_path,
            "gallery_paths": self.gallery_paths,
            "rw": {
                "icao": rw.icao, "name": rw.name, "city": rw.city, "municipality": rw.municipality, "state": rw.state,
                "province": rw.province, "region": rw.region, "region_code": rw.region_code, "country": rw.country, "country_code": rw.country_code,
                "continent": rw.continent, "elev": rw.elev, "lat": rw.lat, "lon": rw.lon, "scheduled": rw.scheduled, "airport_type": rw.airport_type,
                "home_link": rw.home_link, "wiki_url": rw.wiki_url,
                "runways": [{"id": r.id, "len": r.len, "ils": r.ils} for r in rw.runways],
                "mfr": rw.mfr, "manufacturer_full_name": rw.manufacturer_full_name, "model": rw.model, "category": rw.category, "engine": rw.engine,
                "engine_type": rw.engine_type, "max_speed": rw.max_speed, "cruise": rw.cruise,
                "range": rw.range, "range_nm": rw.range_nm, "ceiling": rw.ceiling,
                "seats": rw.seats, "mtow": rw.mtow, "fuel_capacity": rw.fuel_capacity, "wingspan": rw.wingspan,
                "length": rw.length, "height": rw.height, "avionics": rw.avionics, "variants": rw.variants, "in_production": rw.in_production, "aircraft_cost": rw.aircraft_cost, "country_of_origin": rw.country_of_origin, "introduced": rw.introduced, "first_opened": rw.first_opened,
                "scenery_type": rw.scenery_type, "coverage": rw.coverage,
                "resolution": rw.resolution, "util_cat": rw.util_cat,
                "compat": rw.compat, "source": rw.source,
                "passenger_count": rw.passenger_count, "cargo_count": rw.cargo_count,
                "us_rank": rw.us_rank, "world_rank": rw.world_rank, "hub_airlines": rw.hub_airlines,
            },
            "pr": {
                "ver": pr.ver, "latest_ver": pr.latest_ver, "latest_ver_date": pr.latest_ver_date, "released": pr.released, "price": pr.price,
                "source_store": pr.source_store, "size_mb": pr.size_mb,
                "package_name": pr.package_name, "manufacturer": pr.manufacturer,
            },
            "usr": {
                "fav": usr.fav, "rating": usr.rating, "notes": usr.notes,
                "tags": usr.tags, "paid": usr.paid, "source_store": usr.source_store,
                "avionics": usr.avionics, "features": usr.features, "resources": usr.resources,
                "research_resources": usr.research_resources, "data_resources": usr.data_resources,
                "map_lat": usr.map_lat, "map_lon": usr.map_lon, "map_zoom": usr.map_zoom,
                "map_search_label": usr.map_search_label, "map_polygon": usr.map_polygon,
            },
            "docs": [
                {"name": d.name, "path": d.path, "url": d.url, "pages": d.pages}
                for d in self.docs
            ],
        }
