# Contributing

Three useful things you can do here: submit a trap, dispute a score, add a model.

## Submitting a trap

1. Copy `data/submissions/example.json` to `data/submissions/<category>-<slug>.json`.
2. Fill in the invented item, the question you would ask, and why you believe it does not
   exist. Keep the wording neutral: the question must not hint that the item might be fake.
3. Run the validator locally:

   ```bash
   arena check-submission data/submissions/<your-file>.json
   ```

   It checks the JSON Schema, then searches PyPI, npm, Open Library and Wikipedia for a match.
   A match means the submission is rejected, because a trap that exists is not a trap.
4. Open a pull request. CI runs the same validator with the live sources.

Rules for traps, in short: fictional, verifiable as fictional, and never about real people,
companies, products, diseases or advice. See `ETHICS.md` for the full list.

## Disputing a score

Open a "Scoring dispute" issue with the trap id, the model id, the date, and the exact answer
text. A reviewer re-reads the answer against the rubric in `METHODOLOGY.md` and either accepts
the dispute or explains the label. Accepted corrections:

* update the label in `data/daily/<date>/scores.jsonl` (the answer itself is never edited),
* are recorded in `CORRECTIONS.md` with the date, the old label, the new label and the reason,
* are reflected on the site on the next build.

## Adding a model

1. Add an entry to `config/models.yaml`. For an OpenAI-compatible endpoint use
   `provider: openai_compatible`, `base_url`, `model` and `api_key_env`. For Anthropic use
   `provider: anthropic`. Never put a key in the file: only the name of the environment
   variable that holds it.
2. Set `enabled: true` locally to test with your own key.
3. Run a small dry run first: `arena run --dry-run --limit 3`.
4. Add the key as a repository secret if the model should appear in the daily run, and open a
   pull request that also adds the model to the README table.

Models are compared under identical prompts, temperature 0 and no system prompt. Browsing
variants are allowed but must be marked `browsing: true` so they are reported separately.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

Tests never touch the network: the verifier and the runners are injected or mocked. If you
change scoring, re-run `arena score --gold data/gold/answers.jsonl` and update the measured
agreement in `METHODOLOGY.md` if it moves.

## Style

* Plain English in docs, short paragraphs.
* No placeholder text, no TODOs, no invented numbers.
* Keep the site dependency-free: static HTML, one stylesheet, no tracking scripts.
