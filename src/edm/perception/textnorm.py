"""Turkish-aware text normalization helpers."""

from __future__ import annotations


def tr_fold(s: str) -> str:
    """Fold text case with Turkish I/İ mapping before Unicode casefold."""
    return s.replace("İ", "i").replace("I", "ı").casefold()
