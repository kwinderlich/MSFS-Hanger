from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from logger import get_logger
from models import Addon, Document, DOC_EXTENSIONS, IMAGE_EXTENSIONS, CONTENT_TYPE_MAP, SUBTYPE_MAP
from realworld import enrich_addon, guess_icao, is_known_airport_code
import linker

log = get_logger(__name__)

MANIFEST_NAME = "manifest.json"
DOC_DIR_HINTS = {"documentation", "docs", "manual", "manuals", "guide", "guides", "readme", "documentation files"}
IGNORE_DIR_NAMES = {"community", ".git", "__pycache__"}
AIRPORT_HINTS = {"airport", "intl", "international", "regional", "municipal", "airfield", "aerodrome", "heliport", "terminal", "afb", "air base"}
AIRCRAFT_FALSE_AIRPORT_HINTS = {"livery", "aircraft", "airplane", "boeing", "airbus", "cessna", "beechcraft", "piper", "cirrus", "embraer", "bombardier", "flight model"}
CONTAINER_NAMES = {"airports", "airport", "aircraft", "airplanes", "planes", "scenery", "utilities", "mods", "liveries", "misc", "vendors", "publisher"}


def _safe_read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return {}


def _iter_dirs(path: Path) -> list[Path]:
    try:
        return [p for p in sorted(path.iterdir(), key=lambda x: x.name.lower()) if p.is_dir() and not p.name.startswith('.') and p.name.lower() not in IGNORE_DIR_NAMES]
    except Exception:
        return []


def _discover_manifest_files(scan_root: Path) -> list[Path]:
    manifests = []
    try:
        for mf in scan_root.rglob(MANIFEST_NAME):
            if any(part.lower() in IGNORE_DIR_NAMES for part in mf.parts):
                continue
            manifests.append(mf)
    except Exception:
        return []
    uniq = sorted({str(p.resolve()): p for p in manifests}.values(), key=lambda p: str(p).lower())
    return uniq


def _addon_root_for_manifest(manifest_path: Path, container: Optional[Path] = None) -> Path:
    root = manifest_path.parent
    if root.name.lower() in {"package", "packages", "contentinfo"} and root.parent.exists():
        root = root.parent
    if container:
        try:
            rel = root.relative_to(container)
            parts = rel.parts
            if len(parts) >= 2 and parts[0].lower() in CONTAINER_NAMES:
                root = container / Path(*parts[1:])
        except Exception:
            pass
    return root


def _find_thumbnail(addon_dir: Path, manifest_dir: Optional[Path] = None) -> Optional[str]:
    exact_names = {"thumbnail.jpg", "thumbnail.jpeg", "thumbnail.png", "thumbnail.webp"}
    roots = [manifest_dir] if manifest_dir and manifest_dir != addon_dir else []
    roots.append(addon_dir)
    candidates = []
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            name = p.name.lower()
            full = str(p.resolve())
            lower_full = full.lower()
            score = 100
            if "contentinfo" in lower_full:
                score -= 70
            if name in exact_names:
                score -= 60
            if "thumbnail" in name:
                score -= 45
            if "texture" in lower_full or "simobjects" in lower_full:
                score -= 10
            if any(skip in name for skip in ["logo", "icon", "screenshot", "preview"]):
                score += 20
            candidates.append((score, len(full), full))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


def _find_gallery(addon_dir: Path, thumb: Optional[str]) -> list[str]:
    thumb_norm = str(Path(thumb).resolve()).lower() if thumb else ""
    results = []
    for p in addon_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        full = str(p.resolve())
        lower_full = full.lower()
        if "contentinfo" not in lower_full:
            continue
        name = p.name.lower()
        if any(skip in name for skip in ["logo", "icon"]):
            continue
        if thumb_norm and full.lower() == thumb_norm:
            continue
        results.append(full)
    results = sorted(dict.fromkeys(results))[:12]
    if thumb:
        thumb_res = str(Path(thumb).resolve())
        if thumb_res not in results:
            results = [thumb_res] + results
    return results[:12]


