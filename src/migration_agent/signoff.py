# Record human approval of the exact saved plan.
# Keep unanswered questions from reaching a real run.
# Check the saved hash again before any migration writes.
"""Record human approval of the exact saved plan.

Keep unanswered questions from reaching a real run.
Check the saved hash again before any migration writes.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from migration_agent.mapping import read_plan


class SignoffError(ValueError):
    """Explain why human approval is missing or no longer valid."""


def signoff(plan_path: str | Path, signoff_path: str | Path, signed_by: str) -> dict:
    """Save approval only when every question has an answer."""
    plan_path = Path(plan_path)
    proposal = read_plan(plan_path)
    unanswered = [q.id for q in proposal.questions if not q.answer or not q.answer.strip()]
    if unanswered:
        raise SignoffError("unanswered questions: " + ", ".join(unanswered))
    if not signed_by.strip():
        raise SignoffError("signed_by: type the human reviewer's name")
    proposal.signed_off = True
    plan_path.write_text(proposal.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    approval = dict(plan_hash=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                    signed_by=signed_by.strip(), signed_at=datetime.now(timezone.utc).isoformat())
    destination = Path(signoff_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(approval, indent=2) + "\n", encoding="utf-8", newline="\n")
    return approval


def require_signoff(plan_path: str | Path, signoff_path: str | Path) -> None:
    """Refuse a real run unless the approval matches the plan bytes."""
    try:
        approval = json.loads(Path(signoff_path).read_text(encoding="utf-8"))
        plan_hash = hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()
    except (OSError, ValueError):
        raise SignoffError("signoff.json is missing or unreadable; sign off the plan before run") from None
    if (not isinstance(approval, dict) or approval.get("plan_hash") != plan_hash
            or not isinstance(approval.get("signed_by"), str) or not approval["signed_by"].strip()
            or not approval.get("signed_at")):
        raise SignoffError("signoff.json does not match the plan or has no reviewer; sign off again")
