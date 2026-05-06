"""Utilidades de limpieza y preparación de texto."""

from __future__ import annotations

import re


COMMON_ACADEMIC_NOISE = (
    "guía docente",
    "guia docente",
    "universidad",
    "curso académico",
    "curso academico",
)


def normalize_whitespace(text: str) -> str:
    """Normaliza espacios y saltos de línea conservando legibilidad."""
    normalized_text = text.replace("\r", "\n").replace("\t", " ")
    normalized_text = re.sub(r"\n\s*\n+", "\n", normalized_text)
    normalized_text = re.sub(r"[ ]{2,}", " ", normalized_text)
    normalized_text = re.sub(r" *\n *", "\n", normalized_text)
    return normalized_text.strip()


def remove_common_academic_noise(text: str) -> str:
    """Elimina expresiones genéricas poco informativas para la comparación."""
    cleaned_text = text
    for fragment in COMMON_ACADEMIC_NOISE:
        cleaned_text = re.sub(
            re.escape(fragment),
            " ",
            cleaned_text,
            flags=re.IGNORECASE,
        )
    return cleaned_text


def clean_text(text: str) -> str:
    """Limpia un texto manteniendo la información relevante.

    Args:
        text: Texto original.

    Returns:
        Texto en minúsculas, sin espacios repetidos y con caracteres
        innecesarios eliminados.
    """
    normalized_text = normalize_whitespace(text).lower()
    normalized_text = remove_common_academic_noise(normalized_text)
    normalized_text = re.sub(r"[^\w\sáéíóúüñ.,;:()/%-]", " ", normalized_text)
    normalized_text = re.sub(r"[ ]{2,}", " ", normalized_text)
    normalized_text = re.sub(r" *\n *", "\n", normalized_text)
    return normalized_text.strip()
