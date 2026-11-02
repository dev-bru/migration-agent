# Move checked records in small groups using source IDs.
# Save progress only after a whole group succeeds.
# Repeating a group is safe because the target uses upserts.
"""Run an approved migration and resume it from an atomic checkpoint."""

import hashlib
import json
from pathlib import Path

from migration_agent.mapping import read_plan
from migration_agent.signoff import require_signoff
from migration_agent.target import TargetError
from migration_agent.transform import transform


class MigrationError(ValueError):
    """Explain why a migration cannot start or continue."""


def write_checkpoint(path: str | Path, checkpoint: dict) -> None:
    """Replace progress only after the new JSON file is complete."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


async def migrate(export, plan_path, target, checkpoint_path, batch_size=50, signoff_path=None) -> dict:
    """Require approval, retry failed batches and save each finished batch."""
    plan_path, checkpoint_path = Path(plan_path), Path(checkpoint_path)
    require_signoff(plan_path, signoff_path or plan_path.with_name("signoff.json"))
    plan = read_plan(plan_path)
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if type(batch_size) is not int or batch_size < 1:
        raise MigrationError("batch_size must be a positive integer")
    schema = await target.list_databases()
    mapped = transform(export, plan, schema)
    entities = {e.source: e for e in plan.entities}
    jobs = []
    people_dbs = {db["name"] for db in schema if any(p["type"] == "person" for p in db["properties"])
                 and db["name"] in {e.target_database for e in plan.entities}}
    if "member" in entities:
        people_dbs.add(entities["member"].target_database)
    for db in sorted(people_dbs):
        people = {}
        for board in export.boards:
            for member in board.members:
                value = dict(external_id=member.id, name=member.name, email=member.email)
                if member.id in people and people[member.id] != value:
                    raise MigrationError(f"conflicting member {member.id}")
                people[member.id] = value
        jobs.append((f"people:{db}", db, list(people.values()), True))
    order = ["board", "card", "checklist_item", "comment"]
    for name in sorted(entities, key=lambda name: order.index(name) if name in order else len(order)):
        if name != "member":
            jobs.append((name, entities[name].target_database, mapped[name], False))
    checkpoint = dict(plan_hash=plan_hash, batch_size=batch_size, entities={})
    if checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise MigrationError(f"cannot read checkpoint: {error}") from error
        if not isinstance(checkpoint, dict) or checkpoint.get("plan_hash") != plan_hash:
            raise MigrationError("checkpoint plan hash does not match")
        if checkpoint.get("batch_size") != batch_size:
            raise MigrationError("checkpoint batch_size does not match")
        if not isinstance(checkpoint.get("entities"), dict):
            raise MigrationError("checkpoint entities must be an object")
    for name, db, records, people in jobs:
        total = (len(records) + batch_size - 1) // batch_size
        progress = checkpoint["entities"].setdefault(name, dict(done_batches=0, total_batches=total, created=0, updated=0))
        if (not isinstance(progress, dict) or set(progress) != {"done_batches", "total_batches", "created", "updated"}
                or any(type(v) is not int or v < 0 for v in progress.values())
                or progress["total_batches"] != total or progress["done_batches"] > total):
            raise MigrationError(f"invalid checkpoint for {name}")
    for name, db, records, people in jobs:
        progress = checkpoint["entities"][name]
        for index in range(progress["done_batches"], progress["total_batches"]):
            batch = records[index * batch_size:(index + 1) * batch_size]
            for attempt in range(4):
                counts = {"created": 0, "updated": 0}
                try:
                    for record in batch:
                        status = await (target.upsert_person(db, **record) if people else target.upsert_page(db, **record))
                        counts[status] += 1
                    break
                except TargetError as error:
                    if attempt == 3:
                        raise MigrationError(f"{name} batch {index + 1} failed after 3 retries: {error}") from error
            progress["done_batches"] = index + 1
            for status in counts:
                progress[status] += counts[status]
            write_checkpoint(checkpoint_path, checkpoint)
    return checkpoint
