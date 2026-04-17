from __future__ import annotations

import json
import sqlite3
import asyncio
from pathlib import Path
import shutil
import zipfile
from typing import Optional
from datetime import datetime

import aiosqlite

from models import Addon, UserData
from paths import DB_PATH, LOG_DIR, BACKUP_DIR, TEST_DIR, LEGACY_HYBRID_DIR, LEGACY_HQ_DIR, LEGACY_QT_DIR, load_settings_file, save_settings_file, initialize_user_data

EVENT_LOG_FILE = LOG_DIR / 'event_logs.jsonl'

async def init_db(db_path: Path = DB_PATH):
    initialize_user_data()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS addons (
                id TEXT PRIMARY KEY,
                addon_path TEXT UNIQUE,
                type TEXT,
                title TEXT,
                publisher TEXT,
                enabled INTEGER DEFAULT 0,
                exists_flag INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_scanned TEXT,
                data TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                color TEXT DEFAULT '#38BDF8'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ignored_addons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                addon_path TEXT,
                package_name TEXT,
                title TEXT,
                publisher TEXT,
                created_at TEXT,
                note TEXT DEFAULT ''
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_addons_path ON addons(addon_path)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_addons_exists ON addons(exists_flag)")
        async with db.execute("PRAGMA table_info(addons)") as cur:
            addon_cols = {str(row[1]) for row in await cur.fetchall()}
        if 'created_at' not in addon_cols:
            # SQLite does not allow ALTER TABLE ... ADD COLUMN with a non-constant default
            # such as CURRENT_TIMESTAMP. Add the column without a default, then backfill.
            await db.execute("ALTER TABLE addons ADD COLUMN created_at TEXT")
        await db.execute("UPDATE addons SET created_at = COALESCE(NULLIF(created_at,''), NULLIF(last_scanned,''), CURRENT_TIMESTAMP) WHERE created_at IS NULL OR created_at=''")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ignored_addons_path ON ignored_addons(addon_path)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id TEXT PRIMARY KEY,
                category TEXT,
                action TEXT,
                started_at TEXT,
                ended_at TEXT,
                duration_seconds REAL DEFAULT 0,
                screen TEXT DEFAULT '',
                provider TEXT DEFAULT '',
                provider_name TEXT DEFAULT '',
                model TEXT DEFAULT '',
                addon_id TEXT DEFAULT '',
                addon_title TEXT DEFAULT '',
                status TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                prompt_preview TEXT DEFAULT '',
                details_json TEXT DEFAULT '{}',
                summary_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ignored_addons_package ON ignored_addons(package_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_event_logs_category_started ON event_logs(category, started_at DESC)")
        async with db.execute("PRAGMA table_info(event_logs)") as cur:
            cols = {str(row[1]) for row in await cur.fetchall()}
        expected = {
            'category': "TEXT", 'action': "TEXT", 'started_at': "TEXT", 'ended_at': "TEXT", 'duration_seconds': "REAL DEFAULT 0",
            'screen': "TEXT DEFAULT ''", 'provider': "TEXT DEFAULT ''", 'provider_name': "TEXT DEFAULT ''", 'model': "TEXT DEFAULT ''",
            'addon_id': "TEXT DEFAULT ''", 'addon_title': "TEXT DEFAULT ''", 'status': "TEXT DEFAULT ''", 'error_message': "TEXT DEFAULT ''",
            'prompt_preview': "TEXT DEFAULT ''", 'details_json': "TEXT DEFAULT '{}'", 'summary_json': "TEXT DEFAULT '{}'", 'created_at': "TEXT"
        }
        for name, ddl in expected.items():
            if name not in cols:
                await db.execute(f"ALTER TABLE event_logs ADD COLUMN {name} {ddl}")
        await db.execute("UPDATE event_logs SET created_at = COALESCE(NULLIF(created_at,''), NULLIF(started_at,''), CURRENT_TIMESTAMP) WHERE created_at IS NULL OR created_at=''")
        await db.commit()

        file_settings = load_settings_file()
        if file_settings:
            for key, value in file_settings.items():
                await db.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)),
                )
            await db.commit()

async def _write_settings_snapshot(db_path: Path = DB_PATH):
    settings = await get_all_settings(db_path)
    normalized = {}
    for key, value in settings.items():
        try:
            normalized[key] = json.loads(value)
        except Exception:
            normalized[key] = value
    save_settings_file(normalized)

async def upsert_addon(addon: Addon, db_path: Path = DB_PATH):
    await upsert_many([addon], db_path=db_path)

