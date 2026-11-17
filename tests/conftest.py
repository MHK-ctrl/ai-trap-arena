"""Shared fixtures. No test in this suite touches the network."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from arena.trapgen.verifier import Check, Verification

REPO = Path(__file__).resolve().parents[1]


class FakeVerifier:
    """Deterministic stand-in for the four-source verifier."""

    def __init__(self, status: str = "clear", collision_names: set[str] | None = None) -> None:
        self.status = status
        self.collision_names = collision_names or set()
        self.calls: list[tuple[str, str]] = []

    def verify(self, name: str, category: str) -> Verification:
        self.calls.append((name, category))
        if name in self.collision_names:
            return Verification(
                name=name,
                category=category,
                status="collision",
                checks=[Check("wikipedia", "q", "found", "article similarity 1.00")],
            )
        return Verification(
            name=name,
            category=category,
            status=self.status,
            checks=[Check("pypi", "q", "not_found", "404"), Check("npm", "q", "not_found", "404")],
        )


@pytest.fixture()
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A throwaway repository root with the real config and gold set."""
    root = tmp_path / "arena-root"
    root.mkdir()
    shutil.copytree(REPO / "config", root / "config")
    (root / "data" / "gold").mkdir(parents=True)
    shutil.copy(REPO / "data" / "gold" / "answers.jsonl", root / "data" / "gold" / "answers.jsonl")
    (root / "data" / "submissions").mkdir(parents=True)
    shutil.copy(
        REPO / "data" / "submissions" / "schema.json", root / "data" / "submissions" / "schema.json"
    )
    return root


@pytest.fixture()
def scored_day(project: Path) -> Path:
    """Run the whole pipeline once against the mock models, inside the temp root."""
    from arena import cli

    original = cli.ROOT
    cli.ROOT = project
    try:
        assert cli.main(["today", "--date", "2026-02-03", "--offline", "--per-category", "2"]) == 0
        assert cli.main(["run", "--date", "2026-02-03"]) == 0
    finally:
        cli.ROOT = original
    return project


def read_day(root: Path, day: str) -> dict:
    return json.loads((root / "data" / "daily" / day / "traps.json").read_text(encoding="utf-8"))
