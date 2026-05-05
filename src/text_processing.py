"""Utilidades de limpieza y preparación de texto."""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """Limpia un texto manteniendo la información relevante.

    Args:
        text: Texto original.

    Returns:
        Texto en minúsculas, sin espacios repetidos y con caracteres
        innecesarios eliminados.
    """
    normalized_text = text.lower().replace("\r", "\n").replace("\t", " ")
    normalized_text = re.sub(r"[^\w\sáéíóúüñ.,;:()/%-]", " ", normalized_text)
    normalized_text = re.sub(r"\n\s*\n+", "\n", normalized_text)
    normalized_text = re.sub(r"[ ]{2,}", " ", normalized_text)
    normalized_text = re.sub(r" *\n *", "\n", normalized_text)
    return normalized_text.strip()
