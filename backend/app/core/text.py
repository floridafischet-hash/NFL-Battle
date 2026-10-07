"""Sanitizing of user-visible names."""

import re
import unicodedata

# control, format (incl. bidi overrides and zero-width characters), line/paragraph separators
_FORBIDDEN_CATEGORIES = {"Cc", "Cf", "Zl", "Zp", "Co", "Cs"}
_SPACES = re.compile(r"\s+")


def clean_display_name(value: str) -> str:
    """NFKC-normalize, reject invisible/bidi control characters and collapse whitespace."""
    value = unicodedata.normalize("NFKC", value)
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in value):
        raise ValueError("Der Name enthält unsichtbare oder Steuerzeichen.")
    value = _SPACES.sub(" ", value).strip()
    if not value:
        raise ValueError("Name darf nicht leer sein.")
    return value
