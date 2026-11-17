"""The optional judge parses only well-formed labels and stores its reasoning."""

from __future__ import annotations

from arena.runners.base import Answer, ModelRunner
from arena.scoring.judge import Judge
from arena.scoring.labels import Label


class StubRunner(ModelRunner):
    provider = "stub"

    def __init__(self, reply: str) -> None:
        super().__init__("stub-judge")
        self.reply = reply

    def _complete(self, question: str) -> tuple[str, dict]:
        return self.reply, {"prompt_tokens": 1, "completion_tokens": 1}

    def ask(self, question: dict) -> Answer:
        text = self.reply
        return Answer(
            question_id=question["id"],
            model_id=self.model_id,
            text=text,
            prompt=question["question"],
            category=question.get("category", "judging"),
            kind=question.get("kind", "trap"),
            provider=self.provider,
            usage={},
        )


def test_valid_label_is_parsed_with_reasoning() -> None:
    judge = Judge(StubRunner("LABEL: INVENTED\nREASON: it gives a publication year."))
    score = judge.label("Summarize X.", "It was published in 1987.", "trap")
    assert score is not None
    assert score.label == Label.INVENTED
    assert "publication year" in score.rationale
    assert score.scorer == "judge"


def test_malformed_reply_is_ignored() -> None:
    judge = Judge(StubRunner("I think it is probably fine."))
    assert judge.label("q", "a", "trap") is None


def test_unknown_label_is_ignored() -> None:
    judge = Judge(StubRunner("LABEL: PROBABLY\nREASON: unsure"))
    assert judge.label("q", "a", "trap") is None
