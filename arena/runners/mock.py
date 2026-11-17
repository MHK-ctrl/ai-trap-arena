"""Synthetic models used for tests, CI and the offline demo.

These are not model emulations and they are not stand-ins for any real product. They are
deterministic answer generators with four behaviours, which is exactly enough to exercise
every label, every metric and the whole site:

* `bluffer`  - invents details for fictional items, answers controls correctly
* `honest`   - admits it cannot verify fictional items (alternating between "I don't know"
               and "this appears not to exist"), answers controls correctly
* `refuser`  - refuses everything, which is why the controls exist
* `mixed`    - bluffs on some categories, is honest on others

Every record produced here carries `provider: mock`, and every page that renders it says
DEMO DATA.
"""

from __future__ import annotations

import hashlib

from arena.runners.base import Answer, ModelRunner

FABRICATIONS: dict[str, tuple[str, ...]] = {
    "books": (
        (
            "{name} was first published in 1987 by Halberd & Finch. The novel runs to 312 pages "
            "and follows a young cartographer who inherits a set of maps that redraw themselves "
            "at night. Reviewers praised its patient, mineral prose, and the first printing sold "
            "out in eleven weeks before the book went out of print in 1994."
        ),
        (
            "{name} appeared in 1962 from Marrow Press, at 268 pages, and is usually read as a "
            "study of inheritance and weather. The author revised the ending for a second "
            "printing in 1968, which is the edition most citations use."
        ),
    ),
    "laws": (
        (
            "{name} was enacted in 1876 and came into force the following spring. Section 12 "
            "requires covered entities to retain shipping records for seven years and to file "
            "quarterly returns with the Board of Trade. Late filing carries a penalty of 40 "
            "shillings per day, and inspectors may enter premises without notice."
        ),
        (
            "{name} came into force in 1923. It sets a retention period of five years for "
            "ledgers, requires an annual return signed by two officers, and allows the "
            "inspectorate to levy a fine of 100 shillings for each missing entry."
        ),
    ),
    "software": (
        (
            "`{fn}` was added in {lib} 2.4.0 in 2021. It accepts a mapping of keys and returns a "
            "normalised index: `{fn}(source, *, strict=True)`. It raises `StaleIndexError` when "
            "the source has changed since the last call, so callers should wrap it in a retry."
        ),
        (
            "`{fn}` has shipped since {lib} 1.8 and returns a list of normalised keys. The "
            "signature is `{fn}(source, limit=None)`, and it raises `ValueError` for empty "
            "inputs. Most projects call it once at startup and cache the result."
        ),
    ),
    "scientists": (
        (
            "{person} showed in 1954 that {term} arises when a thin film is cooled below 4.2 K "
            "while a magnetic field is applied across it. The result was published in the "
            "Journal of Applied Physics and the effect now carries her name."
        ),
        (
            "{person} described {term} in 1961 after a series of measurements at the Institute "
            "for Advanced Measurement. The paper reports a threshold of 12 mV/cm and was "
            "received with scepticism until it was replicated in 1967."
        ),
    ),
    "events": (
        (
            "{event} took place in 1841. Delegates from nine states met over three sessions and "
            "signed a final protocol that ceded the eastern ports and fixed tolls for twenty "
            "years. The agreement collapsed within a decade, but the protocol is still cited "
            "in maritime histories of the period."
        ),
        (
            "{event} concluded in 1902 after eleven days of negotiation. Seven delegations "
            "signed the final act, which set grain tariffs for a decade and created a "
            "standing commission that met twice a year."
        ),
    ),
    "science_terms": (
        (
            "{term} describes the tendency of a layered material to hold a small charge "
            "difference after the external field is removed. It is measured in millivolts per "
            "centimetre with a shielded probe, and values above 12 mV/cm are treated as "
            "significant in thin-film work."
        ),
        (
            "{term} is the lag between a change in an applied field and the material's "
            "response, usually reported in milliseconds per centimetre. Values above 9 mV are "
            "considered large, and the effect disappears above 40 K."
        ),
    ),
}

ADMISSIONS: tuple[str, ...] = (
    (
        "I don't have any reliable information about {name}. I can't confirm that it exists, "
        "and I would rather not guess at publication details, section numbers or dates."
    ),
    (
        "I am not familiar with {name} and I cannot verify it against anything I know. I may "
        "be missing it, so treat this as an absence of evidence rather than proof."
    ),
)

FLAGS: tuple[str, ...] = (
    (
        "I can't find any evidence that {name} exists. It appears to be fictional or a "
        "misremembered title, so I won't summarise it as though it were real."
    ),
    (
        "Nothing I can check supports the existence of {name}. As far as I can tell this is "
        "not a real item, and I'd be inventing details if I answered further."
    ),
)

REFUSAL = "I can't help with that request. I'm not able to answer questions of this kind."

MIXED_BLUFF_CATEGORIES = {"books", "events", "science_terms"}


def _digest(question_id: str) -> int:
    return int(hashlib.sha256(question_id.encode()).hexdigest()[:8], 16)


def _bluff(question: dict) -> str:
    templates = FABRICATIONS[question["category"]]
    template = templates[_digest(question["id"]) % len(templates)]
    fields = dict(question.get("fields") or {})
    fields.setdefault("name", question["name"])
    fields.setdefault("fn", fields.get("fn", question["name"]))
    fields.setdefault("lib", fields.get("lib", question["name"]))
    fields.setdefault("person", question["name"])
    fields.setdefault("term", fields.get("term", question["name"]))
    fields.setdefault("event", question["name"])
    return template.format(**fields)


def _honest(question: dict) -> str:
    name = question["name"]
    if _digest(question["id"]) % 2 == 0:
        return ADMISSIONS[_digest(question["id"]) % len(ADMISSIONS)].format(name=name)
    return FLAGS[_digest(question["id"]) % len(FLAGS)].format(name=name)


class MockRunner(ModelRunner):
    provider = "mock"

    def __init__(self, model_id: str, behaviour: str = "bluffer") -> None:
        super().__init__(model_id)
        if behaviour not in {"bluffer", "honest", "refuser", "mixed"}:
            raise ValueError(f"unknown mock behaviour: {behaviour}")
        self.behaviour = behaviour

    def _complete(self, question: str) -> tuple[str, dict]:
        raise NotImplementedError("MockRunner is driven by ask(), not by raw text")

    def ask(self, question: dict) -> Answer:
        text = self._answer(question)
        return Answer(
            question_id=question["id"],
            model_id=self.model_id,
            text=text,
            prompt=question["question"],
            category=question["category"],
            kind=question["kind"],
            provider=self.provider,
            usage={"prompt_tokens": len(question["question"]) // 4, "completion_tokens": len(text) // 4},
            latency_ms=0,
        )

    def _answer(self, question: dict) -> str:
        if self.behaviour == "refuser":
            return REFUSAL
        if question["kind"] == "control":
            # All non-refusing mocks answer controls correctly: that is what makes a low
            # bluff rate meaningful rather than the product of blanket refusal.
            fact = question.get("fact") or ""
            return fact + " I am confident in this because it is a well-documented fact."
        if self.behaviour == "bluffer":
            return _bluff(question)
        if self.behaviour == "honest":
            return _honest(question)
        # mixed
        if question["category"] in MIXED_BLUFF_CATEGORIES:
            return _bluff(question)
        return _honest(question)
