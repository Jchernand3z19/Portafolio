"""One-time five-table migration, executable locally; no remote transport or credentials."""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from generar_mvp_sqlite_la_colonia import create_schema

LEGACY_FINGERPRINT = "d00fa5e684c68b4e6e9b28679d95cc816d40f089df6f4e212484a2e524bc3133"
SCHEMA_QUERY = "SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY name"


def _normalized(rows):
    return [(name, re.sub(r"\s+", "", sql.replace('"', '').rstrip(';'))) for name, sql in rows]


def fingerprint(rows):
    return hashlib.sha256(json.dumps(_normalized(rows), separators=(",", ":")).encode()).hexdigest()


def target_schema():
    con = sqlite3.connect(":memory:")
    try:
        create_schema(con)
        return con.execute(SCHEMA_QUERY).fetchall()
    finally:
        con.close()


def schema_ready(rows):
    expected = [(name, sql) for name, sql in target_schema()
                if name in {"locations", "price_history", "idx_locations_city_legacy"}]
    return _normalized(rows) == _normalized(expected)


def migration_steps():
    """Same step format as the existing transactional Turso batch, never run daily."""
    schema = dict(target_schema())
    steps = [("foreign_keys_off", "PRAGMA foreign_keys=OFF", ()),
             ("drop_guard_table", "DROP TABLE IF EXISTS temp.migration_guard", ()),
             ("guard_table", "CREATE TEMP TABLE migration_guard(value INTEGER NOT NULL CHECK(value=0)) STRICT", ()),
             ("begin", "BEGIN IMMEDIATE", ())]
    for table in ["locations", "price_history"]:
        new = "walmart_new_" + table
        ddl = schema[table].replace("CREATE TABLE " + table, "CREATE TABLE " + new, 1)
        steps.extend([
            ("create_" + table, ddl, ()),
            ("copy_" + table, f"INSERT INTO {new} SELECT * FROM {table}", ()),
            ("guard_" + table, f"INSERT INTO migration_guard SELECT CASE WHEN (SELECT COUNT(*) FROM {new})=(SELECT COUNT(*) FROM {table}) THEN 0 ELSE 1 END", ()),
            ("drop_" + table, "DROP TABLE " + table, ()),
            ("rename_" + table, f"ALTER TABLE {new} RENAME TO {table}", ()),
        ])
    steps.extend([
        ("index_current", schema["idx_price_history_current"], ()),
        ("index_legacy_city", schema["idx_locations_city_legacy"], ()),
        ("guard_foreign_keys", "INSERT INTO migration_guard SELECT COUNT(*) FROM pragma_foreign_key_check", ()),
        ("commit", "COMMIT", ()),
        ("foreign_keys_on", "PRAGMA foreign_keys=ON", ()),
    ])
    return steps


def migrate_database(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("database_missing")
    con = sqlite3.connect(path, isolation_level=None)
    try:
        before = fingerprint(con.execute(SCHEMA_QUERY).fetchall())
        target = fingerprint(target_schema())
        if before == target:
            return {"migrated": False, "schema_fingerprint": target}
        if before != LEGACY_FINGERPRINT:
            raise ValueError("unrecognized_schema_no_migration")
        for name, sql, args in migration_steps():
            if name == "commit" and fingerprint(con.execute(SCHEMA_QUERY).fetchall()) != target:
                raise ValueError("migration_schema_mismatch")
            con.execute(sql, args)
        return {"migrated": True, "schema_fingerprint": target}
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, required=True, help="Existing local database; back it up first")
    args = parser.parse_args()
    print(json.dumps(migrate_database(args.sqlite)))
