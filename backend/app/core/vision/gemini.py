"""Gemini as the fast path — ~1s per photo, optional, off without a key.

`gemini-flash-lite-latest` read all four test boxes in 0.8–1.1s, got the fine
print exactly right where local models garbled it, and — alone among every
model tested — *said so* when asked about a photo with no title in frame
instead of inventing one. It also costs ~$0.0001 a photo, or nothing at all on
the free tier.

Two things to know about that free tier: prompts on it may be used to improve
Google's products (the paid tier excludes that, at ~3 cents a month for this
workload), and it sheds requests under load — a dropped call falls through to
the local backend, which is why the ordering in `vision/__init__.py` matters.
"""

import base64

import httpx

from app.config import get_settings
from app.core.vision.base import ALL_TEXT_PROMPT, VisionBackend, VisionUnavailable

API = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiBackend(VisionBackend):
    name = "gemini"

    def available(self) -> bool:
        return bool(get_settings().gemini_api)

    def read_lines(self, image: bytes) -> list[str]:
        settings = get_settings()
        if not settings.gemini_api:
            raise VisionUnavailable("Gemini is not configured (set GEMINI_API)")
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64.b64encode(image).decode(),
                            }
                        },
                        {"text": ALL_TEXT_PROMPT},
                    ]
                }
            ]
        }
        try:
            res = httpx.post(
                f"{API}/{settings.gemini_vision_model}:generateContent",
                params={"key": settings.gemini_api},
                json=body,
                timeout=settings.vision_timeout_seconds,
            )
            res.raise_for_status()
        except httpx.HTTPError as exc:
            # Throttling and "high demand" land here too; the caller moves on
            # to the next backend rather than failing the request.
            raise VisionUnavailable(
                f"Gemini did not answer ({exc.__class__.__name__})"
            ) from exc
        return _text(res.json()).splitlines()


def _text(payload: dict) -> str:
    """First candidate's text, or "" — a blocked or empty answer is a miss,
    not a crash."""
    for candidate in payload.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if part.get("text"):
                return part["text"]
    return ""
