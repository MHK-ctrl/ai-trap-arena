"""Real, verifiable control items.

Controls exist so a model cannot win by refusing everything. Each one carries the fact it
must produce and a set of keyword groups; a control answer counts as CORRECT only when every
group is satisfied. That is stricter than "mentions the topic", and it is the reason a
refusing model scores 0% control accuracy instead of accidentally scoring well.

Every fact below is a well-established, checkable statement, deliberately chosen to be stable
over time (no "current president", no product versions).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date as Date

from arena.prompts import build_control_question
from arena.trapgen.codes import CATEGORY_CODES


@dataclass(frozen=True)
class Control:
    id: str
    category: str
    name: str
    question: str
    fact: str
    expected: tuple[tuple[str, ...], ...]
    label: str = "REAL"
    kind: str = "control"
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "question": self.question,
            "fact": self.fact,
            "expected": [list(group) for group in self.expected],
            "label": self.label,
            "kind": self.kind,
        }


# category -> tuple of (name, fields, fact, expected keyword groups)
CONTROL_POOL: dict[str, tuple[tuple[str, dict[str, str], str, tuple[tuple[str, ...], ...]], ...]] = {
    "books": (
        (
            "The Hobbit",
            {"title": "The Hobbit", "author": "J. R. R. Tolkien"},
            "The Hobbit by J. R. R. Tolkien was published in 1937 by George Allen & Unwin.",
            (("1937",), ("tolkien",)),
        ),
        (
            "Pride and Prejudice",
            {"title": "Pride and Prejudice", "author": "Jane Austen"},
            "Pride and Prejudice by Jane Austen was published in 1813.",
            (("1813",), ("austen",)),
        ),
        (
            "Nineteen Eighty-Four",
            {"title": "Nineteen Eighty-Four", "author": "George Orwell"},
            "Nineteen Eighty-Four by George Orwell was published in 1949.",
            (("1949",), ("orwell",)),
        ),
        (
            "Things Fall Apart",
            {"title": "Things Fall Apart", "author": "Chinua Achebe"},
            "Things Fall Apart by Chinua Achebe was published in 1958.",
            (("1958",), ("achebe",)),
        ),
    ),
    "laws": (
        (
            "the General Data Protection Regulation",
            {"name": "the General Data Protection Regulation (GDPR)"},
            "The GDPR is Regulation (EU) 2016/679, applicable from 25 May 2018.",
            (("2016",), ("679",)),
        ),
        (
            "the US Clean Air Act",
            {"name": "the US Clean Air Act"},
            "The Clean Air Act was enacted in 1970 and substantially amended in 1990.",
            (("1970",),),
        ),
        (
            "the UK Equality Act 2010",
            {"name": "the UK Equality Act 2010"},
            "The Equality Act 2010 consolidated UK anti-discrimination law and took effect in 2010.",
            (("2010",), ("discriminat",)),
        ),
        (
            "the Berne Convention",
            {"name": "the Berne Convention for the Protection of Literary and Artistic Works"},
            "The Berne Convention was adopted in 1886 and covers copyright between signatories.",
            (("1886",), ("copyright",)),
        ),
    ),
    "software": (
        (
            "itertools.chain",
            {"fn": "itertools.chain", "lib": "itertools"},
            "itertools.chain takes several iterables and yields items from each in order.",
            (("chain",), ("iterable",)),
        ),
        (
            "os.path.join",
            {"fn": "os.path.join", "lib": "os.path"},
            "os.path.join joins path components using the operating system separator.",
            (("join",), ("path",)),
        ),
        (
            "json.dumps",
            {"fn": "json.dumps", "lib": "json"},
            "json.dumps serialises a Python object to a JSON formatted string.",
            (("serial",), ("json",)),
        ),
        (
            "pathlib.Path.read_text",
            {"fn": "pathlib.Path.read_text", "lib": "pathlib"},
            "Path.read_text reads the file at that path and returns its contents as a string.",
            (("read",), ("text", "string")),
        ),
    ),
    "scientists": (
        (
            "Marie Curie",
            {"person": "Marie Curie"},
            "Marie Curie discovered radium and polonium with Pierre Curie in 1898.",
            (("radium",), ("1898",)),
        ),
        (
            "Alfred Wegener",
            {"person": "Alfred Wegener"},
            "Alfred Wegener proposed continental drift in 1912.",
            (("drift",), ("1912",)),
        ),
        (
            "Rosalind Franklin",
            {"person": "Rosalind Franklin"},
            "Rosalind Franklin's X-ray diffraction work, including Photo 51 in 1952, revealed DNA's helical structure.",
            (("x-ray", "x‑ray"), ("dna",)),
        ),
        (
            "Dmitri Mendeleev",
            {"person": "Dmitri Mendeleev"},
            "Dmitri Mendeleev published the periodic table in 1869.",
            (("periodic",), ("1869",)),
        ),
    ),
    "events": (
        (
            "the Apollo 11 Moon landing",
            {"event": "the Apollo 11 Moon landing"},
            "Apollo 11 landed on the Moon on 20 July 1969.",
            (("1969",),),
        ),
        (
            "the fall of the Berlin Wall",
            {"event": "the fall of the Berlin Wall"},
            "The Berlin Wall was opened on 9 November 1989.",
            (("1989",),),
        ),
        (
            "the Treaty of Versailles",
            {"event": "the Treaty of Versailles"},
            "The Treaty of Versailles was signed on 28 June 1919, ending World War I between the Allies and Germany.",
            (("1919",),),
        ),
        (
            "the first powered flight by the Wright brothers",
            {"event": "the first powered flight by the Wright brothers"},
            "The Wright brothers made the first sustained powered flight on 17 December 1903.",
            (("1903",),),
        ),
    ),
    "science_terms": (
        (
            "photosynthesis",
            {"term": "photosynthesis"},
            "Photosynthesis converts light, carbon dioxide and water into glucose and oxygen using chlorophyll.",
            (("light",), ("oxygen",)),
        ),
        (
            "osmosis",
            {"term": "osmosis"},
            "Osmosis is the movement of water across a semipermeable membrane toward higher solute concentration.",
            (("water",), ("membrane",)),
        ),
        (
            "plate tectonics",
            {"term": "plate tectonics"},
            "Plate tectonics describes the movement of lithospheric plates over the asthenosphere.",
            (("plate",),),
        ),
        (
            "enzyme catalysis",
            {"term": "enzyme catalysis"},
            "Enzymes are proteins that catalyse reactions by lowering the activation energy.",
            (("cataly", "catalys"),),
        ),
    ),
}


def _questions(category: str, fields: dict[str, str]) -> str:
    return build_control_question(category, fields)


def pick_controls(day: Date, per_category: int = 2) -> list[Control]:
    """Deterministically choose controls for a day, rotating through the pool."""
    chosen: list[Control] = []
    ordinal = day.toordinal()
    for category, pool in CONTROL_POOL.items():
        count = min(per_category, len(pool))
        offset = ordinal % len(pool)
        for i in range(count):
            name, fields, fact, expected = pool[(offset + i) % len(pool)]
            question = _questions(category, fields)
            chosen.append(
                Control(
                    id=f"{day.isoformat()}-CTL-{CATEGORY_CODES[category]}-{i + 1:02d}",
                    category=category,
                    name=name,
                    question=question,
                    fact=fact,
                    expected=expected,
                    meta={"fields": fields, "source": "hand-written control"},
                )
            )
    return chosen


def controls_for_tests() -> list[Control]:
    """Every control in the pool, used by tests and the submission checker."""
    out: list[Control] = []
    for category, pool in CONTROL_POOL.items():
        for i, (name, fields, fact, expected) in enumerate(pool):
            out.append(
                Control(
                    id=f"CTL-{CATEGORY_CODES[category]}-{i + 1:02d}",
                    category=category,
                    name=name,
                    question=_questions(category, fields),
                    fact=fact,
                    expected=expected,
                    meta={"fields": fields},
                )
            )
    return out


def random_control(rng: random.Random) -> Control:
    pool = controls_for_tests()
    return rng.choice(pool)
