"""`arena` command line.

    arena today              generate and verify today's set
    arena run                ask every enabled model, then score
    arena score FILE         score answers you collected yourself
    arena site               rebuild the static site in docs/
    arena test-my-ai         print today's questions for any chatbot
    arena card               render a shareable scorecard PNG
    arena check-submission   validate a community trap submission

Every command prints what it wrote. Nothing is uploaded anywhere: the only network access in
this package is the trap verifier.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as Date
from datetime import datetime, timezone
from pathlib import Path

import yaml

from arena.leaderboard.build_site import build_site, latest_day
from arena.runners import (
    BudgetExceeded,
    CostGuard,
    approx_tokens,
    build_runner,
    enabled_models,
    prices_from_config,
)
from arena.scorecard.make_card import from_score_file, make_card, share_text
from arena.scoring import gold_agreement, score_answers, summarise
from arena.trapgen.generators import (
    CATEGORIES,
    CATEGORY_TITLES,
    VerificationError,
    build_day,
)
from arena.trapgen.verifier import Verifier

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def load_settings(root: Path | None = None) -> dict:
    path = (root or ROOT) / "config" / "settings.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_models(root: Path | None = None) -> dict:
    path = (root or ROOT) / "config" / "models.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def day_dir(root: Path, day: str) -> Path:
    return root / "data" / "daily" / day


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def latest_day_or_die(root: Path) -> str:
    day = latest_day(root / "data")
    if not day:
        raise SystemExit("no scored day found; run `arena today` then `arena run`")
    return day


def load_day(root: Path, day: str) -> dict:
    path = day_dir(root, day) / "traps.json"
    if not path.exists():
        raise SystemExit(f"no traps for {day}; run `arena today --date {day}` first")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# today
# ---------------------------------------------------------------------------
def cmd_today(args: argparse.Namespace) -> int:
    settings = load_settings()
    day = args.date or Date.today().isoformat()
    models = enabled_models(load_models())
    demo = all(m.get("provider") == "mock" for m in models)
    verification = settings.get("verification", {})

    verifier = None
    if not args.offline:
        verifier = Verifier(
            cache_path=ROOT / verification.get("cache_path", "data/cache/verification.json"),
            timeout=float(verification.get("timeout", 10)),
            near_match_ratio=float(verification.get("near_match_ratio", 0.92)),
            sources=tuple(verification.get("sources", ("pypi", "npm", "openlibrary", "wikipedia"))),
            user_agent=verification.get("user_agent", "ai-trap-arena/0.1"),
        )

    try:
        day_set = build_day(
            Date.fromisoformat(day),
            verifier,
            per_category=int(args.per_category or settings.get("per_category", 5)),
            controls_per_category=int(settings.get("controls_per_category", 2)),
            salt=settings.get("seed_salt", "ai-trap-arena-v1"),
            allow_unverified=args.offline,
            demo=demo,
        )
    except VerificationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if not args.offline:
            print(
                "retry when the network is available, or use --offline for a local demo "
                "(offline sets are marked unverified and must not be published)",
                file=sys.stderr,
            )
        return 2

    directory = day_dir(ROOT, day)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "traps.json").write_text(
        json.dumps(day_set.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    unverified = sum(1 for trap in day_set.traps if trap.verification.get("status") == "unverified")
    print(f"date:      {day}")
    print(f"traps:     {len(day_set.traps)} across {len(CATEGORIES)} categories")
    print(f"controls:  {len(day_set.controls)}")
    print(f"demo:      {'yes (synthetic models configured)' if demo else 'no'}")
    if args.offline:
        print(f"verified:  {len(day_set.traps) - unverified}/{len(day_set.traps)} (OFFLINE MODE - unverified)")
    else:
        print(f"verified:  {len(day_set.traps)}/{len(day_set.traps)} against four sources")
    print(f"written:   {directory / 'traps.json'}")

    if args.show:
        for category in CATEGORIES:
            print(f"\n{CATEGORY_TITLES[category]}")
            for trap in day_set.traps:
                if trap.category == category:
                    print(f"  [{trap.id}] {trap.question}")
    return 0


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def _estimate_run(day_set: dict, models: list[dict], settings: dict) -> dict[str, float]:
    questions = day_set["traps"] + day_set["controls"]
    max_out = int(settings.get("max_output_tokens", 400))
    prompt_tokens = sum(approx_tokens(q["question"]) for q in questions)
    guard = CostGuard(cap_usd=float(settings.get("daily_cost_cap_usd", 1.0)), prices=prices_from_config(load_models()))
    estimate = {}
    for model in models:
        free = model.get("provider") == "mock"
        try:
            estimate[model["id"]] = guard.estimate(
                model["id"], prompt_tokens, max_out * len(questions), free=free
            )
        except KeyError:
            estimate[model["id"]] = -1.0
    return estimate


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    models_config = load_models()
    day = args.date or latest_day_or_die(ROOT)
    day_set = load_day(ROOT, day)

    selected = enabled_models(models_config)
    if args.models:
        wanted = {m.strip() for m in args.models.split(",")}
        selected = [m for m in selected if m["id"] in wanted]
        if not selected:
            print(f"error: none of {sorted(wanted)} are enabled in config/models.yaml", file=sys.stderr)
            return 2
    if args.limit:
        traps = day_set["traps"][: args.limit]
        controls = day_set["controls"][: max(1, args.limit // 5)]
        questions = traps + controls
    else:
        questions = day_set["traps"] + day_set["controls"]

    estimates = _estimate_run(day_set, selected, settings)
    print(f"day:        {day}")
    print(f"questions:  {len(questions)} per model")
    print(f"models:     {', '.join(m['id'] for m in selected)}")
    for model_id, estimate in estimates.items():
        label = "free (synthetic)" if estimate == 0 else f"~${estimate:.4f}"
        print(f"  {model_id:<20} {label}")
    total = sum(e for e in estimates.values() if e > 0)
    cap = float(settings.get("daily_cost_cap_usd", 1.0))
    print(f"estimated:  ~${total:.4f} of a ${cap:.2f} daily cap")

    if args.dry_run:
        print("dry run: nothing was sent, nothing was written")
        return 0

    guard = CostGuard(cap_usd=cap, prices=prices_from_config(models_config))
    answers: list[dict] = []
    stopped = False
    for model in selected:
        free = model.get("provider") == "mock"
        try:
            runner = build_runner(model, settings)
        except (KeyError, ValueError) as exc:
            print(f"skipping {model['id']}: {exc}", file=sys.stderr)
            continue
        paid = not free
        for question in questions:
            estimate = guard.estimate(
                model["id"],
                approx_tokens(question["question"]),
                int(settings.get("max_output_tokens", 400)),
                free=free,
            )
            try:
                guard.check(estimate)
            except BudgetExceeded as exc:
                print(f"stopping: {exc}", file=sys.stderr)
                stopped = True
                break
            answer = runner.ask(question)
            answers.append(answer.to_dict())
            if paid and not answer.error:
                spender = guard.charge(
                    model["id"],
                    {"prompt_tokens": answer.usage.get("prompt_tokens") or 0,
                     "completion_tokens": answer.usage.get("completion_tokens") or 0},
                    free=False,
                )
                if spender:
                    print(f"  {model['id']} {question['id']}: ${spender:.5f}")
        if stopped:
            break

    directory = day_dir(ROOT, day)
    write_jsonl(directory / "answers.jsonl", answers)

    scores = score_answers(
        answers, day_set, min_chars=int(settings.get("scoring", {}).get("invented_min_chars", 180))
    )
    write_jsonl(directory / "scores.jsonl", scores)
    (ROOT / "data" / "meta.json").write_text(
        json.dumps(
            {
                "date": day,
                "demo": all(m.get("provider") == "mock" for m in selected),
                "models": [m["id"] for m in selected],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "spent_usd": round(guard.spent_usd, 6),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nwritten:    {directory / 'answers.jsonl'}")
    print(f"written:    {directory / 'scores.jsonl'}")
    if all(m.get("provider") == "mock" for m in selected):
        print("DEMO DATA: these models are synthetic; do not present these numbers as real model results")
    _print_metrics(summarise(scores))
    if stopped:
        print("note: the run stopped at the cost cap; partial results were saved", file=sys.stderr)
    return 0


def _print_metrics(metrics_by_model: dict[str, dict]) -> None:
    print(f"\n{'model':<22}{'bluff':>8}{'honest':>9}{'control':>9}{'refuse':>8}{'score':>8}")
    for model_id, metrics in sorted(metrics_by_model.items(), key=lambda kv: -kv[1]["honesty_score"]):
        print(
            f"{model_id:<22}"
            f"{metrics['bluff_rate']['rate'] * 100:>7.1f}%"
            f"{metrics['honesty_rate']['rate'] * 100:>8.1f}%"
            f"{metrics['control_accuracy']['rate'] * 100:>8.1f}%"
            f"{metrics['over_refusal_rate']['rate'] * 100:>7.1f}%"
            f"{metrics['honesty_score']:>8.1f}"
        )


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------
def _hydrate(rows: list[dict], day_set: dict) -> list[dict]:
    questions = {q["id"]: q for q in day_set["traps"] + day_set["controls"]}
    out = []
    for row in rows:
        qid = row.get("question_id") or row.get("id")
        question = questions.get(qid)
        if not question:
            raise SystemExit(
                f"unknown question id {qid!r}: answers must use ids from data/daily/<date>/traps.json"
            )
        out.append(
            {
                "question_id": qid,
                "model_id": row.get("model_id", "your-model"),
                "text": row.get("text") or row.get("answer") or "",
                "prompt": question["question"],
                "category": question["category"],
                "kind": question["kind"],
                "provider": row.get("provider", "external"),
                "usage": row.get("usage", {}),
                "latency_ms": row.get("latency_ms", 0),
                "error": row.get("error"),
            }
        )
    return out


def cmd_score(args: argparse.Namespace) -> int:
    settings = load_settings()
    min_chars = int(settings.get("scoring", {}).get("invented_min_chars", 180))

    if args.gold:
        agreement = gold_agreement(args.answers)
        print(f"gold set:   {agreement['n']} hand-labelled answers")
        print(f"agreement:  {agreement['agree']}/{agreement['n']} ({agreement['rate'] * 100:.1f}%)")
        print(
            f"95% CI:     {agreement['ci_low'] * 100:.0f}-{agreement['ci_high'] * 100:.0f}%"
        )
        if agreement["disagreements"]:
            print("\ndisagreements:")
            for item in agreement["disagreements"]:
                print(f"  {item['id']}: expected {item['expected']}, got {item['predicted']}")
        return 0 if agreement["rate"] >= float(settings.get("scoring", {}).get("min_gold_agreement", 0.85)) else 1

    day = args.date or latest_day_or_die(ROOT)
    day_set = load_day(ROOT, day)
    rows = read_jsonl(Path(args.answers))
    if not rows:
        print(f"error: no answers in {args.answers}", file=sys.stderr)
        return 2

    answers = _hydrate(rows, day_set)
    scores = score_answers(answers, day_set, min_chars=min_chars)

    if args.json:
        Path(args.json).write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
        print(f"written:    {args.json}")

    metrics = summarise(scores)
    _print_metrics(metrics)

    for model_id, values in metrics.items():
        print(
            f"\n{model_id}: {values['bluff_rate']['count']} bluffs in "
            f"{values['bluff_rate']['n']} fictional answers "
            f"({values['bluff_rate']['rate'] * 100:.1f}%), "
            f"{values['control_accuracy']['count']}/{values['control_accuracy']['n']} controls correct, "
            f"honesty score {values['honesty_score']:.1f}"
        )
    return 0


# ---------------------------------------------------------------------------
# site / test-my-ai / card / submission
# ---------------------------------------------------------------------------
def cmd_site(args: argparse.Namespace) -> int:
    settings = load_settings()
    models = load_models()
    scoring = settings.get("scoring", {})
    written = build_site(
        ROOT / "docs",
        ROOT / "data",
        models=enabled_models(models),
        settings=settings,
        gold_path=ROOT / scoring.get("gold_path", "data/gold/answers.jsonl"),
        day=args.date,
    )
    print(f"built:      {len(written)} files in {ROOT / 'docs'}")
    for path in written:
        print(f"  {path.relative_to(ROOT)}")
    return 0


def cmd_test_my_ai(args: argparse.Namespace) -> int:
    settings = load_settings()
    day = args.date or latest_day_or_die(ROOT)
    day_set = load_day(ROOT, day)
    traps = day_set["traps"]
    limit = len(traps) if args.all else int(settings.get("site", {}).get("test_questions", 12))

    grouped: dict[str, list[dict]] = {}
    for trap in traps:
        grouped.setdefault(trap["category"], []).append(trap)
    chosen: list[dict] = []
    for category in sorted(grouped):
        chosen.extend(grouped[category][: max(1, limit // len(grouped))])
    chosen = chosen[:limit]

    payload = [
        {"question_id": t["id"], "category": t["category"], "question": t["question"]} for t in chosen
    ]
    if args.write:
        path = Path(args.write)
        write_jsonl(path, payload)
        print(f"wrote {len(payload)} questions to {path}")
        print("Ask each one in your AI, then save its reply as JSONL with question_id and text.")
        print("Score it with: arena score your-answers.jsonl")
        return 0

    print(f"# {len(payload)} questions about fictional items (verified as nonexistent), {day}\n")
    for i, item in enumerate(payload, start=1):
        print(f"{i:2d}. {item['question']}")
    print("\nDo not tell the AI that some are fictional before you ask.")
    print("Save its answers as JSONL (question_id, text) and run: arena score answers.jsonl")
    return 0


def cmd_card(args: argparse.Namespace) -> int:
    models = enabled_models(load_models())
    day = args.date or latest_day_or_die(ROOT)
    if args.scores:
        scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
        stats = from_score_file(scores, args.name or "your model", day, demo=args.demo)
    else:
        scores = read_jsonl(day_dir(ROOT, day) / "scores.jsonl")
        model_id = args.model
        if not model_id:
            model_id = scores[0]["model_id"] if scores else ""
        model_scores = [s for s in scores if s["model_id"] == model_id]
        if not model_scores:
            print(f"error: no scores for {model_id!r} on {day}", file=sys.stderr)
            return 2
        name = next((m.get("display_name", model_id) for m in models if m["id"] == model_id), model_id)
        demo = any(m.get("provider") == "mock" and m["id"] == model_id for m in models)
        stats = from_score_file(model_scores, name, day, demo=demo)

    out = Path(args.out or ROOT / "docs" / "assets" / "scorecard.png")
    make_card(stats, out)
    print(f"card:       {out}")
    print("\nshare text:\n")
    print(share_text(stats))
    return 0


def cmd_check_submission(args: argparse.Namespace) -> int:
    import jsonschema

    schema = json.loads((ROOT / "data" / "submissions" / "schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        print(f"schema error: {exc.message}", file=sys.stderr)
        return 2

    verification = load_settings().get("verification", {})
    if args.offline:
        print(f"schema ok: {payload['name']} (verification skipped)")
        return 0

    verifier = Verifier(
        cache_path=ROOT / verification.get("cache_path", "data/cache/verification.json"),
        timeout=float(verification.get("timeout", 10)),
        near_match_ratio=float(verification.get("near_match_ratio", 0.92)),
    )
    result = verifier.verify(payload["name"], payload["category"])
    print(f"schema ok: {payload['name']}")
    print(f"verification: {result.status}")
    for check in result.checks:
        print(f"  {check.source:<12} {check.status:<10} {check.detail}")
    if result.status != "clear":
        print("rejected: a trap must be clear on every source", file=sys.stderr)
        return 1
    print("accepted: this is a usable trap")
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arena", description="Would your AI fall for it?")
    parser.add_argument("--version", action="version", version="arena 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    today = sub.add_parser("today", help="generate and verify today's traps")
    today.add_argument("--date", help="YYYY-MM-DD (default: today)")
    today.add_argument("--per-category", type=int, default=0, help="override traps per category")
    today.add_argument("--show", action="store_true", help="print the questions")
    today.add_argument("--offline", action="store_true", help="skip verification (local demo only)")
    today.set_defaults(func=cmd_today)

    run = sub.add_parser("run", help="ask every enabled model and score the answers")
    run.add_argument("--date", help="YYYY-MM-DD (default: latest)")
    run.add_argument("--models", help="comma separated model ids")
    run.add_argument("--limit", type=int, default=0, help="only the first N traps")
    run.add_argument("--dry-run", action="store_true", help="estimate cost, send nothing")
    run.set_defaults(func=cmd_run)

    score = sub.add_parser("score", help="score an answers file")
    score.add_argument("answers", help="JSONL with question_id and text")
    score.add_argument("--date", help="day the questions came from")
    score.add_argument("--json", help="write score records here")
    score.add_argument("--gold", action="store_true", help="treat the file as the gold set")
    score.set_defaults(func=cmd_score)

    site = sub.add_parser("site", help="rebuild docs/")
    site.add_argument("--date", help="day to build from")
    site.set_defaults(func=cmd_site)

    test = sub.add_parser("test-my-ai", help="print today's questions for any chatbot")
    test.add_argument("--write", help="write questions to this JSONL file")
    test.add_argument("--date", help="day to use")
    test.add_argument("--all", action="store_true", help="print every question, not just the short set")
    test.set_defaults(func=cmd_test_my_ai)

    card = sub.add_parser("card", help="render a scorecard PNG")
    card.add_argument("--date", help="day to use")
    card.add_argument("--model", help="model id from the day's scores")
    card.add_argument("--scores", help="score records JSON produced by `arena score --json`")
    card.add_argument("--name", help="name shown on a card built from --scores")
    card.add_argument("--out", help="output PNG path")
    card.add_argument("--demo", action="store_true", help="mark the card DEMO DATA")
    card.set_defaults(func=cmd_card)

    check = sub.add_parser("check-submission", help="validate a community trap submission")
    check.add_argument("file")
    check.add_argument("--offline", action="store_true", help="schema check only")
    check.set_defaults(func=cmd_check_submission)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
