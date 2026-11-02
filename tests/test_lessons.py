"""Run every teaching script offline and check its learning guide."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = [
    ("01_fde.py", "FDE: plan -> signoff -> dry-run -> run -> validate -> report"),
    ("02_source.py", "Source: 2 cards"),
    ("03_mapping.py", "Mapping: 4 entities; human answers needed"),
    ("04_dry_run.py", "Dry run: zero target writes"),
    ("05_batches.py", "Resume: 2 tasks, no duplicates"),
    ("06_validation_report.py", "Validation: all checks pass; report saved"),
]


@pytest.mark.parametrize("name,expected", LESSONS)
def test_standalone_fake_lesson(name, expected):
    """Execute each lesson from a fresh process without settings or model services."""
    path = ROOT / "lessons" / name
    text = path.read_text(encoding="utf-8")
    comments = text.split('"""', 1)[0].strip().splitlines()
    assert 1 <= len(comments) <= 5
    assert all(line.startswith("#") for line in comments)
    assert "What you will learn" in comments[0]
    assert "Quiz:" in text and "Expected:" in text and "Run:" in text
    result = subprocess.run([sys.executable, str(path), "--fake"], cwd=ROOT,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected in result.stdout
    if name.startswith("05"):
        assert "Forced crash" in result.stdout


def test_target_walkthrough_and_readme():
    """Keep the server lesson and its runnable instructions available."""
    for name in ("lessons/07_mcp_target_server.md", "lessons/README.md", "README.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "Quiz" in text and "Expected" in text
        assert "src/migration_agent/" in text