async def upsert_many(addons: list[Addon], db_path: Path = DB_PATH):
    if not addons:
        return
    rows = []
    for addon in addons:
        rows.append((
            addon.id, addon.addon_path, addon.type, addon.title, addon.publisher,
            int(addon.enabled), int(addon.exists), (addon.date_added or ''), addon.last_scanned,
            json.dumps(addon.to_dict(), ensure_ascii=False),
        ))
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executemany("""
            INSERT INTO addons (id, addon_path, type, title, publisher, enabled, exists_flag, created_at, last_scanned, data)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(addon_path) DO UPDATE SET
                id=excluded.id,
                type=excluded.type,
                title=excluded.title,
                publisher=excluded.publisher,
                enabled=excluded.enabled,
                exists_flag=excluded.exists_flag,
                created_at=COALESCE(NULLIF(addons.created_at,''), excluded.created_at),
                last_scanned=excluded.last_scanned,
                data=excluded.data
        """, rows)
        await db.commit()


async def update_many_existing(addons: list[Addon], db_path: Path = DB_PATH):
    if not addons:
        return
    rows = []
    for addon in addons:
        rows.append((
            addon.addon_path, addon.type, addon.title, addon.publisher,
            int(addon.enabled), int(addon.exists), addon.last_scanned,
            json.dumps(addon.to_dict(), ensure_ascii=False), addon.id,
        ))
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("BEGIN")
        await db.executemany("""
            UPDATE addons
               SET addon_path=?,
                   type=?,
                   title=?,
                   publisher=?,
                   enabled=?,
                   exists_flag=?,
                   last_scanned=?,
                   data=?
             WHERE id=?
        """, rows)
        await db.commit()

async def mark_removed(addon_ids: list[str], db_path: Path = DB_PATH):
    if not addon_ids:
        return
    placeholders = ",".join("?" for _ in addon_ids)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(f"UPDATE addons SET exists_flag=0 WHERE id IN ({placeholders})", addon_ids)
        await db.commit()

async def delete_all_addons(db_path: Path = DB_PATH):
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("DELETE FROM addons")
        await db.commit()

async def delete_addons(addon_ids: list[str], db_path: Path = DB_PATH):
    if not addon_ids:
        return
    placeholders = ",".join("?" for _ in addon_ids)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(f"DELETE FROM addons WHERE id IN ({placeholders})", addon_ids)
        await db.commit()

async def get_all_addons(include_removed: bool = False, db_path: Path = DB_PATH) -> dict[str, Addon]:
    out: dict[str, Addon] = {}
    where = "" if include_removed else "WHERE exists_flag=1"
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT data, created_at FROM addons {where} ORDER BY title COLLATE NOCASE") as cur:
            async for row in cur:
                try:
                    addon = Addon.from_dict(json.loads(row["data"]))
                    addon.date_added = addon.date_added or row["created_at"]
                    out[addon.id] = addon
                except Exception:
                    continue
    return out

async def get_addon(addon_id: str, db_path: Path = DB_PATH) -> Optional[Addon]:
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT data, created_at FROM addons WHERE id=?", (addon_id,)) as cur:
            row = await cur.fetchone()
            if row:
                addon = Addon.from_dict(json.loads(row["data"]))
                addon.date_added = addon.date_added or row["created_at"]
                return addon
    return None

async def update_addon_user_data(addon_id: str, usr_dict: dict, db_path: Path = DB_PATH):
    addon = await get_addon(addon_id, db_path)
    if not addon:
        return
    allowed = {k: v for k, v in usr_dict.items() if k in UserData.__dataclass_fields__}
    addon.usr = UserData(**{**addon.usr.__dict__, **allowed})
    if "avionics" in allowed:
        addon.rw.avionics = allowed.get("avionics")
    await upsert_addon(addon, db_path)