def _find_docs(addon_dir: Path) -> list[Document]:
    docs = []
    seen = set()
    for p in addon_dir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        parent = p.parent.name.lower()
        if p.suffix.lower() not in DOC_EXTENSIONS and not any(k in name for k in ["readme", "manual", "guide", "install", "documentation"]):
            continue
        if parent not in DOC_DIR_HINTS and not any(k in name for k in ["readme", "manual", "guide", "install", "documentation"]):
            continue
        key = str(p.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        docs.append(Document(name=p.name, path=str(p.resolve())))
    docs.sort(key=lambda d: d.name.lower())
    return docs[:40]


def _folder_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except Exception:
            pass
    return round(total / (1024 * 1024), 1)


def _guess_subtype(title: str, addon_type: str) -> Optional[str]:
    if addon_type != "Aircraft":
        return None
    t = title.lower()
    for subtype, keywords in SUBTYPE_MAP.items():
        if any(k in t for k in keywords):
            return subtype
    return "General Aviation"


def _title_from_manifest(manifest: dict, addon_dir: Path) -> str:
    return manifest.get("title") or manifest.get("package_name") or manifest.get("display_name") or addon_dir.name


def _summary_for_type(addon_type: str, title: str, publisher: str) -> str:
    tail = f" by {publisher}" if publisher else ""
    return f"{addon_type} addon{tail}."


def _build_enabled_lookup(community_dir: Optional[Path]) -> Optional[Path]:
    return community_dir if community_dir and community_dir.exists() else None


def _is_enabled(addon_dir: Path, enabled_lookup: Optional[Path]) -> bool:
    if not enabled_lookup:
        return False
    for cand in [addon_dir, *list(addon_dir.parents[:3])]:
        try:
            if linker.find_link_in_community(enabled_lookup, cand):
                return True
        except Exception:
            continue
    return False


def _looks_like_airport_package(raw_ct: str, title: str, package_name: str, addon_root: Path) -> bool:
    if raw_ct in {"AIRCRAFT", "SIMOBJECT", "LIVERY"}:
        return False
    text = " ".join(filter(None, [title, package_name, addon_root.name])).lower()
    if any(h in text for h in AIRCRAFT_FALSE_AIRPORT_HINTS):
        return False
    if raw_ct == "SCENERY":
        return any(h in text for h in AIRPORT_HINTS) or bool(guess_icao(text))
    return any(h in text for h in AIRPORT_HINTS)


def _normalize_title(addon_type: str, title: str, icao: Optional[str], manufacturer: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).strip()


def build_addon_from_manifest(mf_path: Path, enabled_lookup: Optional[Path], container: Optional[Path] = None) -> Optional[Addon]:
    if not mf_path.exists():
        return None
    manifest_dir = mf_path.parent
    addon_root = _addon_root_for_manifest(mf_path, container)
    manifest = _safe_read_json(mf_path)
    if not manifest:
        return None

    raw_ct = str(manifest.get("content_type", "UNKNOWN") or "UNKNOWN").upper()
    addon_type = CONTENT_TYPE_MAP.get(raw_ct, "Mod")
    title = _title_from_manifest(manifest, addon_root)
    probable_icao = guess_icao(" ".join([title, str(manifest.get("package_name") or addon_root.name), addon_root.name]), known_only=True)
    if probable_icao and addon_type != "Aircraft" and _looks_like_airport_package(raw_ct, title, str(manifest.get("package_name") or addon_root.name), addon_root):
        addon_type = "Airport"

    publisher = manifest.get("creator") or manifest.get("publisher") or manifest.get("manufacturer") or ""
    manufacturer_raw = manifest.get("manufacturer") or None
    manufacturer = manufacturer_raw if (manufacturer_raw and manufacturer_raw.lower() != publisher.lower()) else None
    title = _normalize_title(addon_type, title, probable_icao, None)
    version = str(manifest.get("package_version", "") or "")
    package_name = manifest.get("package_name") or manifest_dir.name or addon_root.name
    thumb = _find_thumbnail(addon_root, manifest_dir)
    gallery = _find_gallery(addon_root, thumb)
    docs = _find_docs(addon_root)
    size_mb = _folder_size_mb(addon_root)
    enabled = _is_enabled(addon_root, enabled_lookup)

    addon = Addon(
        id=uuid.uuid4().hex,
        type=addon_type,
        sub=_guess_subtype(title, addon_type),
        title=title,
        publisher=publisher,
        summary=_summary_for_type(addon_type, title, publisher),
        addon_path=str(addon_root.resolve()),
        package_name=package_name,
        manifest_path=str(mf_path.resolve()),
        thumbnail_path=thumb,
        gallery_paths=gallery,
        enabled=enabled,
        last_scanned=time.strftime("%Y-%m-%dT%H:%M:%S"),
        exists=True,
        docs=docs,
    )
    addon.pr.ver = version or None
    addon.pr.size_mb = size_mb or None
    addon.pr.package_name = package_name
    addon.pr.manufacturer = manufacturer
    if addon_type == "Airport":
        addon.rw.icao = probable_icao or guess_icao(" ".join([title, package_name, addon_root.name]))
    enrich_addon(addon)
    return addon




def _merge_gallery(old_paths: list[str], new_paths: list[str]) -> list[str]:
    out = []
    for p in [*(old_paths or []), *(new_paths or [])]:
        if not p:
            continue
        try:
            if Path(p).exists() and p not in out:
                out.append(p)
        except Exception:
            if p not in out:
                out.append(p)
    return out[:20]


def _prefer(old, new):
    return old if old not in (None, "", [], {}) else new


def _merge_existing_addon(old: Addon, scanned: Addon) -> Addon:
    merged = old
    merged.enabled = scanned.enabled
    merged.exists = True
    merged.last_scanned = scanned.last_scanned
    merged.addon_path = scanned.addon_path or old.addon_path
    merged.manifest_path = scanned.manifest_path or old.manifest_path
    merged.package_name = old.package_name or scanned.package_name
    merged.docs = old.docs or scanned.docs
    merged.gallery_paths = _merge_gallery(old.gallery_paths, scanned.gallery_paths)
    if scanned.thumbnail_path and Path(scanned.thumbnail_path).exists():
        if not old.thumbnail_path or not Path(old.thumbnail_path).exists():
            merged.thumbnail_path = scanned.thumbnail_path
    elif old.thumbnail_path and Path(old.thumbnail_path).exists():
        merged.thumbnail_path = old.thumbnail_path
    elif merged.gallery_paths:
        merged.thumbnail_path = merged.gallery_paths[0]

    # only fill missing scan-derived metadata; do not overwrite curated values
    merged.type = old.type or scanned.type
    merged.sub = old.sub or scanned.sub
    merged.title = old.title or scanned.title
    merged.publisher = old.publisher or scanned.publisher
    merged.summary = old.summary or scanned.summary

    for attr in ["lat", "lon"]:
        if getattr(merged, attr) in (None, "") and getattr(scanned, attr) not in (None, ""):
            setattr(merged, attr, getattr(scanned, attr))

    for attr in ["icao","name","city","municipality","state","province","region","region_code","country","country_code","continent","elev","lat","lon","scheduled","airport_type","home_link","wiki_url","mfr","manufacturer_full_name","model","category","engine","engine_type","max_speed","cruise","range","range_nm","ceiling","seats","mtow","avionics","variants","introduced","first_opened","scenery_type","coverage","resolution","util_cat","compat","source"]:
        if getattr(merged.rw, attr) in (None, "", []):
            setattr(merged.rw, attr, getattr(scanned.rw, attr))
    if not merged.rw.runways and scanned.rw.runways:
        merged.rw.runways = scanned.rw.runways

    for attr in ["ver","released","price","source_store","size_mb","package_name","manufacturer"]:
        if getattr(merged.pr, attr) in (None, "", 0):
            setattr(merged.pr, attr, getattr(scanned.pr, attr))
    return merged

class ScanResult:
    def __init__(self):
        self.added: list[Addon] = []
        self.updated: list[Addon] = []
        self.removed: list[str] = []


def _expand_scan_targets(root: Path, selected_paths: Optional[list[str]] = None) -> list[tuple[Path, Path]]:
    selected = [Path(p) for p in (selected_paths or []) if Path(p).exists()]
    containers = selected or _iter_dirs(root)
    jobs = []
    seen = set()
    for container in containers:
        for mf in _discover_manifest_files(container):
            key = str(mf.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            jobs.append((mf, container))
    return jobs


async def scan_addons(
    addons_root: str,
    community_dir: str,
    existing: dict,
    progress_cb: Callable,
    cancel_event: asyncio.Event,
    selected_paths: Optional[list[str]] = None,
    concurrency: int = 6,
    activated_only: bool = False,
) -> ScanResult:
    root = Path(addons_root)
    result = ScanResult()
    if not root.exists():
        await progress_cb({"type": "error", "message": f"Addons folder not found: {addons_root}"})
        return result

    enabled_lookup = _build_enabled_lookup(Path(community_dir) if community_dir else None)
    manifest_jobs = _expand_scan_targets(root, selected_paths)

    total = len(manifest_jobs)
    await progress_cb({"type": "start", "total": total, "current": "Preparing scan...", "pct": 0})
    if total == 0:
        await progress_cb({"type": "done", "scanned": 0, "total": 0, "added": 0, "updated": 0, "removed": 0})
        return result

    existing_by_path = {a.addon_path: a for a in existing.values()}
    seen_paths = set()
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(job: tuple[Path, Path]):
        async with semaphore:
            if cancel_event.is_set():
                return None
            loop = asyncio.get_running_loop()
            mf, container = job
            return await loop.run_in_executor(None, build_addon_from_manifest, mf, enabled_lookup, container)

    tasks = [process_one(job) for job in manifest_jobs]
    scanned = 0
    for coro in asyncio.as_completed(tasks):
        if cancel_event.is_set():
            await progress_cb({"type": "cancelled"})
            return result
        addon = await coro
        scanned += 1
        pct = round(scanned / total * 100, 1)
        current = addon.title if addon else manifest_jobs[scanned - 1][0].parent.name
        msg = {"type": "progress", "scanned": scanned, "total": total, "pct": pct, "current": current}
        if addon:
            if activated_only and not addon.enabled:
                await progress_cb(msg)
                await asyncio.sleep(0)
                continue
            seen_paths.add(addon.addon_path)
            old = existing_by_path.get(addon.addon_path)
            if old:
                addon = _merge_existing_addon(old, addon)
                result.updated.append(addon)
            else:
                result.added.append(addon)
            msg["addon"] = addon.to_frontend_dict()
        await progress_cb(msg)
        await asyncio.sleep(0)

    for path, addon in existing_by_path.items():
        if path not in seen_paths:
            result.removed.append(addon.id)

    await progress_cb({
        "type": "done",
        "scanned": scanned,
        "total": total,
        "added": len(result.added),
        "updated": len(result.updated),
        "removed": len(result.removed),
    })
    return result
