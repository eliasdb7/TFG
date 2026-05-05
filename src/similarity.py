"""Funciones para calcular similitud textual entre asignaturas."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.text_processing import clean_text


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """Calcula la similitud coseno entre dos textos usando TF-IDF.

    Args:
        text_a: Primer texto a comparar.
        text_b: Segundo texto a comparar.

    Returns:
        Valor de similitud entre 0 y 1.
    """
    cleaned_a = clean_text(text_a)
    cleaned_b = clean_text(text_b)

    if not cleaned_a or not cleaned_b:
        return 0.0

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([cleaned_a, cleaned_b])
    similarity_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return float(similarity_matrix[0][0])


def compute_subject_similarity(
    subject_a: dict[str, object],
    subject_b: dict[str, object],
) -> dict[str, float]:
    """Calcula la similitud entre dos asignaturas a partir de nombre y contenidos.

    Args:
        subject_a: Información extraída de la asignatura origen.
        subject_b: Información extraída de la asignatura destino.

    Returns:
        Diccionario con similitud de nombre, contenidos y total.
    """
    nombre_a = str(subject_a.get("nombre") or "")
    nombre_b = str(subject_b.get("nombre") or "")
    contenidos_a = str(subject_a.get("contenidos") or "")
    contenidos_b = str(subject_b.get("contenidos") or "")

    similitud_nombre = compute_text_similarity(nombre_a, nombre_b)
    similitud_contenidos = compute_text_similarity(contenidos_a, contenidos_b)
    similitud_total = (0.30 * similitud_nombre) + (0.70 * similitud_contenidos)

    return {
        "similitud_nombre": similitud_nombre,
        "similitud_contenidos": similitud_contenidos,
        "similitud_total": similitud_total,
    }
