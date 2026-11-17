"""Existence checks for invented items.

A trap is only publishable if four independent sources have no record of it:

* PyPI        - `/pypi/<slug>/json` returns 404
* npm         - `registry.npmjs.org/<slug>` returns 404
* Open Library - no title in the search results is close to the invented title
* Wikipedia    - no article title is close to the invented name

"Close" is a similarity ratio on normalised strings, so a near-miss (the real book with an
extra word) is treated as a collision rather than a pass. Results are cached on disk, because
a day's set never changes once generated.

Network access lives here and nowhere else in the package. Tests inject a fake verifier, and
the CLI has `--offline` for local demos, which marks traps as unverified instead of guessing.
"""

from __future__ import annotations

import difflib
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = "ai-trap-arena/0.1 (+https://github.com/MHK-ctrl/ai-trap-arena)"


def _ssl_context() -> ssl.SSLContext:
    """Use certifi when present.

    Some interpreter builds (notably the macOS framework build) ship without a usable CA
    bundle, which turns every verification into a certificate error. certifi is a declared
    dependency, and the default context is kept as a fallback for environments that manage
    certificates themselves.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - certifi is a declared dependency
        return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


@dataclass
class Check:
    source: str
    query: str
    status: str  # "not_found" | "found" | "error"
    detail: str = ""

    def to_dict(self) -> dict:
        return {"source": self.source, "query": self.query, "status": self.status, "detail": self.detail}


@dataclass
class Verification:
    name: str
    category: str
    status: str  # "clear" | "collision" | "error"
    checks: list[Check] = field(default_factory=list)

    @property
    def is_clear(self) -> bool:
        return self.status == "clear"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
        }


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    a, b = normalise(a), normalise(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # A short name contained in a longer title is still a collision: "the glass meridian"
    # inside "the glass meridian and other stories" is the same book.
    if len(a) >= 8 and a in b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class Verifier:
    """Checks invented names against real registries and encyclopedias."""

    def __init__(
        self,
        cache_path: Path | str | None = None,
        timeout: float = 10.0,
        near_match_ratio: float = 0.92,
        sources: tuple[str, ...] = ("pypi", "npm", "openlibrary", "wikipedia"),
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self.timeout = timeout
        self.near_match_ratio = near_match_ratio
        self.sources = sources
        self.user_agent = user_agent
        self._cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))

    # -- public API ---------------------------------------------------------
    def verify(self, name: str, category: str) -> Verification:
        key = f"{category}|{name}"
        if key in self._cache:
            cached = self._cache[key]
            return Verification(
                name=name,
                category=category,
                status=cached["status"],
                checks=[Check(**c) for c in cached["checks"]],
            )

        checks: list[Check] = []
        for source in self.sources:
            checks.append(getattr(self, f"_check_{source}")(name))

        found = [c for c in checks if c.status == "found"]
        errors = [c for c in checks if c.status == "error"]
        if found:
            status = "collision"
        elif errors:
            status = "error"
        else:
            status = "clear"

        result = Verification(name=name, category=category, status=status, checks=checks)
        if status != "error":
            # Never cache a transient failure: a DNS blip or a missing CA bundle must not
            # poison a name forever. Clear and collision verdicts are stable, so they cache.
            self._cache[key] = result.to_dict()
            self._save()
        return result

    # -- sources ------------------------------------------------------------
    def _get_json(self, url: str) -> tuple[int, dict | list | None]:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout, context=SSL_CONTEXT
            ) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise ConnectionError(str(exc)) from exc

    def _check_pypi(self, name: str) -> Check:
        slug = slugify(name)
        query = f"https://pypi.org/pypi/{slug}/json"
        try:
            status, payload = self._get_json(query)
        except ConnectionError as exc:
            return Check("pypi", query, "error", str(exc)[:200])
        if status == 200:
            version = ""
            if isinstance(payload, dict):
                version = str(payload.get("info", {}).get("version", ""))
            return Check("pypi", query, "found", f"package exists (version {version or 'unknown'})")
        if status == 404:
            return Check("pypi", query, "not_found", "404 no such package")
        return Check("pypi", query, "error", f"HTTP {status}")

    def _check_npm(self, name: str) -> Check:
        slug = slugify(name)
        query = f"https://registry.npmjs.org/{slug}"
        try:
            status, payload = self._get_json(query)
        except ConnectionError as exc:
            return Check("npm", query, "error", str(exc)[:200])
        if status == 200:
            detail = "package exists"
            if isinstance(payload, dict) and payload.get("name"):
                detail = f"package exists ({payload['name']})"
            return Check("npm", query, "found", detail)
        if status == 404:
            return Check("npm", query, "not_found", "404 no such package")
        return Check("npm", query, "error", f"HTTP {status}")

    def _check_openlibrary(self, name: str) -> Check:
        query = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(
            {"title": f'"{name}"', "limit": 10}
        )
        try:
            status, payload = self._get_json(query)
        except ConnectionError as exc:
            return Check("openlibrary", query, "error", str(exc)[:200])
        if status != 200 or not isinstance(payload, dict):
            return Check("openlibrary", query, "error", f"HTTP {status}")
        best, best_title = 0.0, ""
        for doc in payload.get("docs", [])[:10]:
            title = str(doc.get("title", ""))
            score = similarity(name, title)
            if score > best:
                best, best_title = score, title
        if best >= self.near_match_ratio:
            return Check("openlibrary", query, "found", f"title match {best:.2f}: {best_title}")
        return Check("openlibrary", query, "not_found", f"no title above {self.near_match_ratio:.2f}")

    def _check_wikipedia(self, name: str) -> Check:
        query = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": f'"{name}"',
                "srlimit": 5,
                "format": "json",
            }
        )
        try:
            status, payload = self._get_json(query)
        except ConnectionError as exc:
            return Check("wikipedia", query, "error", str(exc)[:200])
        if status != 200 or not isinstance(payload, dict):
            return Check("wikipedia", query, "error", f"HTTP {status}")
        best, best_title = 0.0, ""
        for result in payload.get("query", {}).get("search", []):
            title = str(result.get("title", ""))
            score = similarity(name, title)
            if score > best:
                best, best_title = score, title
        if best >= self.near_match_ratio:
            return Check("wikipedia", query, "found", f"article similarity {best:.2f}: {best_title}")
        return Check("wikipedia", query, "not_found", f"no article above {self.near_match_ratio:.2f}")

    # -- cache --------------------------------------------------------------
    def _save(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.cache_path)
