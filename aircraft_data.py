"""
MSFS Hangar — Aircraft Data via Wikipedia API
===============================================
Fetches real-world aircraft specifications from Wikipedia's free API.
No API key required. Public domain data.

Strategy:
  1. Search Wikipedia for "<manufacturer> <model>" 
  2. Parse the aircraft infobox for specs
  3. Cache results in data/aircraft_cache.json

Usage:
    from aircraft_data import fetch_aircraft_specs
    specs = fetch_aircraft_specs("Beechcraft", "Baron 58")
    # Returns dict with cruise, range, ceiling, seats, etc.

Standalone test:
    python aircraft_data.py "Beechcraft" "Baron 58"
    python aircraft_data.py "Airbus" "A320"
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from paths import USER_DATA_DIR
from typing import Optional

from bs4 import BeautifulSoup

from logger import get_logger

log = get_logger(__name__)

DATA_DIR    = USER_DATA_DIR / "cache"
CACHE_FILE  = DATA_DIR / "aircraft_cache.json"
CACHE_TTL   = 86400 * 30   # 30 days

# Wikipedia API endpoint
WIKI_API = "https://en.wikipedia.org/w/api.php"

# ── Cache ──────────────────────────────────────────────────────────────────

_mem_cache: dict[str, dict] = {}   # in-memory cache for session


def _load_cache() -> dict:
    global _mem_cache
    if _mem_cache:
        return _mem_cache
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            now  = time.time()
            # Drop expired entries
            _mem_cache = {k: v for k, v in data.items()
                          if now - v.get("_cached_at", 0) < CACHE_TTL}
            return _mem_cache
    except Exception as e:
        log.debug("Cache load error: %s", e)
    return {}


def _save_cache(cache: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        log.debug("Cache save error: %s", e)


def _cache_key(mfr: str, model: str) -> str:
    return f"{mfr.strip().lower()}|{model.strip().lower()}"


# ── Wikipedia API helpers ──────────────────────────────────────────────────

def _wiki_request(params: dict) -> dict:
    """Make a Wikipedia API request and return the JSON response."""
    params["format"] = "json"
    params["origin"] = "*"
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MSFS-Hangar/1.0 (aircraft data lookup)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning("Wikipedia API error: %s", e)
        return {}


def _search_wikipedia(query: str) -> Optional[str]:
    """
    Search Wikipedia and return the title of the most likely aircraft article.
    Tries to avoid disambiguation pages.
    """
    data = _wiki_request({
        "action":   "opensearch",
        "search":   query,
        "limit":    5,
        "namespace": 0,
    })
    if not data or len(data) < 2:
        return None

    titles = data[1] if len(data) > 1 else []
    if not titles:
        return None

    # Prefer articles that don't contain 'disambiguation'
    for title in titles:
        if "disambiguation" not in title.lower():
            return title
    return titles[0] if titles else None


def _get_page_wikitext(title: str) -> str:
    """Fetch raw wikitext for a Wikipedia article."""
    data = _wiki_request({
        "action":  "query",
        "titles":  title,
        "prop":    "revisions",
        "rvprop":  "content",
        "rvslots": "main",
    })
    try:
        pages = data.get("query", {}).get("pages", {})
        page  = next(iter(pages.values()))
        return page["revisions"][0]["slots"]["main"]["*"]
    except Exception:
        return ""


def _get_page_extract(title: str) -> str:
    """Fetch a plain-text extract (summary) from Wikipedia."""
    data = _wiki_request({
        "action":   "query",
        "titles":   title,
        "prop":     "extracts",
        "exintro":  True,
        "explaintext": True,
        "exsentences": 4,
    })
    try:
        pages = data.get("query", {}).get("pages", {})
        page  = next(iter(pages.values()))
        return page.get("extract", "")
    except Exception:
        return ""


def _get_page_html(title: str) -> str:
    data = _wiki_request({
        "action": "parse",
        "page": title,
        "prop": "text",
        "redirects": True,
    })
    try:
        return data.get('parse', {}).get('text', {}).get('*', '')
    except Exception:
        return ''


# ── Infobox parsing ────────────────────────────────────────────────────────

def _parse_infobox(wikitext: str) -> dict[str, str]:
    """
    Extract key-value pairs from a Wikipedia aircraft infobox.
    Handles {{convert|...}} templates and wiki markup.
    """
    specs: dict[str, str] = {}

    # Find the infobox block
    m = re.search(r'\{\{[Ii]nfobox [Aa]ircraft.*', wikitext, re.DOTALL)
    if not m:
        return specs

    infobox = m.group(0)
    # Walk line by line extracting | key = value pairs
    for line in infobox.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if "=" not in line:
            continue
        key, _, val = line[1:].partition("=")
        key = key.strip().lower().replace(" ", "_")
        val = _clean_wiki_value(val.strip())
        if key and val:
            specs[key] = val

    return specs


def _clean_wiki_value(val: str) -> str:
    """Strip wiki markup, convert templates to readable text."""
    if not val:
        return ""

    # Handle {{convert|value|unit|...}} → "value unit"
    def convert_template(m):
        parts = [p.strip() for p in m.group(1).split("|")]
        if len(parts) >= 2:
            num  = parts[0]
            unit = parts[1]
            # Map common units
            unit_map = {
                "km/h": "km/h", "mph": "mph", "kn": "kts", "knots": "kts",
                "km":   "km",   "mi":  "mi",  "nmi": "nm",
                "m":    "m",    "ft":  "ft",   "lb": "lb",  "kg": "kg",
                "kN":   "kN",   "lbf": "lbf",
            }
            unit_label = unit_map.get(unit, unit)
            # Get the alt value if present (e.g. convert shows both)
            return f"{num} {unit_label}"
        return parts[0] if parts else ""

    val = re.sub(r'\{\{[Cc]onvert\|([^}]+)\}\}', convert_template, val)

    # {{val|value|unit}} → "value unit"
    val = re.sub(r'\{\{val\|([^}|]+)(?:\|([^}]+))?\}\}',
                 lambda m: (m.group(1) + (" " + m.group(2) if m.group(2) else "")),
                 val)

    # [[link|text]] → text,  [[link]] → link
    val = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', val)

    # {{plainlist|...}} → first item
    val = re.sub(r'\{\{[Pp]lainlist\|(.+?)\}\}', lambda m: m.group(1).split("*")[1].strip() if "*" in m.group(1) else m.group(1), val)

    # Remove remaining {{ }} templates
    val = re.sub(r'\{\{[^}]+\}\}', '', val)

    # Remove HTML tags
    val = re.sub(r'<[^>]+>', '', val)

    # Remove ref tags
    val = re.sub(r'<ref[^>]*>.*?</ref>', '', val, flags=re.DOTALL)

    # Clean up whitespace and punctuation
    val = re.sub(r'\s+', ' ', val).strip()
    val = val.strip(',').strip()

    # Truncate very long values
    if len(val) > 80:
        val = val[:77] + "..."

    return val


def _parse_html_infobox(html: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    if not html:
        return specs
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('table.infobox')
    if not box:
        return specs
    for row in box.select('tr'):
        th = row.find('th')
        td = row.find('td')
        if not th or not td:
            continue
        key = re.sub(r'\s+', ' ', th.get_text(' ', strip=True)).lower().replace(' ', '_')
        val = re.sub(r'\s+', ' ', td.get_text(' ', strip=True))
        val = val.strip().strip(',')
        if key and val:
            specs[key] = val
    return specs


# ── Field mapping ──────────────────────────────────────────────────────────

# Wikipedia infobox field names → our RealWorld field names
_FIELD_MAP = {
    # Manufacturer / model
    "manufacturer":         "mfr",
    "name":                 "model",
    "type":                 None,   # skip — too vague

    # Performance
    "max_speed":            "max_speed",
    "maximum_speed":        "max_speed",
    "cruise_speed":         "cruise",
    "cruising_speed":       "cruise",
    "range":                "range",
    "range_km":             "range",
    "ceiling":              "ceiling",
    "service_ceiling":      "ceiling",

    # Physical
    "max_weight":           "mtow",
    "max_takeoff_weight":   "mtow",
    "gross_weight":         "mtow",
    "capacity":             "seats",
    "number_of_passengers": "seats",
    "passengers":           "seats",
    "crew":                 None,

    # Engine
    "number_of_engines":    None,       # handle separately
    "powerplant":           "engine",
    "engines":              "engine",
    "engine":               "engine",
    "engine_type":          "engine_type",
    "avionics":             "avionics",

    # History
    "first_flight":         "first_flight",
    "introduction":         "introduced",
    "introduced":           "introduced",
    "first_flight":         "first_flight",
    "number_built":         "units_built",

    # Dimensions
    "wingspan":             "wingspan",
    "length":               "length_ft",
}


def _range_to_nm(value: str) -> tuple[str, Optional[int]]:
    if not value:
        return value, None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(nm|nmi|nautical miles|mi|miles|km)", value.lower())
    if not m:
        return value, None
    num = float(m.group(1).replace(",", ""))
    unit = m.group(2)
    if unit in {"nm", "nmi", "nautical miles"}:
        nm = num
    elif unit in {"mi", "miles"}:
        nm = num * 0.868976
    else:
        nm = num * 0.539957
    nm_int = int(round(nm))
    return f"{nm_int} nm", nm_int

def _map_specs(raw: dict[str, str]) -> dict[str, str]:
    """Convert raw infobox keys to our field names."""
    result: dict[str, str] = {}
    for wiki_key, our_key in _FIELD_MAP.items():
        if our_key and wiki_key in raw:
            val = raw[wiki_key]
            if val and our_key not in result:   # don't overwrite better field
                result[our_key] = val

    rng = result.get("range", "")
    if rng:
        pretty, nm = _range_to_nm(rng)
        if pretty:
            result["range"] = pretty
        if nm is not None:
            result["range_nm"] = nm

    # Engine type heuristic
    engine_text = result.get("engine", "") + " " + raw.get("engine_type","")
    engine_lower = engine_text.lower()
    if "turbofan" in engine_lower:
        result.setdefault("engine_type", "Turbofan")
    elif "turboprop" in engine_lower:
        result.setdefault("engine_type", "Turboprop")
    elif "turbojet" in engine_lower:
        result.setdefault("engine_type", "Turbojet")
    elif "piston" in engine_lower or "reciprocating" in engine_lower:
        result.setdefault("engine_type", "Piston")
    elif "electric" in engine_lower:
        result.setdefault("engine_type", "Electric")

    return result


# ── Public API ─────────────────────────────────────────────────────────────

def fetch_aircraft_specs(
    manufacturer: str,
    model: str,
    force_refresh: bool = False,
) -> dict:
    """
    Fetch real-world specs for an aircraft from Wikipedia.
    Results are cached for 30 days.

    Returns a dict with keys matching RealWorld fields:
        mfr, model, engine, engine_type, cruise, range, ceiling,
        seats, mtow, first_flight, introduced, units_built,
        wingspan, length_ft, wiki_title, wiki_summary, wiki_url

    Returns empty dict if nothing found.
    """
    cache = _load_cache()
    key   = _cache_key(manufacturer, model)

    if not force_refresh and key in cache:
        log.debug("Aircraft cache hit: %s %s", manufacturer, model)
        result = dict(cache[key])
        result.pop("_cached_at", None)
        return result

    log.info("Fetching Wikipedia specs for: %s %s", manufacturer, model)

    # Build search queries from most to least specific
    queries = [
        f"{manufacturer} {model}",
        f"{model} aircraft",
        f"{manufacturer} {model.split()[0]}",   # just first word of model
    ]

    wiki_title = None
    for query in queries:
        wiki_title = _search_wikipedia(query)
        if wiki_title:
            log.debug("Wikipedia match: '%s' → '%s'", query, wiki_title)
            break

    if not wiki_title:
        log.info("No Wikipedia article found for %s %s", manufacturer, model)
        return {}

    # Get wikitext/html and extract
    wikitext = _get_page_wikitext(wiki_title)
    html     = _get_page_html(wiki_title)
    extract  = _get_page_extract(wiki_title)
    raw_wiki = _parse_infobox(wikitext)
    raw_html = _parse_html_infobox(html)
    raw = dict(raw_wiki)
    raw.update({k:v for k,v in raw_html.items() if v and (k not in raw or len(v) > len(str(raw.get(k,''))))})
    specs    = _map_specs(raw)

    # Add metadata
    wiki_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(wiki_title.replace(" ", "_"))
    specs["wiki_title"]   = wiki_title
    specs["wiki_url"]     = wiki_url
    specs["wiki_summary"] = extract[:500] if extract else ""
    specs["source"] = 'Wikipedia'

    # Default manufacturer/model from search if not in infobox
    specs.setdefault("mfr",   manufacturer)
    specs.setdefault("manufacturer_full_name", specs.get("mfr") or manufacturer)
    specs.setdefault("model", model)

    log.info("Got specs for %s %s: %s", manufacturer, model,
             {k: v for k, v in specs.items() if k not in ("wiki_summary",)})

    # Cache the result
    cached_entry = dict(specs)
    cached_entry["_cached_at"] = time.time()
    cache[key] = cached_entry
    _mem_cache[key] = cached_entry
    _save_cache(cache)

    return specs


def enrich_addon_aircraft(addon) -> bool:
    """
    Enrich an Aircraft addon's rw field with Wikipedia data.
    Uses addon.rw.mfr + addon.rw.model (or addon.publisher + addon.title).
    Returns True if enrichment succeeded.
    """
    rw  = addon.rw
    mfr   = rw.mfr   or addon.publisher or ""
    model = rw.model  or addon.title    or ""

    # Skip if both are empty or same (means manufacturer is just addon dev)
    if not mfr or not model:
        log.debug("Skip aircraft enrich — missing mfr/model for %s", addon.title)
        return False

    specs = fetch_aircraft_specs(mfr, model)
    if not specs:
        return False

    # Populate rw fields (don't overwrite if already set)
    def setif(field, value):
        if value and not getattr(rw, field, None):
            setattr(rw, field, value)

    setif("mfr",         specs.get("mfr"))
    setif("manufacturer_full_name", specs.get("manufacturer_full_name"))
    setif("model",       specs.get("model"))
    setif("engine",      specs.get("engine"))
    setif("engine_type", specs.get("engine_type"))
    setif("cruise",      specs.get("cruise"))
    setif("range",       specs.get("range"))
    setif("ceiling",     specs.get("ceiling"))
    setif("seats",       specs.get("seats"))
    setif("mtow",        specs.get("mtow"))

    # Always update wiki info
    rw.compat = specs.get("wiki_url", "")   # reuse compat field for wiki URL

    # Update summary if we got a good extract
    if specs.get("wiki_summary") and len(specs["wiki_summary"]) > 50:
        if not addon.summary or "addon by" in addon.summary:
            addon.summary = specs["wiki_summary"]

    return True


def get_cache_stats() -> dict:
    cache = _load_cache()
    return {
        "aircraft_cached": len(cache),
        "cache_file":      str(CACHE_FILE),
        "exists":          CACHE_FILE.exists(),
    }


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from logger import setup_logging
    setup_logging()

    if len(sys.argv) < 3:
        print("Usage: python aircraft_data.py <manufacturer> <model>")
        print("  e.g: python aircraft_data.py Beechcraft 'Baron 58'")
        print("  e.g: python aircraft_data.py Airbus A320")
        sys.exit(1)

    mfr   = sys.argv[1]
    model = " ".join(sys.argv[2:])

    print(f"\nLooking up: {mfr} {model}")
    specs = fetch_aircraft_specs(mfr, model, force_refresh=True)

    if not specs:
        print("No data found.")
    else:
        print(f"\nWikipedia article: {specs.get('wiki_title')} ({specs.get('wiki_url')})")
        print(f"\nSpecifications:")
        for k, v in specs.items():
            if k not in ("wiki_title","wiki_url","wiki_summary","_cached_at"):
                print(f"  {k:20s}: {v}")
        if specs.get("wiki_summary"):
            print(f"\nSummary:\n  {specs['wiki_summary'][:300]}")
