## What does this pull request do?

<!-- One or two sentences. -->

## If it adds a trap

- [ ] The item is fictional and I searched for it myself.
- [ ] `arena check-submission <file>` passes locally (four sources, all clear).
- [ ] The question is neutral and does not hint that the item might not exist.
- [ ] It is not about a real person, company, product, disease or anything that could cause
      harm if someone repeated it.

## If it changes scoring

- [ ] `pytest` passes.
- [ ] `arena score data/gold/answers.jsonl --gold` still meets the threshold.
- [ ] If agreement changed, `METHODOLOGY.md` states the new measured number.
- [ ] Any change to a published label is added to `CORRECTIONS.md` with a reason.

## Checklist

- [ ] `ruff check .` passes.
- [ ] No API keys, tokens or personal data are included.
- [ ] Docs updated if behaviour changed.
