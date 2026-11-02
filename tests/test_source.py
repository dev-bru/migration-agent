"""Check the made-up export and failures at the file boundary."""

import hashlib
import json
from pathlib import Path

import pytest

from migration_agent.source import SourceError, read_export

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/acme_board.json"


def test_sample_counts_and_edge_cases():
    """Keep all records and all the required sample cases."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    export = read_export(FIXTURE)
    assert len(export.boards) == len(data["boards"]) == 1
    board = export.boards[0]
    raw = data["boards"][0]
    for field in ("cards", "lists", "labels", "members"):
        assert len(getattr(board, field)) == len(raw[field])
    assert len(board.cards) == 2
    assert len(board.lists) == 3
    assert len(board.labels) == 3
    assert len(board.members) == 2
    for field in ("checklists", "comments", "attachments"):
        assert sum(len(getattr(card, field)) for card in board.cards) == sum(
            len(card[field]) for card in raw["cards"]
        )
    assert sum(len(card.comments) for card in board.cards) == 2
    assert sum(len(card.attachments) for card in board.cards) == 2
    assert any(card.due is None for card in board.cards)
    assert len({label.name for label in board.labels}) < len(board.labels)
    assert any(not any(card.list_id == item.id for card in board.cards) for item in board.lists)
    assert any(sum(len(check.items) for check in card.checklists) == 3 for card in board.cards)
    assert any(len(card.comments) == 2 and len(card.attachments) == 2 for card in board.cards)


def test_unknown_member_is_kept_and_warned():
    """Keep the card and name the unknown person in a warning."""
    export = read_export(FIXTURE)
    card = export.boards[0].cards[1]
    assert card.member_ids == ["member-missing"]
    assert export.warnings == [
        f"Board board-acme, card {card.id}: unknown member member-missing"
    ]


def test_repeat_reads_and_byte_hash(tmp_path):
    """Return equal models and hash the original file bytes."""
    first = read_export(FIXTURE)
    assert first == read_export(FIXTURE)
    assert first.source_hash == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    path = tmp_path / "spaced.json"
    path.write_bytes(FIXTURE.read_bytes() + b"\n")
    second = read_export(path)
    assert second.boards == first.boards
    assert second.source_hash != first.source_hash


@pytest.mark.parametrize("field,value", [("name", None), ("name", 7), ("member_ids", "wrong")])
def test_bad_card_names_file_record_and_field(tmp_path, field, value):
    """Point the user to the bad card and field."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    card = data["boards"][0]["cards"][0]
    if value is None:
        del card[field]
    else:
        card[field] = value
    path = tmp_path / "bad-card.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SourceError) as error:
        read_export(path)
    for text in (path.name, card["id"], field):
        assert text in str(error.value)


def test_bad_nested_record_names_its_id(tmp_path):
    """Name the nested record too when its field is bad."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["boards"][0]["cards"][0]["checklists"][0]["items"][0]
    item["done"] = "yes"
    path = tmp_path / "bad-item.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SourceError) as error:
        read_export(path)
    for text in (path.name, "card-seeds", item["id"], "done"):
        assert text in str(error.value)


@pytest.mark.parametrize("raw", [b"{", b"\xff", b"null", b'{"boards": {}}', b"{}"])
def test_bad_file_is_source_error(tmp_path, raw):
    """Turn bad JSON, text and top-level shapes into source errors."""
    path = tmp_path / "broken.json"
    path.write_bytes(raw)
    with pytest.raises(SourceError, match="broken.json"):
        read_export(path)


def test_missing_file_is_source_error(tmp_path):
    """Name the missing source file."""
    with pytest.raises(SourceError, match="missing.json"):
        read_export(tmp_path / "missing.json")


def test_bad_date_and_link_are_rejected(tmp_path):
    """Check date and link text before later code uses it."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    card = data["boards"][0]["cards"][0]
    card["due"] = "next week"
    card["attachments"][0]["url"] = "not a link"
    path = tmp_path / "bad-values.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SourceError) as error:
        read_export(path)
    assert "due" in str(error.value)
    assert "link-guide" in str(error.value)
    assert "url" in str(error.value)


def test_unknown_comment_author_is_warned(tmp_path):
    """Warn about unknown comment authors without losing the note."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["boards"][0]["cards"][0]["comments"][0]["member_id"] = "unknown-author"
    path = tmp_path / "unknown-author.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    export = read_export(path)
    assert len(export.boards[0].cards[0].comments) == 2
    assert any("comment-one" in warning and "unknown-author" in warning for warning in export.warnings)
