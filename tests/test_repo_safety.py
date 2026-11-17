"""Repository-level guarantees: no secrets, no unverified traps, no leftovers."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"""(?i)api[_-]?key["']?\s*[:=]\s*["'][A-Za-z0-9/+_-]{16,}"""),
)

TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".jsonl", ".toml", ".txt", ".html", ".css"}


def repo_files() -> list[Path]:
    skip = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
    return [
        path
        for path in REPO.rglob("*")
        if path.is_file() and not (set(path.relative_to(REPO).parts) & skip)
    ]


def test_no_secret_shaped_strings_are_committed() -> None:
    offenders = []
    for path in repo_files():
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO)}: {pattern.pattern}")
    assert not offenders, offenders


def test_no_env_files() -> None:
    assert [p for p in repo_files() if p.name.startswith(".env")] == []


def test_daily_traps_are_verified_and_fictional() -> None:
    trap_files = sorted((REPO / "data" / "daily").glob("*/traps.json"))
    assert trap_files, "no trap data committed"
    for path in trap_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["traps"], path
        for trap in data["traps"]:
            assert trap["label"] == "FICTIONAL", trap["id"]
            assert trap["kind"] == "trap"
            assert trap["why_fictional"].strip()
            status = trap["verification"]["status"]
            assert status == "clear", f"{trap['id']} is {status} and must not be committed"
            sources = {check["source"] for check in trap["verification"]["checks"]}
            assert sources == {"pypi", "npm", "openlibrary", "wikipedia"}, trap["id"]
            assert all(
                check["status"] == "not_found" for check in trap["verification"]["checks"]
            ), trap["id"]


def test_no_trap_name_is_a_control() -> None:
    controls = {
        control["name"].lower()
        for path in (REPO / "data" / "daily").glob("*/traps.json")
        for control in json.loads(path.read_text(encoding="utf-8"))["controls"]
    }
    for path in (REPO / "data" / "daily").glob("*/traps.json"):
        for trap in json.loads(path.read_text(encoding="utf-8"))["traps"]:
            assert trap["name"].lower() not in controls


def test_no_placeholder_markers_in_code_or_data() -> None:
    needles = ("TO" + "DO", "FIX" + "ME", "lorem " + "ipsum", "XXX")
    offenders = []
    for path in repo_files():
        if path.suffix not in {".py", ".yaml", ".yml", ".json", ".jsonl", ".toml", ".css"}:
            continue
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in needles:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO)}: {needle}")
    assert not offenders, offenders
