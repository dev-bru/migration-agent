# Show the planned data before any target writes.
# Use the same transform as the real migration.
# A preview needs no human sign-off.
"""Build a read-only preview of a migration."""

import json

from migration_agent.transform import transform


async def dry_run(export, plan, target) -> dict:
    """Count planned records and show empty fields, warnings and samples."""
    mapped = transform(export, plan, await target.list_databases())
    result = {"entities": {name: {
        "create": len(records),
        "empty_fields": sorted({key for record in records for group in ("values", "relations")
                                for key, value in record[group].items() if value in (None, "", [])}),
        "preview": records[:3],
    } for name, records in mapped.items()}, "warnings": list(export.warnings)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result
