"""What counts as a platform name.

The catalogs report every console a game shipped on as one comma-joined
string ("Xbox Series X|S, PlayStation 4, PC (Microsoft Windows)"). That is a
release list, not the platform a copy sits on, and a client forwarding it
unchanged means "no platform was picked". Both the FK link and the API
fallback ask here, so neither can disagree about it.
"""

from typing import TypeGuard


def names_one_platform(value: object) -> TypeGuard[str]:
    """True when `value` names a single platform we can link or display.

    Keys on the separator alone: real names carry plenty of punctuation
    ("Xbox Series X|S", "PC (Microsoft Windows)") but never a comma.
    """
    return isinstance(value, str) and bool(value.strip()) and "," not in value
