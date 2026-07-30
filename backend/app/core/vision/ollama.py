"""Local vision model through Ollama — the default, and the reliability net.

`gemma3:4b` reads all four test boxes correctly (title, console and publisher)
in ~4.6s, in one call. Measured alternatives, for the next person tempted to
swap the default: `gemma3:12b` misreads the stylised titles the 4b gets right,
`qwen3-vl:4b` needs a second model to catch them at all, `glm-ocr` is as
accurate but ~50s, and `deepseek-ocr` is fast but fabricates text. Bigger lost
every time.
"""

import base64

import httpx

from app.config import get_settings
from app.core.vision.base import ALL_TEXT_PROMPT, VisionBackend, VisionUnavailable


class OllamaBackend(VisionBackend):
    name = "ollama"

    def available(self) -> bool:
        return bool(get_settings().ollama_url)

    def read_lines(self, image: bytes) -> list[str]:
        settings = get_settings()
        if not settings.ollama_url:
            raise VisionUnavailable("Cover reading is not configured (set OLLAMA_URL)")
        try:
            res = httpx.post(
                f"{settings.ollama_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.vision_model,
                    "prompt": ALL_TEXT_PROMPT,
                    "images": [base64.b64encode(image).decode()],
                    "stream": False,
                },
                timeout=settings.vision_timeout_seconds,
            )
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise VisionUnavailable(
                f"Ollama did not answer ({exc.__class__.__name__})"
            ) from exc
        return (res.json().get("response") or "").splitlines()
