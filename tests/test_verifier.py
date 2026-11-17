"""Verifier behaviour with the network mocked. No HTTP in the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from arena.trapgen.verifier import Verifier, normalise, similarity, slugify


def make_verifier(tmp_path: Path, monkeypatch, handler) -> Verifier:
    verifier = Verifier(cache_path=tmp_path / "cache.json", timeout=1)
    monkeypatch.setattr(verifier, "_get_json", handler)
    return verifier


def empty_source(url: str):
    """Registries answer 404, search APIs answer 200 with no results."""
    if "openlibrary.org" in url:
        return 200, {"docs": []}
    if "wikipedia.org" in url:
        return 200, {"query": {"search": []}}
    return 404, None


def test_clear_when_no_source_knows_the_name(tmp_path: Path, monkeypatch) -> None:
    def handler(url: str):
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    result = verifier.verify("The Glass Meridian", "books")
    assert result.status == "clear"
    assert {c.source for c in result.checks} == {"pypi", "npm", "openlibrary", "wikipedia"}
    assert all(c.status == "not_found" for c in result.checks)


def test_existing_package_is_a_collision(tmp_path: Path, monkeypatch) -> None:
    def handler(url: str):
        if "pypi.org" in url:
            return 200, {"info": {"version": "1.2.3"}}
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    result = verifier.verify("requests", "software")
    assert result.status == "collision"
    assert any(c.source == "pypi" and c.status == "found" for c in result.checks)


def test_near_title_in_open_library_is_a_collision(tmp_path: Path, monkeypatch) -> None:
    def handler(url: str):
        if "openlibrary.org" in url:
            return 200, {"docs": [{"title": "The Glass Meridian and Other Stories"}]}
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    assert verifier.verify("The Glass Meridian", "books").status == "collision"


def test_unrelated_search_results_are_not_a_collision(tmp_path: Path, monkeypatch) -> None:
    def handler(url: str):
        if "wikipedia.org" in url:
            return 200, {"query": {"search": [{"title": "Meridian (astronomy)"}]}}
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    assert verifier.verify("The Glass Meridian", "books").status == "clear"


def test_network_error_is_reported_not_hidden(tmp_path: Path, monkeypatch) -> None:
    def handler(url: str):
        raise ConnectionError("timed out")

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    result = verifier.verify("Anything At All", "books")
    assert result.status == "error"
    assert all(c.status == "error" for c in result.checks)


def test_results_are_cached(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def handler(url: str):
        calls["n"] += 1
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    verifier.verify("Cache Me", "events")
    first = calls["n"]
    verifier.verify("Cache Me", "events")
    assert calls["n"] == first, "a cached verification must not hit the network again"

    reopened = Verifier(cache_path=tmp_path / "cache.json")

    def explode(url: str):
        raise AssertionError("cache was not used")

    monkeypatch.setattr(reopened, "_get_json", explode)
    assert reopened.verify("Cache Me", "events").status == "clear"


def test_slug_and_similarity_helpers() -> None:
    assert slugify("The Glass Meridian") == "the-glass-meridian"
    assert normalise("The   Glass, Meridian!") == "the glass meridian"
    assert similarity("The Glass Meridian", "the glass meridian") == 1.0
    assert similarity("The Glass Meridian", "The Glass Meridian and Other Stories") == 1.0
    assert similarity("The Glass Meridian", "Meridian") < 0.9


@pytest.mark.parametrize("name", ["pyquill", "Vantorre Data Retention Act"])
def test_names_are_slugified_for_registries(tmp_path: Path, monkeypatch, name: str) -> None:
    seen: list[str] = []

    def handler(url: str):
        seen.append(url)
        return empty_source(url)

    verifier = make_verifier(tmp_path, monkeypatch, handler)
    verifier.verify(name, "software")
    assert any(slugify(name) in url for url in seen)
