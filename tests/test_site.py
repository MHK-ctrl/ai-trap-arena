"""The site must build from data, stay self-contained, and not leak answers."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from arena.leaderboard.build_site import build_site
from arena.runners import enabled_models

LINK_RE = re.compile(r'href="([^"]+)"')


def build(project: Path) -> list[Path]:
    settings = yaml.safe_load((project / "config" / "settings.yaml").read_text(encoding="utf-8"))
    models = enabled_models(yaml.safe_load((project / "config" / "models.yaml").read_text(encoding="utf-8")))
    return build_site(
        project / "docs",
        project / "data",
        models=models,
        settings=settings,
        gold_path=project / "data" / "gold" / "answers.jsonl",
    )


def test_build_writes_every_page(scored_day: Path) -> None:
    written = build(scored_day)
    names = {p.name for p in written}
    assert {"index.html", "today.html", "methodology.html", "test-your-ai.html"} <= names
    assert (scored_day / "docs" / "assets" / "style.css").exists()
    assert (scored_day / "docs" / "models").is_dir()
    assert len(list((scored_day / "docs" / "models").glob("*.html"))) == 4


def test_demo_data_is_labelled_on_every_page(scored_day: Path) -> None:
    build(scored_day)
    pages = list((scored_day / "docs").rglob("*.html"))
    assert len(pages) >= 8
    for page in pages:
        assert "DEMO DATA" in page.read_text(encoding="utf-8"), page.name


def test_today_page_hides_answers(scored_day: Path) -> None:
    build(scored_day)
    today = (scored_day / "docs" / "today.html").read_text(encoding="utf-8")
    assert "was first published in 1987" not in today
    assert "fictional" in today.lower()


def test_pages_have_no_external_scripts_or_styles(scored_day: Path) -> None:
    build(scored_day)
    for path in (scored_day / "docs").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text.lower(), path
        assert 'src="http' not in text, path
        assert 'rel="stylesheet" href="http' not in text, path


def test_internal_links_resolve(scored_day: Path) -> None:
    build(scored_day)
    docs = scored_day / "docs"
    for path in docs.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for href in LINK_RE.findall(text):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = (path.parent / href.split("#")[0]).resolve()
            assert target.exists(), f"{path.name} links to missing {href}"


def test_model_page_shows_unedited_example(scored_day: Path) -> None:
    build(scored_day)
    page = (scored_day / "docs" / "models" / "mock-bluffer.html").read_text(encoding="utf-8")
    assert "Example bluffs" in page
    assert "Scorer rationale" in page


def test_build_requires_a_scored_day(project: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        build(project)