async def update_addon_core(addon_id: str, fields: dict, db_path: Path = DB_PATH):
    addon = await get_addon(addon_id, db_path)
    if not addon:
        return
    direct_allowed = {"type", "sub", "title", "publisher", "summary", "thumbnail_path", "gallery_paths"}
    for key, value in fields.items():
        if key in direct_allowed:
            setattr(addon, key, value)
        elif key == "manufacturer":
            addon.pr.manufacturer = value
            addon.rw.mfr = value
        elif key == "manufacturer_full_name":
            addon.rw.manufacturer_full_name = value
        elif key == "model":
            addon.rw.model = value
        elif key == "category":
            addon.rw.category = value
        elif key == "icao":
            addon.rw.icao = value
        elif key == "version":
            addon.pr.ver = value
        elif key == "latest_version":
            addon.pr.latest_ver = value
        elif key == "latest_version_date":
            addon.pr.latest_ver_date = value
        elif key == "released":
            addon.pr.released = value
        elif key == "price":
            addon.pr.price = value
        elif key == "package_name":
            addon.package_name = value
            addon.pr.package_name = value
        elif key == "product_source_store":
            addon.pr.source_store = value
        elif key == "rw_override" and isinstance(value, dict):
            for rk, rv in value.items():
                if rk in addon.rw.__dataclass_fields__:
                    setattr(addon.rw, rk, rv)
    await upsert_addon(addon, db_path)

async def set_enabled(addon_id: str, enabled: bool, db_path: Path = DB_PATH):
    addon = await get_addon(addon_id, db_path)
    if not addon:
        return
    addon.enabled = enabled
    await upsert_addon(addon, db_path)

async def get_setting(key: str, default: str = "", db_path: Path = DB_PATH) -> str:
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str, db_path: Path = DB_PATH):
    last_exc = None
    for attempt in range(4):
        try:
            async with aiosqlite.connect(str(db_path), timeout=8) as db:
                await db.execute('PRAGMA busy_timeout = 8000')
                await db.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
                await db.commit()
            await _write_settings_snapshot(db_path)
            return
        except sqlite3.OperationalError as exc:
            last_exc = exc
            if 'locked' not in str(exc).lower() or attempt >= 3:
                raise
            await asyncio.sleep(0.12 * (attempt + 1))
    if last_exc:
        raise last_exc

async def get_json_setting(key: str, default, db_path: Path = DB_PATH):
    raw = await get_setting(key, "", db_path)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

async def set_json_setting(key: str, value, db_path: Path = DB_PATH):
    await set_setting(key, json.dumps(value, ensure_ascii=False), db_path)

async def get_all_settings(db_path: Path = DB_PATH) -> dict[str, str]:
    out = {}
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute("SELECT key, value FROM settings") as cur:
            async for row in cur:
                out[row[0]] = row[1]
    return out


async def get_addons(include_removed: bool = False, db_path: Path = DB_PATH) -> list[Addon]:
    return list((await get_all_addons(include_removed=include_removed, db_path=db_path)).values())


async def list_ignored_addons(db_path: Path = DB_PATH) -> list[dict]:
    out = []
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, addon_path, package_name, title, publisher, created_at, note FROM ignored_addons ORDER BY COALESCE(title, addon_path) COLLATE NOCASE") as cur:
            async for row in cur:
                out.append(dict(row))
    return out


async def add_ignored_addons(entries: list[dict], db_path: Path = DB_PATH):
    if not entries:
        return
    rows = []
    for entry in entries:
        rows.append((
            (entry.get('addon_path') or '').strip(),
            (entry.get('package_name') or '').strip(),
            (entry.get('title') or '').strip(),
            (entry.get('publisher') or '').strip(),
            (entry.get('created_at') or '').strip(),
            (entry.get('note') or '').strip(),
        ))
    async with aiosqlite.connect(str(db_path)) as db:
        for addon_path, package_name, title, publisher, created_at, note in rows:
            if not addon_path and not package_name:
                continue
            await db.execute(
                "DELETE FROM ignored_addons WHERE (? != '' AND LOWER(addon_path)=LOWER(?)) OR (? != '' AND LOWER(package_name)=LOWER(?))",
                (addon_path, addon_path, package_name, package_name),
            )
            await db.execute(
                "INSERT INTO ignored_addons(addon_path, package_name, title, publisher, created_at, note) VALUES(?,?,?,?,?,?)",
                (addon_path, package_name, title, publisher, created_at, note),
            )
        await db.commit()


async def remove_ignored_addons(ignore_ids: list[int], db_path: Path = DB_PATH):
    if not ignore_ids:
        return
    placeholders = ",".join("?" for _ in ignore_ids)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(f"DELETE FROM ignored_addons WHERE id IN ({placeholders})", [int(x) for x in ignore_ids])
        await db.commit()


