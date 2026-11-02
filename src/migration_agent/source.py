"""Read and check a board export.

Keep source records in typed models for later mapping.
Warn about unknown people so their cards are not lost.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError


class SourceError(ValueError):
    """The source file or one of its records is not valid."""


class SourceRecord(BaseModel):
    """Keep the source id and reject fields we cannot keep."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1)


class Member(SourceRecord):
    """Describe a person on the board."""

    name: str
    email: str


class Label(SourceRecord):
    """Describe a tag, even when another tag has the same name."""

    name: str
    color: str | None = None


class BoardList(SourceRecord):
    """Describe a task status in board order."""

    name: str


class ChecklistItem(SourceRecord):
    """Describe one small task and whether it is done."""

    name: str
    done: bool = False


class Checklist(SourceRecord):
    """Group the small tasks on a card."""

    name: str
    items: list[ChecklistItem] = Field(default_factory=list)


class Comment(SourceRecord):
    """Keep a note, its author and its time."""

    text: str
    member_id: str
    created_at: datetime


class Attachment(SourceRecord):
    """Keep a link without copying a file."""

    name: str
    url: HttpUrl


class Card(SourceRecord):
    """Keep a task and all of its linked source records."""

    name: str
    list_id: str
    description: str = ""
    due: datetime | None = None
    member_ids: list[str] = Field(default_factory=list)
    label_ids: list[str] = Field(default_factory=list)
    checklists: list[Checklist] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)


class Board(SourceRecord):
    """Keep one project and its lists, cards, tags and people."""

    name: str
    description: str = ""
    closed: bool = False
    lists: list[BoardList]
    cards: list[Card]
    labels: list[Label]
    members: list[Member]


class Export(BaseModel):
    """Hold the checked boards, file hash and source warnings."""

    model_config = ConfigDict(extra="forbid")
    boards: list[Board]
    source_hash: str
    warnings: list[str] = Field(default_factory=list)


class _ExportData(BaseModel):
    """Check only the fields that belong in the source file."""

    model_config = ConfigDict(extra="forbid")
    boards: list[Board]


def read_export(path: str | Path) -> Export:
    """Read the file and report bad fields with their record ids."""
    source_path = Path(path)
    try:
        raw = source_path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SourceError(f"{source_path}: export file: {exc}") from exc
    try:
        # JSON mode accepts date strings while keeping numbers and names strict.
        checked = _ExportData.model_validate_json(raw)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            record = data
            ids = []
            for part in error["loc"]:
                if isinstance(record, dict) and "id" in record:
                    ids.append(str(record["id"]))
                if isinstance(record, dict):
                    record = record.get(part)
                elif isinstance(record, list) and isinstance(part, int):
                    record = record[part]
                else:
                    break
            field = ".".join(str(part) for part in error["loc"])
            problems.append(f"record {' / '.join(ids) or 'export'}, field {field}: {error['msg']}")
        raise SourceError(f"{source_path}: {'; '.join(problems)}") from exc
    warnings = []
    for board in checked.boards:
        known_members = {member.id for member in board.members}
        for card in board.cards:
            for member_id in card.member_ids:
                if member_id not in known_members:
                    warnings.append(f"Board {board.id}, card {card.id}: unknown member {member_id}")
            for comment in card.comments:
                if comment.member_id not in known_members:
                    warnings.append(
                        f"Board {board.id}, card {card.id}, comment {comment.id}: "
                        f"unknown member {comment.member_id}"
                    )
    return Export(boards=checked.boards, source_hash=hashlib.sha256(raw).hexdigest(), warnings=warnings)
