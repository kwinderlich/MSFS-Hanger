from __future__ import annotations

import csv
import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from logger import get_logger
from models import Addon, Runway
from paths import USER_DATA_DIR, BASE_DIR

log = get_logger(__name__)
CACHE_DIR = USER_DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BUNDLED_CACHE_DIR = BASE_DIR / "data" / "cache"

OURAIRPORTS_AIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OURAIRPORTS_RUNWAYS = "https://davidmegginson.github.io/ourairports-data/runways.csv"
OURAIRPORTS_COUNTRIES = "https://davidmegginson.github.io/ourairports-data/countries.csv"
OURAIRPORTS_REGIONS = "https://davidmegginson.github.io/ourairports-data/regions.csv"

_MEM: dict[str, dict] = {}
_LOAD_LOCK = threading.Lock()
_LOAD_FAILED_UNTIL = 0.0

_CONTINENTS = {
    "AF": "Africa", "AN": "Antarctica", "AS": "Asia", "EU": "Europe",
    "NA": "North America", "OC": "Oceania", "SA": "South America",
}

COMMON_AIRCRAFT = {
    "737": {"mfr": "Boeing", "introduced": "1968", "engine_type": "Turbofan", "seats": "189", "ceiling": "41,000 ft", "category": "Airliner"},
    "747": {"mfr": "Boeing", "introduced": "1970", "engine_type": "Turbofan", "seats": "416", "ceiling": "45,100 ft", "category": "Airliner"},
    "777": {"mfr": "Boeing", "introduced": "1995", "engine_type": "Turbofan", "seats": "396", "ceiling": "43,100 ft", "category": "Airliner"},
    "787": {"mfr": "Boeing", "introduced": "2011", "engine_type": "Turbofan", "seats": "242-335", "ceiling": "43,000 ft", "category": "Airliner"},
    "a320": {"mfr": "Airbus", "introduced": "1988", "engine_type": "Turbofan", "seats": "150-180", "ceiling": "39,000 ft", "category": "Airliner"},
    "a321": {"mfr": "Airbus", "introduced": "1994", "engine_type": "Turbofan", "seats": "185-236", "ceiling": "39,000 ft", "category": "Airliner"},
    "a330": {"mfr": "Airbus", "introduced": "1994", "engine_type": "Turbofan", "seats": "250-440", "ceiling": "41,100 ft", "category": "Airliner"},
    "a350": {"mfr": "Airbus", "introduced": "2015", "engine_type": "Turbofan", "seats": "300-410", "ceiling": "43,100 ft", "category": "Airliner"},
    "cessna 172": {"mfr": "Cessna", "introduced": "1956", "engine_type": "Piston", "seats": "4", "ceiling": "14,000 ft", "category": "General Aviation"},
    "bonanza": {"mfr": "Beechcraft", "introduced": "1947", "engine_type": "Piston", "seats": "6", "ceiling": "18,500 ft", "category": "General Aviation"},
    "king air": {"mfr": "Beechcraft", "introduced": "1964", "engine_type": "Turboprop", "seats": "6-11", "ceiling": "35,000 ft", "category": "General Aviation"},
    "tbm": {"mfr": "Daher", "introduced": "1990", "engine_type": "Turboprop", "seats": "6", "ceiling": "31,000 ft", "category": "General Aviation"},
}

class RealWorldError(Exception):
    pass


def _seed_cache_from_bundle(name: str, path: Path):
    if path.exists():
        return
    for src in [BUNDLED_CACHE_DIR / name, BASE_DIR / name, BASE_DIR.parent / name]:
        try:
            if src.exists() and src.stat().st_size > 0:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(src.read_bytes())
                return
        except Exception:
            continue


def _download_if_stale(url: str, path: Path, max_age_hours: int = 24 * 30):
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return
    resp = requests.get(url, timeout=25, headers={"User-Agent": "MSFS-Hangar/2.0"})
    resp.raise_for_status()
    path.write_bytes(resp.content)


def _safe_download_if_stale(url: str, path: Path, max_age_hours: int = 24 * 30):
    _seed_cache_from_bundle(path.name, path)
    try:
        _download_if_stale(url, path, max_age_hours=max_age_hours)
    except Exception as e:
        if not path.exists():
            raise
        log.warning("Using cached %s after refresh failed: %s", path.name, e)


def _load_csv_dict(path: Path, key: str):
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {row.get(key, ""): row for row in rows if row.get(key)}


