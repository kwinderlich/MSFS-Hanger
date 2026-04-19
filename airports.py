"""
MSFS Hangar — Airport Data from OurAirports
=============================================
Downloads and caches the free OurAirports dataset.
Provides lookup by ICAO code returning real-world airport info.

Data source: https://davidmegginson.github.io/ourairports-data/
License: Public Domain — no attribution required.
"""
from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from paths import USER_DATA_DIR
from typing import Optional
import urllib.request

from logger import get_logger

log = get_logger(__name__)

DATA_DIR     = USER_DATA_DIR / "cache"
AIRPORTS_CSV = DATA_DIR / "airports.csv"
RUNWAYS_CSV  = DATA_DIR / "runways.csv"

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL  = "https://davidmegginson.github.io/ourairports-data/runways.csv"

# In-memory cache after first load
_airports_cache: dict[str, dict] = {}
_airports_by_local_code: dict[str, str] = {}
_airports_by_gps_code: dict[str, str] = {}
_airports_by_iata_code: dict[str, str] = {}
_runways_cache:  dict[str, list] = {}   # icao → list of runway dicts
_cache_loaded = False


# ── Download ───────────────────────────────────────────────────────────────

def download_airports_data(force: bool = False) -> tuple[bool, str]:
    """
    Download airports.csv and runways.csv from OurAirports.
    Called automatically on first lookup if files are missing.
    Returns (success, message).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for url, path in [(AIRPORTS_URL, AIRPORTS_CSV), (RUNWAYS_URL, RUNWAYS_CSV)]:
        if path.exists() and not force:
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if age_days < 30:
                results.append(f"{path.name}: cached ({age_days:.0f}d old)")
                continue

        log.info("Downloading %s from %s", path.name, url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MSFS-Hangar/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            path.write_bytes(data)
            log.info("Downloaded %s: %d bytes", path.name, len(data))
            results.append(f"{path.name}: downloaded ({len(data)//1024} KB)")
        except Exception as e:
            log.error("Failed to download %s: %s", url, e)
            results.append(f"{path.name}: FAILED — {e}")
            return False, "; ".join(results)

    return True, "; ".join(results)


# ── Loading ────────────────────────────────────────────────────────────────

def _ensure_loaded():
    global _cache_loaded
    if _cache_loaded:
        return

    # Download if missing
    if not AIRPORTS_CSV.exists() or not RUNWAYS_CSV.exists():
        ok, msg = download_airports_data()
        if not ok:
            log.warning("Airport data unavailable: %s", msg)
            _cache_loaded = True
            return

    # Load airports
    try:
        with open(AIRPORTS_CSV, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                icao = (row.get("ident") or "").strip().upper()
                if icao and len(icao) >= 3:
                    local_code = (row.get("local_code") or "").strip().upper()
                    gps_code = (row.get("gps_code") or "").strip().upper()
                    iata_code = (row.get("iata_code") or "").strip().upper()
                    faa_id = local_code or (gps_code if gps_code and gps_code != icao else "")
                    _airports_cache[icao] = {
                        "icao":       icao,
                        "faa_id":     faa_id,
                        "local_code": local_code,
                        "gps_code":   gps_code,
                        "name":       row.get("name", ""),
                        "city":       row.get("municipality", ""),
                        "municipality": row.get("municipality", ""),
                        "country":    row.get("iso_country", ""),
                        "region":     row.get("iso_region", ""),
                        "continent":  row.get("continent", ""),
                        "scheduled":  row.get("scheduled_service", ""),
                        "lat":        _safe_float(row.get("latitude_deg")),
                        "lon":        _safe_float(row.get("longitude_deg")),
                        "elev":       row.get("elevation_ft", ""),
                        "type":       row.get("type", ""),
                        "iata":       iata_code,
                        "wiki":       row.get("wikipedia_link", ""),
                        "home_link":  row.get("home_link", ""),
                    }
                    for code, bucket in ((local_code, _airports_by_local_code), (gps_code, _airports_by_gps_code), (iata_code, _airports_by_iata_code)):
                        if code and code != icao and code not in bucket:
                            bucket[code] = icao
        log.info("Loaded %d airports from OurAirports", len(_airports_cache))
    except Exception as e:
        log.error("Error loading airports.csv: %s", e)

    # Load runways
    try:
        with open(RUNWAYS_CSV, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                icao = (row.get("airport_ident") or "").strip().upper()
                if not icao:
                    continue
                le_id  = row.get("le_ident", "")
                he_id  = row.get("he_ident", "")
                length = row.get("length_ft", "")
                width  = row.get("width_ft", "")
                surf   = row.get("surface", "")
                le_ils = row.get("le_ils_freq_mhz", "")
                he_ils = row.get("he_ils_freq_mhz", "")

                rwy_id = f"{le_id}/{he_id}" if le_id and he_id else (le_id or he_id or "?")
                ils    = le_ils or he_ils or ""

                len_str = f"{length} ft" if length else ""
                if width: len_str += f" × {width} ft"
                if surf:  len_str += f" ({surf})"

                rwy = {"id": rwy_id, "len": len_str, "ils": ils or "none"}
                _runways_cache.setdefault(icao, []).append(rwy)

        log.info("Loaded runways for %d airports", len(_runways_cache))
    except Exception as e:
        log.error("Error loading runways.csv: %s", e)

    _cache_loaded = True


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


# ── Country/region helpers ─────────────────────────────────────────────────

# OurAirports uses iso_region like "US-CA" or "GB-ENG"
_US_STATES = {
    "US-AL":"Alabama","US-AK":"Alaska","US-AZ":"Arizona","US-AR":"Arkansas",
    "US-CA":"California","US-CO":"Colorado","US-CT":"Connecticut","US-DE":"Delaware",
    "US-FL":"Florida","US-GA":"Georgia","US-HI":"Hawaii","US-ID":"Idaho",
    "US-IL":"Illinois","US-IN":"Indiana","US-IA":"Iowa","US-KS":"Kansas",
    "US-KY":"Kentucky","US-LA":"Louisiana","US-ME":"Maine","US-MD":"Maryland",
    "US-MA":"Massachusetts","US-MI":"Michigan","US-MN":"Minnesota","US-MS":"Mississippi",
    "US-MO":"Missouri","US-MT":"Montana","US-NE":"Nebraska","US-NV":"Nevada",
    "US-NH":"New Hampshire","US-NJ":"New Jersey","US-NM":"New Mexico","US-NY":"New York",
    "US-NC":"North Carolina","US-ND":"North Dakota","US-OH":"Ohio","US-OK":"Oklahoma",
    "US-OR":"Oregon","US-PA":"Pennsylvania","US-RI":"Rhode Island","US-SC":"South Carolina",
    "US-SD":"South Dakota","US-TN":"Tennessee","US-TX":"Texas","US-UT":"Utah",
    "US-VT":"Vermont","US-VA":"Virginia","US-WA":"Washington","US-WV":"West Virginia",
    "US-WI":"Wisconsin","US-WY":"Wyoming","US-DC":"D.C.",
}
_COUNTRIES = {
    "US":"United States","GB":"United Kingdom","CA":"Canada","AU":"Australia",
    "DE":"Germany","FR":"France","JP":"Japan","NL":"Netherlands","AE":"United Arab Emirates",
    "SG":"Singapore","NZ":"New Zealand","ES":"Spain","IT":"Italy","CH":"Switzerland",
    "NO":"Norway","SE":"Sweden","DK":"Denmark","FI":"Finland","AT":"Austria",
    "BE":"Belgium","PT":"Portugal","GR":"Greece","TR":"Turkey","PL":"Poland",
    "CZ":"Czech Republic","HU":"Hungary","RO":"Romania","SK":"Slovakia","HR":"Croatia",
    "CN":"China","KR":"South Korea","TW":"Taiwan","IN":"India","TH":"Thailand",
    "MY":"Malaysia","ID":"Indonesia","PH":"Philippines","VN":"Vietnam","HK":"Hong Kong",
    "BR":"Brazil","MX":"Mexico","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "ZA":"South Africa","EG":"Egypt","MA":"Morocco","KE":"Kenya","NG":"Nigeria",
    "OM":"Oman","QA":"Qatar","KW":"Kuwait","BH":"Bahrain","SA":"Saudi Arabia",
    "IL":"Israel","JO":"Jordan","LB":"Lebanon","TN":"Tunisia","DZ":"Algeria",
    "RU":"Russia","UA":"Ukraine","IS":"Iceland","IE":"Ireland","LU":"Luxembourg",
}


def _parse_location(airport: dict) -> dict:
    """Extract state/province/country from iso_country and iso_region."""
    iso_country = airport.get("country", "")
    iso_region  = airport.get("region", "")
    country     = _COUNTRIES.get(iso_country, iso_country)
    state       = _US_STATES.get(iso_region, "")
    province    = ""

    if not state and iso_region:
        # For non-US: "CA-ON" → "Ontario" (simplified)
        region_code = iso_region
        if iso_country == "CA":
            CA_PROVINCES = {
                "CA-AB":"Alberta","CA-BC":"British Columbia","CA-MB":"Manitoba",
                "CA-NB":"New Brunswick","CA-NL":"Newfoundland","CA-NS":"Nova Scotia",
                "CA-NT":"Northwest Territories","CA-NU":"Nunavut","CA-ON":"Ontario",
                "CA-PE":"Prince Edward Island","CA-QC":"Quebec","CA-SK":"Saskatchewan",
                "CA-YT":"Yukon",
            }
            province = CA_PROVINCES.get(region_code, "")

    return {"country": country, "state": state, "province": province, "region_name": state or province or iso_region}


# ── Public API ─────────────────────────────────────────────────────────────

def lookup_airport(icao: str) -> Optional[dict]:
    """
    Look up an airport by ICAO code.
    Returns a dict with real-world data, or None if not found.
    """
    _ensure_loaded()
    icao = icao.strip().upper()
    airport = _airports_cache.get(icao)
    if not airport:
        return None

    loc     = _parse_location(airport)
    runways = _runways_cache.get(icao, [])

    # Classify airport type using OurAirports type field
    type_map = {
        "large_airport":  "Large Commercial",
        "medium_airport": "Medium Commercial",
        "small_airport":  "General Aviation",
        "heliport":       "Heliport",
        "seaplane_base":  "Seaplane Base",
        "balloonport":    "Balloonport",
        "closed":         "Closed",
    }
    apt_type = type_map.get(airport.get("type", ""), airport.get("type", ""))

    elev = airport.get("elev")
    elev_str = f"{elev} ft" if elev else ""

    return {
        "icao":         icao,
        "faa_id":       airport.get("faa_id", "") or airport.get("local_code", "") or airport.get("gps_code", ""),
        "name":         airport.get("name", ""),
        "city":         airport.get("city", ""),
        "municipality": airport.get("municipality", ""),
        "country":      loc["country"],
        "state":        loc["state"],
        "province":     loc["province"],
        "region":       loc.get("region_name") or airport.get("region", ""),
        "lat":          airport.get("lat"),
        "lon":          airport.get("lon"),
        "elev":         elev_str,
        "iata":         airport.get("iata", ""),
        "airport_type": apt_type,
        "continent":    airport.get("continent", ""),
        "scheduled":    airport.get("scheduled", ""),
        "wiki_url":     airport.get("wiki", ""),
        "home_link":    airport.get("home_link", ""),
        "runways":      runways,
    }


def lookup_airports_batch(icaos: list[str]) -> dict[str, dict]:
    """Look up multiple ICAOs at once. Returns {icao: data}."""
    _ensure_loaded()
    return {icao: data for icao in icaos
            if (data := lookup_airport(icao)) is not None}


def get_cache_stats() -> dict:
    _ensure_loaded()
    return {
        "airports_loaded": len(_airports_cache),
        "runways_loaded":  len(_runways_cache),
        "airports_csv":    str(AIRPORTS_CSV),
        "exists":          AIRPORTS_CSV.exists(),
    }


def lookup_airport_by_code(code: str) -> Optional[dict]:
    """Look up an airport by ICAO, FAA/local code, GPS code, or IATA code."""
    _ensure_loaded()
    code = (code or '').strip().upper()
    if not code:
        return None
    airport = lookup_airport(code)
    if airport:
        return airport
    for bucket in (_airports_by_local_code, _airports_by_gps_code, _airports_by_iata_code):
        ident = bucket.get(code)
        if ident:
            airport = lookup_airport(ident)
            if airport:
                if not airport.get('faa_id') and code not in {airport.get('icao', ''), airport.get('iata', '')}:
                    airport['faa_id'] = code
                return airport
    return None


def lookup_airport_by_faa(faa_id: str) -> Optional[dict]:
    """Backwards-compatible FAA/local-code helper."""
    return lookup_airport_by_code(faa_id)


def search_airports(query: str = '', limit: int = 50) -> list[dict]:
    """Search cached airports by ICAO/IATA/local code, name, or municipality.
    Keeps results lightweight for UI pickers.
    """
    _ensure_loaded()
    q = (query or '').strip().upper()
    rows = []
    for ident, airport in _airports_cache.items():
        score = 0
        name = str(airport.get('name') or '')
        city = str(airport.get('municipality') or airport.get('city') or '')
        country = str(airport.get('country') or '')
        local_code = str(airport.get('local_code') or airport.get('faa_id') or '')
        iata = str(airport.get('iata') or '')
        apt_type = str(airport.get('type') or '')
        if q:
            hay = ' '.join([ident, local_code, iata, name, city, country]).upper()
            if ident == q:
                score = 1000
            elif local_code == q or iata == q:
                score = 950
            elif ident.startswith(q):
                score = 900
            elif name.upper().startswith(q):
                score = 820
            elif city.upper().startswith(q):
                score = 760
            elif q in hay:
                score = 600
            else:
                continue
        else:
            # Without a query, return common scheduled airports first.
            score = 200
            if airport.get('scheduled') == 'yes':
                score += 50
        if apt_type == 'large_airport':
            score += 40
        elif apt_type == 'medium_airport':
            score += 30
        elif apt_type == 'small_airport':
            score += 10
        rows.append((score, ident, {
            'icao': ident,
            'faa_id': local_code,
            'iata': iata,
            'name': name,
            'municipality': city,
            'country': _COUNTRIES.get(country, country),
            'region': _parse_location(airport).get('region_name') or airport.get('region', ''),
            'lat': airport.get('lat'),
            'lon': airport.get('lon'),
            'airport_type': apt_type,
            'scheduled': airport.get('scheduled', ''),
        }))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in rows[:max(1, min(int(limit or 50), 200))]]
