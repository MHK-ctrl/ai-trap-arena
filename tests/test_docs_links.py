"""Internal links in the docs and the built site must resolve."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    names = ["README.md", "METHODOLOGY.md", "ETHICS.md", "CONTRIBUTING.md", "PLAN.md", "blog/post.md"]
    return [REPO / name for name in names if (REPO / name).exists()]


def test_internal_markdown_links_resolve() -> None:
    missing = []
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            local = target.split("#")[0]
            if not local:
                continue
            if not (path.parent / local).resolve().exists():
                missing.append(f"{path.relative_to(REPO)} -> {target}")
    assert not missing, missing


def test_required_documents_exist() -> None:
    for name in ["README.md", "METHODOLOGY.md", "ETHICS.md", "CONTRIBUTING.md", "PLAN.md"]:
        assert (REPO / name).exists(), name


def test_no_placeholder_text_in_documents() -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8").lower()
        assert "lorem ipsum" not in text, path
        assert "todo:" not in text, path


def test_built_site_has_no_dead_internal_links() -> None:
    docs = REPO / "docs"
    if not (docs / "index.html").exists():
        return
    missing = []
    for page in docs.rglob("*.html"):
        for href in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8")):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if not (page.parent / href.split("#")[0]).resolve().exists():
                missing.append(f"{page.relative_to(REPO)} -> {href}")
    assert not missing, missing
