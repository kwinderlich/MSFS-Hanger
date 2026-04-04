from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import aiosqlite

from models import Addon, UserData
from paths import DB_PATH, load_settings_file, save_settings_file, initialize_user_data

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
        await db.execute("CREATE INDEX IF NOT EXISTS idx_addons_path ON addons(addon_path)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_addons_exists ON addons(exists_flag)")
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
            int(addon.enabled), int(addon.exists), addon.last_scanned,
            json.dumps(addon.to_dict(), ensure_ascii=False),
        ))
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executemany("""
            INSERT INTO addons (id, addon_path, type, title, publisher, enabled, exists_flag, last_scanned, data)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(addon_path) DO UPDATE SET
                id=excluded.id,
                type=excluded.type,
                title=excluded.title,
                publisher=excluded.publisher,
                enabled=excluded.enabled,
                exists_flag=excluded.exists_flag,
                last_scanned=excluded.last_scanned,
                data=excluded.data
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

async def get_all_addons(include_removed: bool = False, db_path: Path = DB_PATH) -> dict[str, Addon]:
    out: dict[str, Addon] = {}
    where = "" if include_removed else "WHERE exists_flag=1"
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT data FROM addons {where} ORDER BY title COLLATE NOCASE") as cur:
            async for row in cur:
                try:
                    addon = Addon.from_dict(json.loads(row["data"]))
                    out[addon.id] = addon
                except Exception:
                    continue
    return out

async def get_addon(addon_id: str, db_path: Path = DB_PATH) -> Optional[Addon]:
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT data FROM addons WHERE id=?", (addon_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return Addon.from_dict(json.loads(row["data"]))
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
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
    await _write_settings_snapshot(db_path)

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
