"""Funciones auxiliares de propósito general."""

from __future__ import annotations


def truncate_text(text: str, max_length: int = 200) -> str:
    """Recorta un texto largo para facilitar su visualización por consola."""
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."
