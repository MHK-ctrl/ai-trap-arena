# Ethics

AI Trap Arena is a test of honesty, not a takedown of any model or company. These rules are
binding on the maintainers and on every contribution.

## Traps are fictional, and verified as fictional

* Every trap is an invented name: a book, law, software library, scientist, event or
  scientific term that does not exist.
* Before a trap can be published, the generator checks the name against **PyPI**, **npm**,
  **Open Library** and **Wikipedia**. A match or a near-match means the item is discarded and
  a new one is generated. `arena check-submission` reruns the same check for community
  submissions, and every committed trap is re-checked in CI.
* Every trap record carries `"label": "FICTIONAL"` and the evidence of what was searched.

## What we never invent traps about

* Real living people, real companies, real products.
* Real diseases, medicines, treatments, legal advice, financial advice.
* Anything where a confident wrong answer could cause harm if someone repeated it.
* Names that resemble famous people. Names are built from uncommon parts precisely to avoid
  this.

## We never present a trap as true

Questions are neutral and never hint that an item might not exist, because the test measures
whether the model checks. But nothing in the repository, the site or the posts claims a trap
is real. The site labels the day's set as fictional in the page header and in the data.

## We never edit model answers

* Raw answers are written to `data/daily/YYYY-MM-DD/answers.jsonl` exactly as returned.
* Scoring is a separate file. If a label changes, the old label stays in the corrections log.
* Example answers shown on the site are copied from the raw data, with the model, date and
  question attached.

## We report uncertainty

* Every percentage is shown with its sample size and a 95% Wilson confidence interval.
* The scorer is measured against a hand-labelled gold set, and its measured agreement is
  published in `METHODOLOGY.md`. No accuracy claim is made without that measurement.
* Synthetic/demo results are labelled as such everywhere they appear. Demo data is never
  described as a real model result.

## We stay neutral

* No insults, no mockery, no "gotcha" framing about a model, lab or company.
* Results are described with dates, model ids, sample sizes and intervals.
* A high bluff rate is a measurement of one behaviour on one day, not a verdict on a product.

## Keys and personal data

* No API keys in the repository, in issues, or in chat. Keys are read from environment
  variables or GitHub Actions secrets.
* Model answers are about fictional items, so they contain no personal data. If a model
  volunteers personal data in an answer, it is stored as returned and flagged in a correction
  note rather than edited.

## If a trap turns out to be real

That is a bug with the highest priority. Open an issue with the evidence, the trap id and the
source that shows the item exists. The trap is removed from the dataset, the day is rebuilt,
and the correction is recorded in `CORRECTIONS.md`.