async def remap_ignored_paths(old_root: str, new_root: str, db_path: Path = DB_PATH):
    old_root_norm = str(old_root or '').strip().replace('/', '\\').rstrip('\\')
    new_root_norm = str(new_root or '').strip().replace('/', '\\').rstrip('\\')
    if not old_root_norm or not new_root_norm or old_root_norm.lower() == new_root_norm.lower():
        return
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, addon_path FROM ignored_addons") as cur:
            rows = await cur.fetchall()
        for row in rows:
            path_value = (row['addon_path'] or '').strip()
            if not path_value:
                continue
            low = path_value.lower().replace('/', '\\')
            old_low = old_root_norm.lower()
            if low == old_low or low.startswith(old_low + '\\'):
                suffix = path_value[len(old_root_norm):].lstrip('\\/')
                next_path = new_root_norm + ('\\' + suffix if suffix else '')
                await db.execute("UPDATE ignored_addons SET addon_path=? WHERE id=?", (next_path, row['id']))
        await db.commit()


def _read_event_log_file() -> list[dict]:
    initialize_user_data()
    out = []
    try:
        if EVENT_LOG_FILE.exists():
            for line in EVENT_LOG_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out

def _append_event_log_file(entry: dict):
    initialize_user_data()
    payload = dict(entry or {})
    if 'created_at' not in payload:
        payload['created_at'] = datetime.now().isoformat(timespec='seconds')
    try:
        with EVENT_LOG_FILE.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + '\n')
    except Exception:
        pass

async def add_event_log(entry: dict, db_path: Path = DB_PATH):
    payload = dict(entry or {})
    details = payload.pop('details', {}) or {}
    summary = payload.pop('summary', {}) or {}
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO event_logs(
                id, category, action, started_at, ended_at, duration_seconds,
                screen, provider, provider_name, model, addon_id, addon_title,
                status, error_message, prompt_preview, details_json, summary_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(payload.get('id') or ''),
                str(payload.get('category') or ''),
                str(payload.get('action') or ''),
                str(payload.get('started_at') or payload.get('timestamp') or ''),
                str(payload.get('ended_at') or ''),
                float(payload.get('duration_seconds') or 0),
                str(payload.get('screen') or ''),
                str(payload.get('provider') or ''),
                str(payload.get('provider_name') or ''),
                str(payload.get('model') or ''),
                str(payload.get('addon_id') or ''),
                str(payload.get('addon_title') or ''),
                str(payload.get('status') or ''),
                str(payload.get('error_message') or ''),
                str(payload.get('prompt_preview') or ''),
                json.dumps(details, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
            ),
        )
        await db.commit()
    _append_event_log_file({**payload, 'details': details, 'summary': summary})


async def list_event_logs(category: Optional[str] = None, limit: int = 200, db_path: Path = DB_PATH) -> list[dict]:
    where = ""
    args: list = []
    if category:
        where = "WHERE category=?"
        args.append(category)
    args.append(int(limit))
    out = []
    seen = set()
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM event_logs {where} ORDER BY COALESCE(started_at, created_at) DESC LIMIT ?",
            args,
        ) as cur:
            async for row in cur:
                item = dict(row)
                for src, dst in (("details_json", "details"), ("summary_json", "summary")):
                    raw = item.pop(src, None)
                    try:
                        item[dst] = json.loads(raw) if raw else {}
                    except Exception:
                        item[dst] = {}
                key = str(item.get('id') or '') or f"{item.get('created_at','')}|{item.get('action','')}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
    for item in _read_event_log_file():
        if category and str(item.get('category') or '') != category:
            continue
        key = str(item.get('id') or '') or f"{item.get('created_at','')}|{item.get('action','')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda item: str(item.get('started_at') or item.get('created_at') or ''), reverse=True)
    return out[: int(limit)]


async def delete_event_logs_range(category: Optional[str] = None, start_at: Optional[str] = None, end_at: Optional[str] = None, db_path: Path = DB_PATH) -> dict:
    clauses = []
    args: list = []
    if category:
        clauses.append("category=?")
        args.append(str(category))
    if start_at:
        clauses.append("COALESCE(started_at, created_at) >= ?")
        args.append(str(start_at))
    if end_at:
        clauses.append("COALESCE(started_at, created_at) <= ?")
        args.append(str(end_at))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    deleted = 0
    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute(f"SELECT COUNT(*) FROM event_logs {where}", args) as cur:
            row = await cur.fetchone()
            deleted = int((row or [0])[0] or 0)
        await db.execute(f"DELETE FROM event_logs {where}", args)
        await db.commit()
    # rewrite JSONL fallback file
    try:
        kept = []
        for item in _read_event_log_file():
            ts = str(item.get('started_at') or item.get('created_at') or '')
            if category and str(item.get('category') or '') != str(category):
                kept.append(item); continue
            if start_at and ts < str(start_at):
                kept.append(item); continue
            if end_at and ts > str(end_at):
                kept.append(item); continue
        initialize_user_data()
        with EVENT_LOG_FILE.open('w', encoding='utf-8') as fh:
            for item in kept:
                fh.write(json.dumps(item, ensure_ascii=False) + '\n')
    except Exception:
        pass
    return {'deleted': deleted, 'category': category or 'all', 'start_at': start_at or '', 'end_at': end_at or ''}


