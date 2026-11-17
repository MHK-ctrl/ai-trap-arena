# PLAN

This file is the build order for AI Trap Arena. It is committed so the repository shows how
it was made, and so anyone can reproduce the pipeline from an empty checkout.

## What the project does

Every day it invents plausible items that do not exist (books, laws, software, scientists,
events, scientific terms), checks each one against four real sources to be sure it does not
exist, asks several AI models neutral questions about them, and scores whether the model
bluffed or admitted ignorance. It asks about real items as controls so a model cannot win by
refusing everything. Results go to a public leaderboard, and anyone can test their own AI and
get a shareable scorecard.

## Files, in the order they are created

| # | File | Purpose |
|---|---|---|
| 1 | `PLAN.md` | this file |
| 2 | `LICENSE`, `CODE_OF_CONDUCT.md`, `ETHICS.md`, `CONTRIBUTING.md`, `.gitignore`, `pyproject.toml` | project metadata and public rules |
| 3 | `config/settings.yaml` | question counts, temperature, cost cap, scoring thresholds, verification settings |
| 4 | `config/models.yaml` | model registry; three synthetic mock models enabled, real providers commented out |
| 5 | `arena/trapgen/generators.py` | six seeded generators, deterministic from the date |
| 6 | `arena/trapgen/verifier.py` | PyPI / npm / Open Library / Wikipedia existence checks, cached |
| 7 | `arena/trapgen/controls.py` | real items with verified facts and expected keywords |
| 8 | `arena/prompts.py` | neutral question templates, identical for every model |
| 9 | `arena/runners/base.py` | `Answer` record and runner interface |
| 10 | `arena/runners/mock.py` | offline models: bluffer, honest, refuser, mixed |
| 11 | `arena/runners/openai_compatible.py` | any OpenAI-compatible endpoint, key from env var |
| 12 | `arena/runners/anthropic_client.py` | Anthropic Messages API, key from env var |
| 13 | `arena/runners/cost_guard.py` | daily budget cap and dry-run estimates |
| 14 | `arena/scoring/labels.py` | the seven labels |
| 15 | `arena/scoring/rules.py` | deterministic classifier |
| 16 | `arena/scoring/judge.py` | optional LLM judge with a fixed rubric for UNCLEAR answers |
| 17 | `arena/scoring/stats.py` | Wilson intervals, bluff/honesty/over-refusal rates, honesty score |
| 18 | `arena/scoring/__init__.py` | scoring pipeline and gold-set evaluation |
| 19 | `arena/leaderboard/history.py` | per-day series and trend SVG |
| 20 | `arena/leaderboard/build_site.py` | static site into `docs/` |
| 21 | `arena/scorecard/make_card.py` | 1200x630 PNG scorecard and share text |
| 22 | `arena/cli.py` | `arena today/run/score/site/test-my-ai/card`, plus `check-submission` |
| 23 | `tests/` | pytest suite, network mocked |
| 24 | `data/gold/answers.jsonl` | 60 hand-labelled answers used to measure the scorer |
| 25 | `data/submissions/schema.json` | JSON Schema for community trap submissions |
| 26 | `.github/workflows/ci.yml`, `.github/workflows/daily.yml` | tests and the daily job (dry run by default) |
| 27 | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/*` | contribution paths |
| 28 | `METHODOLOGY.md` | how traps, scoring and ranking work, with measured scorer agreement |
| 29 | `README.md` | written last, after the pipeline has actually run |
| 30 | `blog/post.md` | the story post, drafted from real (here: demo) data |

## Execution order

1. Write the package and tests.
2. `pip install -e ".[dev]"`, run `pytest`, `ruff check .`, fix until green.
3. Run the full pipeline: `arena today` (real verification against four sources), `arena run`
   (mock models, because no provider keys exist on this machine), `arena site`, `arena card`.
4. Measure the scorer against the gold set; if agreement is below 85%, improve the rules and
   re-measure. Write the final measured number into `METHODOLOGY.md`.
5. Verify no committed trap matches a real item, check for secrets, check internal links,
   serve `docs/` locally.
6. Write `README.md` with screenshots of the real site and card.
7. Publish to GitHub, enable Pages, configure the daily job.
8. Draft the blog post, wait for approval, publish, capture the URL.
9. Draft the LinkedIn post with the blog and repo URLs, wait for approval, publish.

## Honesty rules baked into the build

* No provider API keys exist on this machine, so the first run is **demo data** produced by
  synthetic mock models. Every page, the README, the blog post and the LinkedIn post say so.
* Traps are only published after the verifier has checked all four sources. If verification
  cannot run, the CLI refuses to write the day (unless `--offline` is passed, which marks
  every trap `verification: unverified` and is only used by tests and local demos).
* Raw model answers are stored unedited. The scorer never rewrites them.
* Scorer accuracy is measured on a hand-labelled set and reported with its sample size.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| A fake name accidentally matches a real thing | four-source check, near-match comparison, regeneration, plus a full re-check of every committed trap |
| Mock results read as real model results | `demo: true` in `data/meta.json`, a banner on every page, "DEMO DATA" on the card, explicit wording in README/blog/LinkedIn |
| Scorer mislabels hedged answers | gold set spanning all seven labels, including partial fabrication, and a measured agreement number |
| Cost blow-up when real models are enabled | `dry_run` default, per-run token estimate, daily cap enforced before each call |
| Daily job failing silently | workflow commits its own log, CI runs the same commands on push |
