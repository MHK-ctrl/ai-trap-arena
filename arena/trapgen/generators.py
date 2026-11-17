"""Seeded trap generators.

Everything is derived from the date and `seed_salt`, so the same day always produces the same
candidates in the same order. Verification can therefore be cached, replayed and audited: if
a trap is rejected as a real item, the next day's run reaches the same decision.

A candidate is only accepted after `Verifier` reports it clear on all four sources. In strict
mode (the default, and the only mode the daily job uses) a network error aborts the day rather
than publishing something unverified. `allow_unverified=True` exists for tests and for
`arena today --offline`, and stamps every trap with `verification.status == "unverified"`.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date as Date
from itertools import count

from arena.prompts import build_question
from arena.trapgen.codes import CATEGORY_CODES
from arena.trapgen.controls import Control, pick_controls

CATEGORIES: tuple[str, ...] = (
    "books",
    "laws",
    "software",
    "scientists",
    "events",
    "science_terms",
)

CATEGORY_TITLES: dict[str, str] = {
    "books": "Fictional books",
    "laws": "Fictional laws and regulations",
    "software": "Fictional software libraries and functions",
    "scientists": "Fictional scientists and discoveries",
    "events": "Fictional historical events",
    "science_terms": "Fictional scientific terms",
}


class VerificationError(RuntimeError):
    """Raised when a trap cannot be verified and strict mode is on."""


@dataclass(frozen=True)
class Trap:
    id: str
    category: str
    name: str
    question: str
    why_fictional: str
    verification: dict
    fields: dict = field(default_factory=dict)
    label: str = "FICTIONAL"
    kind: str = "trap"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "question": self.question,
            "why_fictional": self.why_fictional,
            "verification": self.verification,
            "label": self.label,
            "kind": self.kind,
        }


@dataclass
class DaySet:
    date: str
    traps: list[Trap]
    controls: list[Control]
    demo: bool = False

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "demo": self.demo,
            "traps": [t.to_dict() for t in self.traps],
            "controls": [c.to_dict() for c in self.controls],
        }

    def questions(self) -> list[dict]:
        out = [
            {
                "id": t.id,
                "kind": "trap",
                "category": t.category,
                "question": t.question,
                "name": t.name,
                "fields": t.fields,
            }
            for t in self.traps
        ]
        out += [
            {
                "id": c.id,
                "kind": "control",
                "category": c.category,
                "question": c.question,
                "name": c.name,
                "fact": c.fact,
            }
            for c in self.controls
        ]
        return out


# ---------------------------------------------------------------------------
# Name material. Deliberately uncommon parts: the goal is names that sound plausible and
# collide with nothing. Surnames are invented compounds rather than common real surnames.
# ---------------------------------------------------------------------------

BOOK_ADJECTIVES = (
    "Crimson",
    "Silent",
    "Gilded",
    "Hollow",
    "Wintry",
    "Amber",
    "Fractured",
    "Luminous",
    "Quiet",
    "Salt",
    "Iron",
    "Velvet",
    "Paper",
    "Glass",
    "Northern",
    "Borrowed",
    "Unwritten",
    "Half-Light",
)
BOOK_NOUNS = (
    "Meridian",
    "Orchard",
    "Archive",
    "Compass",
    "Kestrel",
    "Lantern",
    "Estuary",
    "Cartographer",
    "Moth",
    "Harbor",
    "Atlas",
    "Threshold",
    "Almanac",
    "Passage",
)
BOOK_FIRST = (
    "Odalys",
    "Corin",
    "Mirela",
    "Brennick",
    "Ilse",
    "Tavish",
    "Nessa",
    "Quillon",
    "Marit",
    "Elsbeth",
    "Dorian",
    "Perrin",
)
BOOK_LAST = (
    "Vasterholt",
    "Quenby",
    "Brannock",
    "Melverton",
    "Ostrey",
    "Dainsworth",
    "Larrowby",
    "Corvel",
    "Ashfen",
    "Wrenmoor",
)
LAW_PLACES = (
    "Vantorre",
    "Brindlewick",
    "Marrowgate",
    "Kellwater",
    "Ostrey",
    "Sable Harbor",
    "Dunmarch",
    "Larrow",
    "Pellworth",
    "Cindermoor",
)
LAW_TOPICS = (
    "Data Retention",
    "Coastal Shipping",
    "Railway Safety",
    "Textile Standards",
    "Grain Storage",
    "Telegraph Licensing",
    "Mining Ventilation",
    "Inland Fisheries",
    "Parcel Tariffs",
    "Public Weights",
)
SOFTWARE_STEMS = (
    "quill",
    "sedgemill",
    "fluxkettle",
    "peat",
    "bramble",
    "cinder",
    "dovetail",
    "nettle",
    "marl",
    "shale",
    "wisp",
    "gantry",
)
SOFTWARE_PREFIXES = ("py", "", "go", "rs")
FUNCTION_VERBS = (
    "resolve",
    "coalesce",
    "fracture",
    "align",
    "harvest",
    "stabilize",
    "weave",
    "probe",
)
FUNCTION_NOUNS = (
    "tide_map",
    "shard_keys",
    "amber_index",
    "kite_buffer",
    "loom_state",
    "drift_table",
    "wick_queue",
    "ember_cache",
)
SCIENTIST_FIRST = (
    "Marisol",
    "Tobias",
    "Ines",
    "Corin",
    "Odalys",
    "Kestrel",
    "Brennick",
    "Ilse",
    "Tavish",
    "Mirela",
    "Quillon",
    "Nessa",
)
SCIENTIST_LAST = BOOK_LAST
TERM_ROOTS = ("quellion", "vesper", "brannic", "solver", "nerrith", "corvin", "thalar")
TERM_SUFFIXES = (
    "ic decay",
    "ine cascade",
    " drift",
    "ic flux",
    "ine hysteresis",
    "ic resonance",
)
EVENT_PLACES = (
    "Vantorre",
    "Brindlewick",
    "Marrowgate",
    "Kellwater",
    "Ostrey",
    "Dunmarch",
    "Pellworth",
    "Cindermoor",
    "Larrow",
    "Sable Harbor",
)
EVENT_FORMS = ("the Treaty of {place}", "the {place} Convention", "the {place} Incident", "the {place} Accord")


def day_seed(day: Date, category: str, salt: str) -> int:
    material = f"{salt}:{day.isoformat()}:{category}".encode()
    return int(hashlib.sha256(material).hexdigest()[:16], 16)


def rng_for(day: Date, category: str, salt: str) -> random.Random:
    return random.Random(day_seed(day, category, salt))


def article_for(word: str) -> str:
    """`A` or `An` by sound of the first letter, so titles read like titles."""
    return "An" if word[:1].lower() in "aeiou" else "A"


def _book_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    style = rng.randrange(3)
    adjective = rng.choice(BOOK_ADJECTIVES)
    noun = rng.choice(BOOK_NOUNS)
    if style == 0:
        title = f"The {adjective} {noun}"
    elif style == 1:
        title = f"{noun} of the {adjective} {rng.choice(BOOK_NOUNS)}"
    else:
        title = f"{article_for(adjective)} {adjective} {noun}"
    author = f"{rng.choice(BOOK_FIRST)} {rng.choice(BOOK_LAST)}"
    why = (
        "Invented title and author. No book with this title appears in Open Library, and no "
        "Wikipedia article carries the name."
    )
    return title, {"title": title, "author": author}, why


def _law_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    place = rng.choice(LAW_PLACES)
    topic = rng.choice(LAW_TOPICS)
    year = rng.randint(1834, 1959)
    style = rng.randrange(2)
    if style == 0:
        name = f"the {place} {topic} Act of {year}"
    else:
        number = rng.randint(11, 289)
        name = f"Regulation {number} of {year} on {topic} in {place}"
    why = (
        "Invented jurisdiction, instrument and year. The place does not exist, so no statute "
        "with this citation can exist."
    )
    return name, {"name": name}, why


def _software_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    lib = f"{rng.choice(SOFTWARE_PREFIXES)}{rng.choice(SOFTWARE_STEMS)}"
    fn = f"{rng.choice(FUNCTION_VERBS)}_{rng.choice(FUNCTION_NOUNS)}"
    why = (
        "Invented package and function name. The package is absent from PyPI and npm, so the "
        "function cannot be imported from it."
    )
    return lib, {"lib": lib, "fn": f"{lib}.{fn}"}, why


def _scientist_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    first = rng.choice(SCIENTIST_FIRST)
    last = rng.choice(SCIENTIST_LAST)
    term = f"{rng.choice(TERM_ROOTS)}{rng.choice(TERM_SUFFIXES)}"
    person = f"Dr. {first} {last}"
    why = (
        "Invented person and invented phenomenon. The name has no Wikipedia article and the "
        "term appears in no source."
    )
    return person, {"person": person, "term": term}, why


def _event_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    place = rng.choice(EVENT_PLACES)
    form = rng.choice(EVENT_FORMS)
    event = form.format(place=place)
    why = (
        "Invented place and invented event. No treaty, convention or incident with this name "
        "is recorded."
    )
    return event, {"event": event}, why


def _term_fields(rng: random.Random) -> tuple[str, dict[str, str], str]:
    term = f"{rng.choice(TERM_ROOTS)}{rng.choice(TERM_SUFFIXES)}"
    why = (
        "Invented term built from invented roots. It appears in no textbook, paper title or "
        "encyclopedia article."
    )
    return term, {"term": term}, why


BUILDERS = {
    "books": _book_fields,
    "laws": _law_fields,
    "software": _software_fields,
    "scientists": _scientist_fields,
    "events": _event_fields,
    "science_terms": _term_fields,
}


def candidates(day: Date, category: str, salt: str = "ai-trap-arena-v1"):
    """Endless deterministic stream of (name, fields, why) for one category."""
    rng = rng_for(day, category, salt)
    builder = BUILDERS[category]
    for _ in count():
        yield builder(rng)


def build_day(
    day: Date,
    verifier=None,
    *,
    per_category: int = 5,
    controls_per_category: int = 2,
    salt: str = "ai-trap-arena-v1",
    allow_unverified: bool = False,
    max_attempts: int = 80,
    demo: bool = False,
) -> DaySet:
    """Generate and verify one day's set.

    `verifier` must expose `verify(name, category) -> Verification`. Passing None with
    `allow_unverified=True` produces a local-only set with no evidence.
    """
    traps: list[Trap] = []
    for category in CATEGORIES:
        used: set[str] = set()
        produced = 0
        attempts = 0
        for name, fields, why in candidates(day, category, salt):
            if produced >= per_category or attempts >= max_attempts:
                break
            attempts += 1
            if name in used:
                continue
            used.add(name)

            if verifier is None:
                verification = {
                    "status": "unverified",
                    "checks": [],
                    "note": "no verifier supplied; local demo only",
                }
                status = "clear"
            else:
                result = verifier.verify(name, category)
                verification = result.to_dict()
                status = result.status

            if status == "collision":
                continue
            if status == "error":
                if not allow_unverified:
                    raise VerificationError(
                        f"could not verify {name!r} ({category}) and strict mode is on; "
                        "retry, or use --offline for a local demo"
                    )
                verification = {
                    "status": "unverified",
                    "checks": verification.get("checks", []),
                    "note": "verification failed; trap is not publishable",
                }

            produced += 1
            question = build_question(category, fields, variant=(produced - 1) + day.toordinal())
            traps.append(
                Trap(
                    id=f"{day.isoformat()}-{CATEGORY_CODES[category]}-{produced:02d}",
                    category=category,
                    name=name,
                    question=question,
                    why_fictional=why,
                    verification=verification,
                    fields=fields,
                )
            )

        if produced < per_category:
            raise VerificationError(
                f"only {produced}/{per_category} verified traps for {category} on "
                f"{day.isoformat()} after {attempts} attempts"
            )

    controls = pick_controls(day, controls_per_category)
    return DaySet(date=day.isoformat(), traps=traps, controls=controls, demo=demo)