def _safe_json_load(path: Path, default):
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return data
    except Exception:
        pass
    return default


async def detect_storage_sources(db_path: Path = DB_PATH) -> dict:
    initialize_user_data()
    return {
        'sqlite': {
            'path': str(db_path),
            'exists': db_path.exists(),
            'size': (db_path.stat().st_size if db_path.exists() else 0),
            'modified': (datetime.fromtimestamp(db_path.stat().st_mtime).isoformat(timespec='seconds') if db_path.exists() else ''),
        },
        'legacy_hybrid': {
            'dir': str(LEGACY_HYBRID_DIR),
            'exists': LEGACY_HYBRID_DIR.exists(),
            'addons_json': str(LEGACY_HYBRID_DIR / 'addons.json'),
            'addons_exists': (LEGACY_HYBRID_DIR / 'addons.json').exists(),
            'collections_exists': (LEGACY_HYBRID_DIR / 'collections.json').exists(),
            'settings_exists': (LEGACY_HYBRID_DIR / 'settings.json').exists(),
        },
        'legacy_hq': {
            'dir': str(LEGACY_HQ_DIR),
            'exists': LEGACY_HQ_DIR.exists(),
            'db': str(LEGACY_HQ_DIR / 'hangar_hq.db'),
            'db_exists': (LEGACY_HQ_DIR / 'hangar_hq.db').exists(),
        },
        'legacy_qt': {
            'dir': str(LEGACY_QT_DIR),
            'exists': LEGACY_QT_DIR.exists(),
            'settings_exists': (LEGACY_QT_DIR / 'settings.json').exists(),
        },
    }


async def migrate_legacy_storage(db_path: Path = DB_PATH) -> dict:
    initialize_user_data()
    await init_db(db_path)
    report = {
        'imported_addons': 0,
        'imported_settings': 0,
        'imported_collections': 0,
        'sources': [],
        'notes': [],
    }

    hybrid = LEGACY_HYBRID_DIR
    if hybrid.exists():
        report['sources'].append(str(hybrid))
        addons_path = hybrid / 'addons.json'
        if addons_path.exists():
            raw = _safe_json_load(addons_path, [])
            items = []
            if isinstance(raw, list):
                items = [item for item in raw if isinstance(item, dict)]
            elif isinstance(raw, dict):
                if isinstance(raw.get('addons'), list):
                    items = [item for item in raw.get('addons', []) if isinstance(item, dict)]
                else:
                    items = [v for v in raw.values() if isinstance(v, dict)]
            parsed = []
            for item in items:
                try:
                    addon = Addon.from_dict(item)
                    parsed.append(addon)
                except Exception:
                    continue
            if parsed:
                await upsert_many(parsed, db_path=db_path)
                report['imported_addons'] = len(parsed)
            else:
                report['notes'].append('No importable legacy add-ons were found in addons.json.')

        settings_path = hybrid / 'settings.json'
        settings_raw = _safe_json_load(settings_path, {})
        if isinstance(settings_raw, dict):
            for key, value in settings_raw.items():
                await set_setting(str(key), json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value), db_path=db_path)
                report['imported_settings'] += 1

        collections_path = hybrid / 'collections.json'
        collections_raw = _safe_json_load(collections_path, None)
        if collections_raw is not None:
            profiles = []
            if isinstance(collections_raw, list):
                for idx, item in enumerate(collections_raw):
                    if isinstance(item, dict):
                        name = str(item.get('name') or item.get('title') or f'Collection {idx+1}')
                        addon_ids = item.get('addon_ids') or item.get('addons') or item.get('ids') or []
                        if isinstance(addon_ids, list):
                            profiles.append({'id': str(item.get('id') or f'legacy-{idx+1}'), 'name': name, 'addon_ids': addon_ids, 'created_at': str(item.get('created_at') or '')})
            elif isinstance(collections_raw, dict):
                maybe = collections_raw.get('profiles') or collections_raw.get('collections')
                if isinstance(maybe, list):
                    for idx, item in enumerate(maybe):
                        if isinstance(item, dict):
                            name = str(item.get('name') or item.get('title') or f'Collection {idx+1}')
                            addon_ids = item.get('addon_ids') or item.get('addons') or item.get('ids') or []
                            if isinstance(addon_ids, list):
                                profiles.append({'id': str(item.get('id') or f'legacy-{idx+1}'), 'name': name, 'addon_ids': addon_ids, 'created_at': str(item.get('created_at') or '')})
            if profiles:
                await set_setting('profiles_json', json.dumps(profiles, ensure_ascii=False), db_path=db_path)
                report['imported_collections'] = len(profiles)

    hq_db = LEGACY_HQ_DIR / 'hangar_hq.db'
    if hq_db.exists():
        report['sources'].append(str(hq_db))
        report['notes'].append('Legacy HQ database detected and preserved for backup, but automatic row-level migration is not implemented in this build.')

    qt_settings = LEGACY_QT_DIR / 'settings.json'
    if qt_settings.exists():
        report['sources'].append(str(qt_settings))
        qt_raw = _safe_json_load(qt_settings, {})
        if isinstance(qt_raw, dict):
            for key, value in qt_raw.items():
                if key and not await get_setting(str(key), '', db_path=db_path):
                    await set_setting(str(key), json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value), db_path=db_path)
                    report['imported_settings'] += 1

    return report


