# Map source records without changing either workspace.
# Keep parent IDs so links can use the source IDs.
# Share these rules between preview, migration and checks.
"""Turn source records into target values without side effects."""

from migration_agent.mapping import MappingPlan, PlanError, check_plan
from migration_agent.source import Export


def transform(export: Export, plan: MappingPlan, target_schema: list[dict]) -> dict[str, list[dict]]:
    """Map each planned entity and reject values that would lose data."""
    check_plan(plan, target_schema)
    if plan.source_hash != export.source_hash:
        raise PlanError("source_hash does not match the export")
    records = {}

    def visit(record, parents, board):
        """Collect a record with its board and parent IDs."""
        kind = type(record).__name__
        names = {"BoardList": "list", "ChecklistItem": "checklist_item"}
        name = names.get(kind, kind.lower())
        records.setdefault(name, []).append((record, parents, board))
        for value in record.__dict__.values():
            if isinstance(value, list):
                for child in value:
                    if hasattr(child, "model_dump"):
                        visit(child, dict(parents, **{name: record.id}), board)

    for board in export.boards:
        visit(board, {}, board)
    destinations = {e.target_database: e.source for e in plan.entities}
    schemas = {db["name"]: {p["name"]: p for p in db["properties"]} for db in target_schema}
    result = {}
    for entity in plan.entities:
        pages = []
        for record, parents, board in records.get(entity.source, []):
            page = {"external_id": record.id, "values": {}, "relations": {}}
            raw = record.model_dump(mode="json")
            for field in entity.fields:
                value = raw[field.source_field]
                prop = schemas.get(entity.target_database, {}).get(field.target_property, {})
                if field.type == "relation":
                    parent_kind = destinations.get(prop.get("relation_database"))
                    if parent_kind in parents:
                        value = [parents[parent_kind]]
                    else:
                        value = value if isinstance(value, list) else ([] if value is None else [value])
                elif field.type == "person":
                    ids = value if isinstance(value, list) else [value]
                    value = [i for i in ids if i in {m.id for m in board.members}]
                elif field.source_field == "list_id" and field.type == "select":
                    value = next((item.name for item in board.lists if item.id == value), value)
                elif field.source_field == "label_ids" and field.type == "multi_select":
                    labels = {item.id: item.name for item in board.labels}
                    value = list(dict.fromkeys(labels.get(i, i) for i in value))
                elif isinstance(value, list) and (field.source_field == "attachments" or
                                                  any(isinstance(i, dict) for i in value)):
                    if field.source_field == "attachments":
                        value = [i["url"] for i in value]
                        if field.type == "text":
                            value = "\n".join(value)
                        elif field.type == "url" and len(value) <= 1:
                            value = value[0] if value else None
                        else:
                            raise PlanError(f"{record.id}: {field.target_property} cannot hold all attachment links")
                    else:
                        raise PlanError(f"{record.id}: {field.target_property} cannot hold nested records")
                group = "relations" if field.type == "relation" else "values"
                page[group][field.target_property] = value
            for prop in schemas.get(entity.target_database, {}).values():
                fields = page["relations"] if prop["type"] == "relation" else page["values"]
                if prop.get("required") and fields.get(prop["name"]) in (None, "", []):
                    raise PlanError(f"{record.id}: required target property {prop['name']} is empty")
            pages.append(page)
        ids = [page["external_id"] for page in pages]
        if len(ids) != len(set(ids)):
            raise PlanError(f"{entity.source}: duplicate external ids")
        result[entity.source] = pages
    return result
