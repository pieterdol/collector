"""What every vision backend has to provide.

A backend's whole job is: photo in, the lines of text printed on the box out.
Everything that turns those lines into a catalog search — noise filtering,
console detection, candidate ordering, arbitration — lives above this seam and
is backend-agnostic, so a new backend is one new module and one registry line.
"""

import io
from abc import ABC, abstractmethod

from PIL import Image, ImageOps

#: What the model sees. Phone photos at 4032px are slower *and* read worse
#: (they come back empty); 1024px answers in a few seconds.
MAX_EDGE = 1024

#: Never ask "what is the title?" — every local model tested answers that
#: question with an invention when the title isn't in frame (both gemma3 and
#: qwen3-vl named "The Last of Us Part II" for a photo of the *back* of a
#: Stellar Blade box). Asking for the text that is printed keeps the model
#: grounded in the pixels, and the title falls out of the result.
ALL_TEXT_PROMPT = (
    "List every piece of text printed on this box, one per line, largest "
    "first. No commentary."
)


class VisionUnavailable(RuntimeError):
    """A backend isn't configured, or isn't answering."""


class VisionBackend(ABC):
    """One way of reading a cover."""

    #: Registry key, also what the UI reports.
    name: str

    @abstractmethod
    def available(self) -> bool:
        """Whether this backend is configured (key present, URL set, …)."""

    @abstractmethod
    def read_lines(self, image: bytes) -> list[str]:
        """The text printed on the box, one line per string, largest first.

        Raise VisionUnavailable when the backend itself failed (unreachable,
        throttled, refused) so the next backend gets a turn. Return an empty
        list when it answered but saw nothing — also a cue to try the next one.
        """


def prepare_image(data: bytes) -> bytes:
    """Upright and shrink a photo for whichever backend gets it.

    Phones record rotation in EXIF rather than rotating pixels, and models see
    pixels: the same photo reads "Letter Blade" sideways and "BLADE" upright.
    Clients downscale too; this is what guarantees it.
    """
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    image = image.convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()