def _backup_filename() -> str:
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'MSFSHangar Backup {stamp}.zip'


async def create_data_backup(db_path: Path = DB_PATH, destination: Optional[Path] = None) -> dict:
    initialize_user_data()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_zip = Path(destination) if destination else (BACKUP_DIR / _backup_filename())
    backup_zip.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'user_data_dir': str(DB_PATH.parent),
        'db_path': str(db_path),
        'legacy_hybrid_dir': str(LEGACY_HYBRID_DIR),
        'legacy_hq_dir': str(LEGACY_HQ_DIR),
        'legacy_qt_dir': str(LEGACY_QT_DIR),
    }
    with zipfile.ZipFile(backup_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('backup_manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        for base in [DB_PATH.parent, LEGACY_HYBRID_DIR, LEGACY_HQ_DIR, LEGACY_QT_DIR]:
            if not base.exists():
                continue
            for path in base.rglob('*'):
                if path.is_dir():
                    continue
                try:
                    if path == backup_zip:
                        continue
                    arcname = f'{base.name}/{path.relative_to(base)}'
                    zf.write(path, arcname)
                except Exception:
                    continue
    return {
        'ok': True,
        'backup_zip': str(backup_zip),
        'size': backup_zip.stat().st_size if backup_zip.exists() else 0,
        'default_name': backup_zip.name,
    }


async def run_storage_test(db_path: Path = DB_PATH) -> dict:
    initialize_user_data()
    await init_db(db_path)
    stamp = datetime.now().isoformat(timespec='seconds')
    key = 'storage_test_last_run'
    value = {'timestamp': stamp, 'db_path': str(db_path)}
    await set_json_setting(key, value, db_path=db_path)
    roundtrip = await get_json_setting(key, {}, db_path=db_path)
    marker = TEST_DIR / 'storage_test_marker.json'
    marker.write_text(json.dumps({'timestamp': stamp, 'marker': 'ok'}, indent=2), encoding='utf-8')
    marker_roundtrip = {}
    if marker.exists():
        marker_roundtrip = json.loads(marker.read_text(encoding='utf-8'))
    settings_snapshot = load_settings_file()
    if not db_path.exists() or roundtrip != value or not marker.exists() or marker_roundtrip.get('timestamp') != stamp or 'storage_test_last_run' not in settings_snapshot:
        raise RuntimeError('Storage test failed: data could not be re-read immediately after write.')
    await add_event_log({
        'id': f'storage-test-{stamp}',
        'category': 'system',
        'action': 'storage_test',
        'started_at': stamp,
        'ended_at': stamp,
        'duration_seconds': 0,
        'screen': 'settings_application',
        'status': 'ok',
        'details': {'marker_file': str(marker), 'db_path': str(db_path)},
        'summary': {'roundtrip_ok': roundtrip == value},
    }, db_path=db_path)
    return {
        'ok': True,
        'timestamp': stamp,
        'db_path': str(db_path),
        'db_exists_after_test': db_path.exists(),
        'settings_roundtrip_ok': roundtrip == value,
        'marker_file': str(marker),
        'marker_exists': marker.exists(),
    }
