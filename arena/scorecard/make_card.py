"""1200x630 share card, drawn with Pillow. No network, no template engine.

Layout is deliberately boring: one headline number, one score, the date, the model name, and
a footer that says the items are fictional. Every text block is measured and shrunk until it
fits, and `make_card` raises if something would still overflow - a card with clipped text is
worse than no card.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BACKGROUND = (11, 16, 32)
PANEL = (19, 26, 46)
TEXT = (232, 236, 247)
MUTED = (167, 176, 200)
ACCENT = (122, 162, 255)
BAD = (251, 113, 133)
GOOD = (74, 222, 128)
WARN = (251, 191, 36)

FONT_DIR = Path(__file__).parent / "fonts"
REGULAR = FONT_DIR / "Lato-Regular.ttf"
BOLD = FONT_DIR / "Lato-Bold.ttf"

PAD = 64


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    path: Path,
    *,
    max_size: int,
    min_size: int,
    max_width: int,
) -> ImageFont.FreeTypeFont:
    for size in range(max_size, min_size - 1, -2):
        font = _font(path, size)
        width = draw.textbbox((0, 0), text, font=font)[2]
        if width <= max_width:
            return font
    return _font(path, min_size)


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int
) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


@dataclass
class CardStats:
    model_name: str
    bluff_count: int
    n_fictional: int
    honesty_score: float
    control_accuracy: float
    date: str
    demo: bool = False

    @property
    def bluff_rate(self) -> float:
        return self.bluff_count / self.n_fictional if self.n_fictional else 0.0


def _bluff_verdict(bluff_count: int, n: int) -> str:
    if n == 0:
        return "no answers to score"
    rate = bluff_count / n
    if rate == 0:
        return "no bluffs: every answer admitted it could not verify the item"
    if rate < 0.34:
        return "mostly honest, with some invented details"
    if rate < 0.67:
        return "invented details about half the time"
    return "invented details almost every time"


def make_card(stats: CardStats, out_path: Path | str) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Panels
    draw.rectangle([0, 0, WIDTH, 8], fill=ACCENT)
    draw.rounded_rectangle([PAD, 150, WIDTH - PAD, 470], radius=24, fill=PANEL)

    # Brand and date
    brand_font = _font(BOLD, 24)
    draw.text((PAD, 40), "AI TRAP ARENA", font=brand_font, fill=ACCENT)
    small = _font(REGULAR, 20)
    draw.text((PAD + 232, 44), "would your AI fall for it?", font=small, fill=MUTED)
    date_label = stats.date
    draw.text(
        (WIDTH - PAD - draw.textbbox((0, 0), date_label, font=small)[2], 44),
        date_label,
        font=small,
        fill=MUTED,
    )
    if stats.demo:
        badge_font = _font(BOLD, 18)
        badge_w = draw.textbbox((0, 0), "DEMO DATA", font=badge_font)[2] + 24
        draw.rounded_rectangle(
            [WIDTH - PAD - badge_w, 84, WIDTH - PAD, 118], radius=17, fill=(58, 42, 7)
        )
        draw.text(
            (WIDTH - PAD - badge_w + 12, 90), "DEMO DATA", font=badge_font, fill=(255, 223, 155)
        )

    # Headline
    headline = f"{stats.bluff_count} of {stats.n_fictional} answers invented details"
    headline_font = _fit(
        draw, headline, BOLD, max_size=52, min_size=30, max_width=WIDTH - 2 * PAD - 320
    )
    draw.text((PAD + 40, 190), headline, font=headline_font, fill=TEXT)

    # Verdict, wrapped
    verdict = _bluff_verdict(stats.bluff_count, stats.n_fictional)
    verdict_font = _font(REGULAR, 24)
    y = 190 + draw.textbbox((0, 0), headline, font=headline_font)[3] + 18
    for line in _wrap(draw, verdict, verdict_font, WIDTH - 2 * PAD - 360):
        if y > 330:
            break
        draw.text((PAD + 40, y), line, font=verdict_font, fill=MUTED)
        y += 32

    # Model name
    name_font = _fit(
        draw,
        stats.model_name,
        BOLD,
        max_size=26,
        min_size=16,
        max_width=WIDTH - 2 * PAD - 360,
    )
    draw.text((PAD + 40, 400), stats.model_name, font=name_font, fill=MUTED)

    # Big score on the right
    score_text = f"{stats.honesty_score:.0f}"
    score_font = _font(BOLD, 118)
    score_w = draw.textbbox((0, 0), score_text, font=score_font)[2]
    score_x = WIDTH - PAD - 60 - score_w
    draw.text((score_x, 196), score_text, font=score_font, fill=GOOD)
    label_font = _font(REGULAR, 22)
    draw.text((score_x - 4, 330), "honesty score / 100", font=label_font, fill=MUTED)

    control_text = f"{stats.control_accuracy * 100:.0f}% of real questions correct"
    control_font = _font(REGULAR, 20)
    control_w = draw.textbbox((0, 0), control_text, font=control_font)[2]
    draw.text((WIDTH - PAD - 40 - control_w, 372), control_text, font=control_font, fill=MUTED)

    # Footer
    footer_font = _font(REGULAR, 19)
    footer = "Fictional items only: every trap was verified as nonexistent before use."
    draw.text((PAD, HEIGHT - 96), footer, font=footer_font, fill=MUTED)
    repo = "github.com/MHK-ctrl/ai-trap-arena"
    draw.text((PAD, HEIGHT - 64), repo, font=_font(BOLD, 19), fill=ACCENT)

    note = "Not a product review: one behaviour, one day, small sample."
    note_w = draw.textbbox((0, 0), note, font=footer_font)[2]
    if note_w <= WIDTH - 2 * PAD:
        draw.text((WIDTH - PAD - note_w, HEIGHT - 64), note, font=footer_font, fill=MUTED)

    # Every visible string must fit its box.
    for text, font, max_width in (
        (headline, headline_font, WIDTH - 2 * PAD - 320),
        (stats.model_name, name_font, WIDTH - 2 * PAD - 360),
        (footer, footer_font, WIDTH - 2 * PAD),
        (repo, _font(BOLD, 19), WIDTH - 2 * PAD),
    ):
        if draw.textbbox((0, 0), text, font=font)[2] > max_width:
            raise ValueError(f"text does not fit the card: {text!r}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)
    return out_path


def share_text(stats: CardStats) -> str:
    return (
        f"I asked an AI {stats.n_fictional} questions about books, laws and software libraries "
        f"that do not exist. It invented details in {stats.bluff_count} of them.\n\n"
        f"Honesty score: {stats.honesty_score:.0f}/100 on {stats.date}. "
        f"{stats.control_accuracy * 100:.0f}% of the real control questions were answered "
        "correctly, so this is not a score for refusing everything.\n\n"
        "Test your own AI in two minutes: https://github.com/MHK-ctrl/ai-trap-arena\n\n"
        "#AI #LLM #Hallucination #OpenSource"
    )


def from_score_file(scores: list[dict], model_name: str, day: str, demo: bool = False) -> CardStats:
    """Build card stats from score records produced by `arena score`."""
    from arena.scoring import summarise

    metrics = summarise(scores).get(scores[0]["model_id"] if scores else "", None)
    if not metrics:
        raise ValueError("no scorable answers in this file")
    return CardStats(
        model_name=model_name,
        bluff_count=metrics["bluff_rate"]["count"],
        n_fictional=metrics["bluff_rate"]["n"],
        honesty_score=metrics["honesty_score"],
        control_accuracy=metrics["control_accuracy"]["rate"],
        date=day or Date.today().isoformat(),
        demo=demo,
    )
