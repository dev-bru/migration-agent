"""Check the SQLite target with made-up records and no network.

Check schema rules before using the store through MCP.
Keep each workspace in memory or in pytest's temporary folder.
"""

import sqlite3

import pytest

from migration_agent.target_server.store import PROPERTY_TYPES, Store, StoreError


@pytest.fixture
def store():
    """Open a fresh workspace and close it after the test."""
    target = Store()
    yield target
    target.close()


def test_schema_round_trip_and_persistence(tmp_path):
    """Read three saved property rules after reopening the file."""
    path = tmp_path / "nested" / "target.sqlite"
    target = Store(path)
    spec = {"name": "Tasks", "properties": [
        {"name": "Title", "type": "title", "required": True},
        {"name": "Done", "type": "checkbox"},
        {"name": "Tags", "type": "multi_select"},
    ]}
    schema = target.create_database(spec)
    assert schema == {"name": "Tasks", "properties": [
        dict(prop, required=prop.get("required", False), relation_database=None) for prop in spec["properties"]
    ]}
    assert target.create_database(spec) == schema
    target.close()
    target = Store(path)
    try:
        assert target.get_database("Tasks") == schema
        assert target.list_databases() == [schema]
        assert {row[0] for row in target.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")} == {
            "databases", "properties", "pages", "page_values", "people",
        }
    finally:
        target.close()


def test_unknown_type_lists_valid_types(store):
    """Reject an unknown type and leave no partial database."""
    with pytest.raises(StoreError) as error:
        store.create_database({"name": "Bad", "properties": [{"name": "Title", "type": "mystery"}]})
    assert all(kind in str(error.value) for kind in PROPERTY_TYPES)
    assert store.list_databases() == []


@pytest.mark.parametrize("target", [None, "Missing"])
def test_relation_needs_existing_database(store, target):
    """Refuse a relation until its target database exists."""
    spec = {"name": "Tasks", "properties": [
        {"name": "Project", "type": "relation", "relation_database": target},
    ]}
    with pytest.raises(StoreError, match="existing|Missing"):
        store.create_database(spec)
    store.create_database({"name": "Projects", "properties": []})
    spec["properties"][0]["relation_database"] = "Projects"
    assert store.create_database(spec)["properties"][0]["relation_database"] == "Projects"


def test_external_ids_are_unique_per_database(store):
    """Allow the same source ID in two databases, but never twice in one."""
    for db in ("Tasks", "Projects"):
        store.create_database({"name": db, "properties": []})
        assert store.upsert_page(db, "same", {}) == "created"
        assert store.upsert_page(db, "same", {}) == "updated"
        assert store.count_pages(db) == 1
        assert store.upsert_person(db, "same", "Ada", "ada@example.test") == "created"
        assert store.upsert_person(db, "same", "Bea", "bea@example.test") == "updated"
        assert tuple(store.connection.execute("SELECT name, email FROM people WHERE db = ?", (db,)).fetchone()) == (
            "Bea", "bea@example.test",
        )
        for table in ("pages", "people"):
            with pytest.raises(sqlite3.IntegrityError), store.connection:
                if table == "pages":
                    store.connection.execute("INSERT INTO pages (db, external_id) VALUES (?, 'same')", (db,))
                else:
                    store.connection.execute(
                        "INSERT INTO people (db, external_id, name, email) VALUES (?, 'same', 'Ada', '')", (db,),
                    )
    assert store.connection.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 2


def test_schema_failure_does_not_change_existing_data(store):
    """Keep the old schema when a retry supplies different property rules."""
    spec = {"name": "Tasks", "properties": [{"name": "Title", "type": "title"}]}
    schema = store.create_database(spec)
    with pytest.raises(StoreError, match="different schema"):
        store.create_database({"name": "Tasks", "properties": []})
    assert store.get_database("Tasks") == schema


@pytest.mark.parametrize("kind,good,bad", [
    ("title", "Make a kite", []),
    ("text", "Made-up notes", 9),
    ("number", 2.5, True),
    ("date", "2026-11-02T10:00:00Z", "2026-02-30"),
    ("select", "Ready", ["Ready"]),
    ("multi_select", ["Blue", "Small"], ["Blue", 3]),
    ("person", ["member-1"], ["missing-member"]),
    ("url", "https://example.test/kite", 8),
    ("checkbox", False, 0),
])
def test_property_types_and_failed_update(store, kind, good, bad):
    """Read each value type and keep the old value after an invalid update."""
    store.create_database({"name": "Tasks", "properties": [
        {"name": "Field", "type": kind, "required": True},
    ]})
    store.upsert_person("Tasks", "member-1", "Ada", "ada@example.test")
    store.upsert_page("Tasks", "card-1", {"Field": good})
    assert store.get_page("Tasks", "card-1")["values"] == {"Field": good}
    before = store.connection.serialize()
    with pytest.raises(StoreError, match="Field"):
        store.upsert_page("Tasks", "card-1", {"Field": bad})
    assert store.connection.serialize() == before


def test_pagination_and_unknown_database_errors(store):
    """Reject invalid page ranges and unknown database names."""
    store.create_database({"name": "Tasks", "properties": []})
    for offset, limit in ((-1, 1), (0, 0), (True, 1), (0, 1.5)):
        with pytest.raises(StoreError, match="offset.*limit"):
            store.list_pages("Tasks", offset, limit)
    with pytest.raises(StoreError, match="Missing.*valid names"):
        store.count_pages("Missing")
