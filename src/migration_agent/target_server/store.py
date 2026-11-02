# Save the target workspace in a local SQLite file.
# Check records before writing them so a bad record cannot erase good data.
# Use source IDs to update records safely when a migration runs again.
"""Save the target workspace in a local SQLite file.

Check records before writing them so a bad record cannot erase good data.
Use source IDs to update records safely when a migration runs again.
"""

from datetime import date, datetime
import json
import math
from pathlib import Path
import sqlite3


PROPERTY_TYPES = (
    "title", "text", "number", "date", "select", "multi_select", "person",
    "url", "relation", "checkbox",
)


class StoreError(ValueError):
    """Explain why a schema or record cannot be saved."""


class Store:
    """Keep one SQLite connection for a target workspace."""

    def __init__(self, path: str | Path = ":memory:"):
        """Open a workspace and create its tables if needed."""
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS databases (
                name TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY,
                db TEXT NOT NULL REFERENCES databases(name),
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                required INTEGER NOT NULL CHECK (required IN (0, 1)),
                relation_database TEXT REFERENCES databases(name),
                UNIQUE (db, name)
            );
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                db TEXT NOT NULL REFERENCES databases(name),
                external_id TEXT NOT NULL,
                UNIQUE (db, external_id)
            );
            CREATE TABLE IF NOT EXISTS page_values (
                page_id INTEGER NOT NULL REFERENCES pages(id),
                property_id INTEGER NOT NULL REFERENCES properties(id),
                value TEXT NOT NULL,
                PRIMARY KEY (page_id, property_id)
            );
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY,
                db TEXT NOT NULL REFERENCES databases(name),
                external_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                UNIQUE (db, external_id)
            );
        """)

    def close(self) -> None:
        """Close the workspace file."""
        self.connection.close()

    def _database(self, db: str) -> None:
        if self.connection.execute("SELECT 1 FROM databases WHERE name = ?", (db,)).fetchone() is None:
            raise StoreError(f"unknown database '{db}'; use list_databases for valid names")

    def create_database(self, spec: dict) -> dict:
        """Save a named database with a list of property rules."""
        if not isinstance(spec, dict) or set(spec) != {"name", "properties"}:
            raise StoreError("spec must contain name and properties")
        name, properties = spec["name"], spec["properties"]
        if not isinstance(name, str) or not name.strip() or not isinstance(properties, list):
            raise StoreError("name must be non-empty text; properties must be a list")
        checked = []
        names = set()
        for prop in properties:
            if not isinstance(prop, dict) or set(prop) - {"name", "type", "required", "relation_database"}:
                raise StoreError("each property needs name, type, optional required and relation_database")
            prop_name, kind = prop.get("name"), prop.get("type")
            if not isinstance(prop_name, str) or not prop_name.strip() or prop_name in names:
                raise StoreError("property names must be non-empty and unique in the database")
            if kind not in PROPERTY_TYPES:
                raise StoreError(f"property '{prop_name}': valid types: {', '.join(PROPERTY_TYPES)}")
            required = prop.get("required", False)
            if type(required) is not bool:
                raise StoreError(f"property '{prop_name}': required must be a boolean")
            target = prop.get("relation_database")
            if kind == "relation":
                if not isinstance(target, str) or not target:
                    raise StoreError(f"relation '{prop_name}' must name an existing relation_database")
                self._database(target)
            elif target is not None:
                raise StoreError(f"property '{prop_name}': relation_database is valid only for relation")
            names.add(prop_name)
            checked.append({"name": prop_name, "type": kind, "required": required,
                            "relation_database": target})
        existing = self.connection.execute("SELECT 1 FROM databases WHERE name = ?", (name,)).fetchone()
        if existing:
            schema = self.get_database(name)
            if schema["properties"] != checked:
                raise StoreError(f"database '{name}' already exists with a different schema")
            return schema
        with self.connection:
            self.connection.execute("INSERT INTO databases (name) VALUES (?)", (name,))
            self.connection.executemany(
                "INSERT INTO properties (db, name, type, required, relation_database) VALUES (?, ?, ?, ?, ?)",
                [(name, p["name"], p["type"], p["required"], p["relation_database"]) for p in checked],
            )
        return self.get_database(name)

    def get_database(self, db: str) -> dict:
        """Read a database name and all its property rules."""
        self._database(db)
        rows = self.connection.execute(
            "SELECT name, type, required, relation_database FROM properties WHERE db = ? ORDER BY id", (db,),
        )
        return {"name": db, "properties": [dict(row, required=bool(row["required"])) for row in rows]}

    def list_databases(self) -> list[dict]:
        """List database schemas in name order."""
        return [self.get_database(row[0]) for row in
                self.connection.execute("SELECT name FROM databases ORDER BY name").fetchall()]

    def upsert_person(self, db: str, external_id: str, name: str, email: str) -> str:
        """Create or update a person by their source ID within a database."""
        self._database(db)
        if not all(isinstance(value, str) for value in (external_id, name, email)) or not external_id.strip():
            raise StoreError("external_id must be non-empty text; name and email must be text")
        with self.connection:
            exists = self.connection.execute(
                "SELECT 1 FROM people WHERE db = ? AND external_id = ?", (db, external_id),
            ).fetchone()
            self.connection.execute(
                """INSERT INTO people (db, external_id, name, email) VALUES (?, ?, ?, ?)
                   ON CONFLICT (db, external_id) DO UPDATE SET name = excluded.name, email = excluded.email
                   WHERE name != excluded.name OR email != excluded.email""", (db, external_id, name, email),
            )
        return "updated" if exists else "created"

    def _value(self, prop: sqlite3.Row, value: object) -> object:
        kind, name = prop["type"], prop["name"]
        if value is None:
            return None
        valid = False
        if kind in {"title", "text", "select", "url"}:
            valid = isinstance(value, str)
        elif kind == "number":
            valid = type(value) in (int, float) and (type(value) is int or math.isfinite(value))
        elif kind == "checkbox":
            valid = type(value) is bool
        elif kind == "date":
            if isinstance(value, str):
                try:
                    date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value)
                    valid = True
                except ValueError:
                    pass
        elif kind in {"multi_select", "person", "relation"}:
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        if not valid:
            raise StoreError(f"property '{name}' expects {kind}")
        if kind in {"relation", "person"}:
            table = "pages" if kind == "relation" else "people"
            db = prop["relation_database"] if kind == "relation" else prop["db"]
            resolved = []
            for external_id in value:
                row = self.connection.execute(
                    f"SELECT id FROM {table} WHERE db = ? AND external_id = ?", (db, external_id),
                ).fetchone()
                if row is None:
                    raise StoreError(f"property '{name}': unknown {kind} external id '{external_id}' in '{db}'")
                resolved.append(row[0])
            return resolved
        return value

    def upsert_page(self, db: str, external_id: str, values: dict, relations: dict | None = None) -> str:
        """Replace a page's values and resolve linked source IDs before saving."""
        self._database(db)
        if not isinstance(external_id, str) or not external_id.strip():
            raise StoreError("external_id must be non-empty text")
        if not isinstance(values, dict) or (relations is not None and not isinstance(relations, dict)):
            raise StoreError("values and relations must be objects keyed by property name")
        relations = {} if relations is None else relations
        properties = self.connection.execute("SELECT * FROM properties WHERE db = ? ORDER BY id", (db,)).fetchall()
        by_name = {p["name"]: p for p in properties}
        for fields, is_relation in ((values, False), (relations, True)):
            for name in fields:
                if name not in by_name:
                    raise StoreError(f"unknown property '{name}'; valid properties: {', '.join(by_name)}")
                if (by_name[name]["type"] == "relation") != is_relation:
                    raise StoreError(f"property '{name}' belongs in {'relations' if not is_relation else 'values'}")
        checked = []
        for prop in properties:
            fields = relations if prop["type"] == "relation" else values
            value = fields.get(prop["name"])
            if prop["required"] and (value is None or value == "" or value == []):
                raise StoreError(f"missing required property '{prop['name']}' (expects {prop['type']})")
            if prop["name"] in fields:
                checked.append((prop["id"], json.dumps(self._value(prop, value), ensure_ascii=False, allow_nan=False)))
        with self.connection:
            row = self.connection.execute(
                "SELECT id FROM pages WHERE db = ? AND external_id = ?", (db, external_id),
            ).fetchone()
            if row is None:
                page_id = self.connection.execute(
                    "INSERT INTO pages (db, external_id) VALUES (?, ?)", (db, external_id),
                ).lastrowid
            else:
                page_id = row[0]
            keep = {prop_id for prop_id, _ in checked}
            for old in self.connection.execute("SELECT property_id FROM page_values WHERE page_id = ?", (page_id,)).fetchall():
                if old[0] not in keep:
                    self.connection.execute("DELETE FROM page_values WHERE page_id = ? AND property_id = ?", (page_id, old[0]))
            self.connection.executemany(
                """INSERT INTO page_values (page_id, property_id, value) VALUES (?, ?, ?)
                   ON CONFLICT (page_id, property_id) DO UPDATE SET value = excluded.value
                   WHERE value != excluded.value""", [(page_id, prop_id, value) for prop_id, value in checked],
            )
        return "created" if row is None else "updated"

    def get_page(self, db: str, external_id: str) -> dict | None:
        """Read a page with linked records shown as source IDs."""
        self._database(db)
        page = self.connection.execute("SELECT id FROM pages WHERE db = ? AND external_id = ?", (db, external_id)).fetchone()
        if page is None:
            return None
        result = {"external_id": external_id, "values": {}, "relations": {}}
        for row in self.connection.execute(
            """SELECT p.name, p.type, v.value FROM page_values v
               JOIN properties p ON p.id = v.property_id WHERE v.page_id = ? ORDER BY p.id""", (page[0],),
        ).fetchall():
            value = json.loads(row["value"])
            if row["type"] in {"relation", "person"} and value is not None:
                table = "pages" if row["type"] == "relation" else "people"
                value = [self.connection.execute(f"SELECT external_id FROM {table} WHERE id = ?", (item,)).fetchone()[0]
                         for item in value]
            result["relations" if row["type"] == "relation" else "values"][row["name"]] = value
        return result

    def list_pages(self, db: str, offset: int = 0, limit: int = 50) -> list[dict]:
        """Read a stable slice of pages in their creation order."""
        self._database(db)
        if type(offset) is not int or type(limit) is not int or offset < 0 or limit < 1:
            raise StoreError("offset must be an integer >= 0; limit must be an integer >= 1")
        rows = self.connection.execute(
            "SELECT external_id FROM pages WHERE db = ? ORDER BY id LIMIT ? OFFSET ?", (db, limit, offset),
        ).fetchall()
        return [self.get_page(db, row[0]) for row in rows]

    def count_pages(self, db: str) -> int:
        """Count the pages in one database."""
        self._database(db)
        return self.connection.execute("SELECT COUNT(*) FROM pages WHERE db = ?", (db,)).fetchone()[0]
