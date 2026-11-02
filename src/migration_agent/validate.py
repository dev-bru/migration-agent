# Compare the workspace with the same values used for migration.
# Read all pages for counts and links, then re-read a fixed sample.
# Save clear failures so a customer can find each affected record.
"""Check migrated pages without changing target data."""

import json
from pathlib import Path
import random

from migration_agent.transform import transform


async def validate(export, plan, target, path: str | Path, sample_size=20, seed=0) -> dict:
    """Save counts, required fields, links and a repeatable content check."""
    if type(sample_size) is not int or sample_size < 0 or type(seed) is not int:
        raise ValueError("sample_size must be a non-negative integer; seed must be an integer")
    schema = await target.list_databases()
    mapped = transform(export, plan, schema)
    schemas = {db["name"]: db for db in schema}
    checks = {name: dict(name=name, status="pass", detail=[], ids=[]) for name in
              ("counts", "required_properties", "relations", "content_sample")}

    def fail(name, detail, ids):
        """Keep a failed check and each affected source ID."""
        check = checks[name]
        check["status"] = "fail"
        check["detail"].append(detail)
        check["ids"].extend(i for i in ids if i not in check["ids"])

    candidates = []
    for entity in plan.entities:
        if entity.source == "member":
            for check in checks.values():
                if check["status"] == "pass":
                    check["status"] = "warn"
                check["detail"].append("member: target has no read tool for people")
            continue
        db = entity.target_database
        expected = {p["external_id"]: p for p in mapped[entity.source]}
        count = await target.count_pages(db)
        pages = []
        while True:
            batch = await target.list_pages(db, offset=len(pages), limit=50)
            pages.extend(batch)
            if len(batch) < 50:
                break
        actual = {p["external_id"]: p for p in pages}
        difference = count - len(expected)
        if difference or set(actual) != set(expected):
            fail("counts", f"{entity.source}: expected {len(expected)}, found {count}, difference {difference:+d}",
                 sorted(set(actual) ^ set(expected)))
        else:
            checks["counts"]["detail"].append(f"{entity.source}: {count} pages match")
        for page in pages:
            external_id = page["external_id"]
            for prop in schemas.get(db, {}).get("properties", []):
                group = "relations" if prop["type"] == "relation" else "values"
                value = page[group].get(prop["name"])
                if prop.get("required") and value in (None, "", []):
                    fail("required_properties", f"{external_id}: missing {prop['name']}", [external_id])
                if prop["type"] == "relation":
                    wanted = expected.get(external_id, {}).get("relations", {}).get(prop["name"], [])
                    if wanted and not value:
                        fail("relations", f"{external_id}: missing relation {prop['name']}", [external_id])
                    for linked_id in value or []:
                        if await target.get_page(prop["relation_database"], linked_id) is None:
                            fail("relations", f"{external_id}: {prop['name']} points to missing {linked_id}",
                                 [external_id, linked_id])
        candidates.extend((entity.source, db, p) for p in expected.values())
    sample = random.Random(seed).sample(candidates, min(sample_size, len(candidates)))
    for entity, db, expected in sample:
        external_id = expected["external_id"]
        actual = await target.get_page(db, external_id)
        if actual is None:
            fail("content_sample", f"{entity} {external_id}: missing page", [external_id])
            continue
        for group in ("values", "relations"):
            for field, value in expected[group].items():
                if field not in actual[group] or actual[group][field] != value:
                    fail("content_sample", f"{entity} {external_id}: changed {field}", [external_id])
    for check in checks.values():
        check["detail"] = "; ".join(check["detail"]) or "All checked values match"
    result = dict(checks=list(checks.values()), seed=seed, sample_size=len(sample),
                  sample=[dict(entity=e, database=db, external_id=p["external_id"]) for e, db, p in sample])
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return result