def _load_csv_grouped(path: Path, key: str):
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        out.setdefault(row.get(key, ""), []).append(row)
    return out


def _ensure_data():
    global _LOAD_FAILED_UNTIL
    if _MEM:
        return
    if _LOAD_FAILED_UNTIL and time.time() < _LOAD_FAILED_UNTIL:
        raise RealWorldError("airport-data-temporarily-unavailable")
    with _LOAD_LOCK:
        if _MEM:
            return
        airport_path = CACHE_DIR / "ourairports_airports.csv"
        runway_path = CACHE_DIR / "ourairports_runways.csv"
        country_path = CACHE_DIR / "ourairports_countries.csv"
        region_path = CACHE_DIR / "ourairports_regions.csv"
        try:
            _safe_download_if_stale(OURAIRPORTS_AIRPORTS, airport_path)
            _safe_download_if_stale(OURAIRPORTS_RUNWAYS, runway_path)
            try:
                _safe_download_if_stale(OURAIRPORTS_COUNTRIES, country_path)
            except Exception:
                pass
            try:
                _safe_download_if_stale(OURAIRPORTS_REGIONS, region_path)
            except Exception:
                pass
            _MEM["airports"] = _load_csv_dict(airport_path, "ident")
            _MEM["runways"] = _load_csv_grouped(runway_path, "airport_ident")
            _MEM["countries"] = _load_csv_dict(country_path, "code") if country_path.exists() else {}
            _MEM["regions"] = _load_csv_dict(region_path, "code") if region_path.exists() else {}
            _LOAD_FAILED_UNTIL = 0.0
        except Exception as e:
            _LOAD_FAILED_UNTIL = time.time() + 300
            log.warning("Airport data preload failed: %s", e)
            raise RealWorldError(str(e))


def is_known_airport_code(code: Optional[str]) -> bool:
    if not code:
        return False
    ident = str(code).strip().upper()
    if len(ident) != 4 or not ident.isalpha():
        return False
    try:
        _ensure_data()
        return ident in _MEM.get("airports", {})
    except Exception:
        return False


def guess_icao(text: str, known_only: bool = False) -> Optional[str]:
    if not text:
        return None
    candidates = re.findall(r"\b([A-Z]{4})\b", text.upper())
    for cand in candidates:
        if cand in {"MSFS", "XBOX", "PACK", "BETA", "PLUS", "CITY", "TOWN", "ROAD"}:
            continue
        if known_only and not is_known_airport_code(cand):
            continue
        return cand
    return None


def _apply_airport(addon: Addon, ident: str):
    _ensure_data()
    airport = _MEM["airports"].get(ident)
    if not airport:
        return False
    countries = _MEM.get("countries", {})
    regions = _MEM.get("regions", {})
    region = regions.get(airport.get("iso_region", ""), {})
    country = countries.get(airport.get("iso_country", ""), {})
    runways = _MEM.get("runways", {}).get(ident, [])

    addon.lat = float(airport["latitude_deg"]) if airport.get("latitude_deg") else addon.lat
    addon.lon = float(airport["longitude_deg"]) if airport.get("longitude_deg") else addon.lon
    addon.rw.lat = addon.lat
    addon.rw.lon = addon.lon
    addon.rw.icao = ident
    addon.rw.name = airport.get("name") or addon.rw.name or addon.title
    addon.rw.city = airport.get("municipality") or addon.rw.city
    addon.rw.municipality = airport.get("municipality") or addon.rw.municipality
    addon.rw.country_code = airport.get("iso_country") or addon.rw.country_code
    addon.rw.country = country.get("name") or airport.get("iso_country") or addon.rw.country
    addon.rw.region_code = airport.get("iso_region") or addon.rw.region_code
    addon.rw.region = region.get("name") or airport.get("iso_region") or addon.rw.region
    if addon.rw.country == "United States":
        addon.rw.state = region.get("local_code") or region.get("name") or addon.rw.state
    elif addon.rw.country == "Canada":
        addon.rw.province = region.get("local_code") or region.get("name") or addon.rw.province
    addon.rw.continent = _CONTINENTS.get(airport.get("continent"), airport.get("continent")) or addon.rw.continent
    addon.rw.elev = f"{airport.get('elevation_ft')} ft" if airport.get("elevation_ft") else addon.rw.elev
    addon.rw.scheduled = airport.get("scheduled_service") or addon.rw.scheduled
    addon.rw.airport_type = airport.get("type") or addon.rw.airport_type
    addon.rw.wiki_url = airport.get("wikipedia_link") or addon.rw.wiki_url
    addon.rw.home_link = airport.get("home_link") or addon.rw.home_link
    addon.rw.runways = [
        Runway(
            id="/".join([p for p in [row.get("le_ident"), row.get("he_ident")] if p]) or "?",
            len=(f"{row.get('length_ft','')} ft" if row.get("length_ft") else "") + (f" × {row.get('width_ft')} ft" if row.get("width_ft") else "") + (f" ({row.get('surface')})" if row.get("surface") else ""),
            ils=(row.get("le_ils_freq_mhz") or row.get("he_ils_freq_mhz") or "none"),
        )
        for row in runways[:12]
    ]
    addon.rw.source = "OurAirports"
    if addon.type == "Scenery" and not addon.rw.scenery_type:
        addon.rw.scenery_type = "Airport scenery"
    return True


