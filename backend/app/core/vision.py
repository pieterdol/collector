"""Reading a cover with a local vision model (Ollama).

Movie discs and game boxes have no public barcode catalog, so the fallback
used to be "type the title yourself". A photo of the front can answer that
instead — but only as a *search term*: what comes back here is never trusted,
it is handed to the normal catalog search and the catalog decides.

Two models are asked, because they fail in opposite directions:

* the reader (`VISION_MODEL`, a qwen3-vl class model) does real OCR and
  degrades by dropping words it cannot make out — "Stellar Blade" in a
  cursive script reads as "BLADE";
* the recogniser (`VISION_RECOGNIZER_MODEL`, moondream) names covers it
  knows from the art alone, catching exactly those stylised logos, but
  invents titles just as confidently when it doesn't know.

Neither is reliable alone; the union, filtered by the catalog, is.
"""

import base64
import io
import re

import httpx
from PIL import Image, ImageOps

from app.config import get_settings

#: What the model sees. Phone photos at 4032px are both slower and read
#: worse (they come back empty); 1024px answers in a few seconds.
MAX_EDGE = 1024

TITLE_PROMPT = (
    "Read the main title printed on this cover. Reply with only the title text."
)
#: One narrow question, ~1s, and it was right on all four boxes tested.
#: Asking for the title and the console together instead is a false economy:
#: the two-part instruction sends the model wandering (30s, and one box came
#: back empty), so this stays a separate call.
CONSOLE_PROMPT = "Which console name is printed on this box? Answer with only the console name."
#: Slower (3-10x) and slightly worse at the title, but it surfaces the
#: publisher and console, which are printed in plain type.
ALL_TEXT_PROMPT = (
    "List every piece of text printed on this box, one per line, largest "
    "first. No commentary."
)

#: Printed on nearly every box and never worth searching for.
NOISE = re.compile(
    r"^\W*(?:"
    r"(?:www\.|https?://).*"
    r"|(?:pegi|usk|esrb|cero)\b.*"
    r"|\d{1,2}\+?"  # a bare rating number ("18"); real years survive
    r"|ultra\s?hd|blu-?ray|dvd|4k"
    r"|only\son\splaystation"
    r"|includes\b.*voucher.*"
    r"|(?:ultimate|deluxe|standard|collector'?s)\sedition"
    r"|game\sof\sthe\syear.*"
    r")\W*$",
    re.IGNORECASE,
)

#: Console as printed on the box → the platform name IGDB uses. Keys are
#: normalised by _platform_key, so punctuation and spacing don't matter
#: ("PS5.", "PlayStation®5" and "playstation 5" all land here).
PLATFORMS = {
    "ps5": "PlayStation 5",
    "playstation5": "PlayStation 5",
    "ps4": "PlayStation 4",
    "playstation4": "PlayStation 4",
    "nintendoswitch2": "Nintendo Switch 2",
    "nintendoswitch": "Nintendo Switch",
    "xboxseriesx|s": "Xbox Series X|S",
    "xboxseriesxs": "Xbox Series X|S",
    "xboxseriesx": "Xbox Series X|S",
    "xboxone": "Xbox One",
}


class VisionUnavailable(RuntimeError):
    """Ollama isn't configured, or isn't answering."""


def available() -> bool:
    return bool(get_settings().ollama_url)


def prepare_image(data: bytes) -> bytes:
    """Upright and shrink a photo for the model.

    Phones record rotation in EXIF rather than rotating the pixels, and the
    models see pixels: the same photo reads "Letter Blade" sideways and
    "BLADE" upright. Clients downscale too, but this is what guarantees it.
    """
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    image = image.convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def clean_answer(answer: str) -> str | None:
    """One model answer → a usable search term, or None.

    Small models pad their answers: moondream shouts ("!!!STELLAR BLADE!!!")
    or only speaks in prose, with the title quoted inside it.
    """
    text = (answer or "").strip()
    if not text:
        return None
    quoted = re.search(r"[\"“']([^\"”']{2,80})[\"”']", text)
    if quoted:
        text = quoted.group(1)
    text = re.sub(r"^(the )?(title|game|answer) (is|reads)\s*:?\s*", "", text, flags=re.I)
    text = text.strip().strip("!?.,:;\"'“” \n").strip()
    if not text or text.upper() == "UNKNOWN" or len(text) < 2:
        return None
    return text


def console_on_box(image: bytes) -> str | None:
    """The console whose name is printed on the box, as IGDB spells it.

    Only worth asking for games — it narrows the catalog search to the right
    edition, and becomes the platform the copy is filed under. The reader is
    the one to ask: the recogniser answers nothing at all to this.
    """
    return platform_from([_ask(get_settings().vision_model, CONSOLE_PROMPT, image)])


def platform_from(lines: list[str]) -> str | None:
    """The console printed on the box, if one of them says so."""
    for line in lines:
        if _platform_key(line) in PLATFORMS:
            return PLATFORMS[_platform_key(line)]
    return None


def search_terms(lines: list[str]) -> list[str]:
    """Box text worth searching — the console name is a filter, not a title
    (searching "PS4" would happily return the wrong game)."""
    return [line for line in lines if _platform_key(line) not in PLATFORMS]


def _platform_key(line: str) -> str:
    """Normalise box print for the PLATFORMS lookup: case, spacing and the
    ®/™/. decoration all vary between boxes and between model answers."""
    return re.sub(r"[^a-z0-9|]", "", line.lower())


def title_candidates(image: bytes) -> list[str]:
    """Both models' idea of the title, reader first, deduped."""
    settings = get_settings()
    answers = [_ask(settings.vision_model, TITLE_PROMPT, image)]
    if settings.vision_recognizer_model:
        answers.append(_ask(settings.vision_recognizer_model, TITLE_PROMPT, image))
        # Moondream returns nothing for an instruction like the above but
        # will describe the picture, with the title quoted in the prose.
        if not clean_answer(answers[-1]):
            answers.append(
                _ask(
                    settings.vision_recognizer_model,
                    "Transcribe the text printed on this cover.",
                    image,
                )
            )
    return dedupe([clean_answer(a) for a in answers])


def all_text(image: bytes) -> list[str]:
    """Every line on the box, minus the ratings and URLs."""
    answer = _ask(get_settings().vision_model, ALL_TEXT_PROMPT, image)
    lines = [line.strip(" .") for line in (answer or "").splitlines()]
    return dedupe([line for line in lines if line and not NOISE.match(line)])


def _ask(model: str, prompt: str, image: bytes) -> str:
    """One Ollama generate call. Never raises for a model's bad answer —
    only for not being able to reach it at all."""
    settings = get_settings()
    if not settings.ollama_url:
        raise VisionUnavailable("Cover reading is not configured (set OLLAMA_URL)")
    try:
        res = httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "images": [base64.b64encode(image).decode()],
                "stream": False,
            },
            timeout=settings.vision_timeout_seconds,
        )
        res.raise_for_status()
    except httpx.HTTPError as exc:
        raise VisionUnavailable(f"Ollama did not answer ({exc.__class__.__name__})") from exc
    return res.json().get("response") or ""


def dedupe(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out