def _guess_aircraft_fields(addon: Addon):
    text = " ".join(filter(None, [addon.title, addon.package_name or "", addon.publisher or ""]))
    lower = text.lower()
    rw = addon.rw
    if not rw.mfr and addon.pr and addon.pr.manufacturer and addon.pr.manufacturer.lower() != (addon.publisher or "").lower():
        rw.mfr = addon.pr.manufacturer
    if not rw.manufacturer_full_name and rw.mfr:
        rw.manufacturer_full_name = rw.mfr
    if not rw.mfr:
        maker_candidates = ["Beechcraft", "Cessna", "Piper", "Cirrus", "Boeing", "Airbus", "Douglas", "ATR", "Bombardier", "Embraer", "Daher", "Diamond", "Bell", "Robinson", "Leonardo", "Sikorsky", "Dassault", "Gulfstream"]
        for cand in maker_candidates:
            if cand.lower() in lower:
                rw.mfr = cand
                rw.manufacturer_full_name = rw.manufacturer_full_name or cand
                break
    for key, data in COMMON_AIRCRAFT.items():
        if key in lower:
            rw.mfr = rw.mfr or data.get("mfr")
            rw.manufacturer_full_name = rw.manufacturer_full_name or rw.mfr
            rw.introduced = rw.introduced or data.get("introduced")
            rw.engine_type = rw.engine_type or data.get("engine_type")
            rw.seats = rw.seats or data.get("seats")
            rw.ceiling = rw.ceiling or data.get("ceiling")
            rw.category = rw.category or data.get("category")
            break
    if not rw.model:
        model = addon.title or addon.package_name or ""
        if rw.mfr and model.lower().startswith(rw.mfr.lower() + " "):
            model = model[len(rw.mfr):].strip()
        rw.model = model
    rw.source = rw.source or ("Manifest metadata + title parsing" if rw.mfr else "Title parsing only")


def enrich_addon(addon: Addon):
    try:
        text = " ".join(filter(None, [addon.title, addon.package_name or "", addon.addon_path]))
        ident = guess_icao(text, known_only=True)
        if addon.type in {"Airport", "Scenery"} and ident:
            _apply_airport(addon, ident)
        elif addon.type == "Aircraft":
            _guess_aircraft_fields(addon)
    except Exception as e:
        log.warning("Real-world enrichment failed for %s: %s", addon.title, e)


def fetch_aircraft_specs(query: str) -> dict:
    # legacy compatibility for existing app endpoint; use Wikipedia summary search
    q = (query or "").strip()
    if not q:
        return {}
    headers = {"User-Agent": "MSFS-Hangar/2.0 (aircraft lookup)"}
    try:
        search = requests.get("https://en.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 1}, timeout=20, headers=headers)
        search.raise_for_status()
        results = ((((search.json() or {}).get("query") or {}).get("search")) or [])
        if not results:
            return {}
        title = results[0].get("title")
        extract = requests.get("https://en.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts", "exintro": True, "explaintext": True, "titles": title, "format": "json"}, timeout=20, headers=headers)
        extract.raise_for_status()
        pages = (((extract.json() or {}).get("query") or {}).get("pages") or {})
        page = next(iter(pages.values())) if pages else {}
        return {"wiki_title": title, "summary": page.get("extract", "")[:500], "source": f"Wikipedia: {title}"}
    except Exception as e:
        log.warning("Legacy aircraft lookup failed for %s: %s", q, e)
        return {}
