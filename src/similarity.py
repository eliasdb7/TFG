"""Funciones para calcular similitud textual entre asignaturas."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.text_processing import clean_text


SPANISH_STOPWORDS = {
    "a",
    "al",
    "ante",
    "bajo",
    "con",
    "contra",
    "de",
    "del",
    "desde",
    "durante",
    "e",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "eran",
    "eras",
    "eres",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estas",
    "este",
    "esto",
    "estos",
    "fue",
    "ha",
    "han",
    "hasta",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "más",
    "mas",
    "mi",
    "mis",
    "muy",
    "o",
    "para",
    "pero",
    "por",
    "que",
    "se",
    "ser",
    "si",
    "sin",
    "sobre",
    "su",
    "sus",
    "un",
    "una",
    "unos",
    "unas",
    "y",
    "ya",
}


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """Calcula la similitud coseno entre dos textos usando TF-IDF."""
    cleaned_a = clean_text(text_a)
    cleaned_b = clean_text(text_b)

    if not cleaned_a or not cleaned_b:
        return 0.0

    vectorizer = TfidfVectorizer(
        stop_words=list(SPANISH_STOPWORDS),
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform([cleaned_a, cleaned_b])
    similarity_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return float(similarity_matrix[0][0])


def compute_ects_signal(
    ects_a: float | None,
    ects_b: float | None,
) -> dict[str, float | str | bool | None]:
    """Calcula una señal auxiliar basada en la diferencia de ECTS."""
    if ects_a is None or ects_b is None:
        return {
            "ects_origen": ects_a,
            "ects_destino": ects_b,
            "diferencia_ects": None,
            "compatibilidad_ects": "sin_datos",
            "ects_compatibles": False,
        }

    difference = abs(float(ects_a) - float(ects_b))
    if difference == 0:
        compatibility = "coincidencia_exacta"
        compatible = True
    elif difference <= 1:
        compatibility = "compatibles_con_margen"
        compatible = True
    else:
        compatibility = "diferencia_relevante"
        compatible = False

    return {
        "ects_origen": float(ects_a),
        "ects_destino": float(ects_b),
        "diferencia_ects": difference,
        "compatibilidad_ects": compatibility,
        "ects_compatibles": compatible,
    }


def interpret_affinity(
    total_similarity: float,
    ects_signal: dict[str, float | str | bool | None],
) -> str:
    """Devuelve una interpretación textual inicial de la afinidad."""
    if total_similarity >= 0.75:
        base_affinity = "afinidad alta"
    elif total_similarity >= 0.50:
        base_affinity = "afinidad media"
    else:
        base_affinity = "afinidad baja"

    compatibility = ects_signal.get("compatibilidad_ects")
    if compatibility == "coincidencia_exacta":
        return f"{base_affinity} con ECTS coincidentes"
    if compatibility == "compatibles_con_margen":
        return f"{base_affinity} con ECTS próximos"
    if compatibility == "diferencia_relevante":
        return f"{base_affinity} con diferencia de ECTS"
    return f"{base_affinity} sin señal de ECTS"


def compute_subject_similarity(
    subject_a: dict[str, object],
    subject_b: dict[str, object],
) -> dict[str, float | str | bool | None]:
    """Calcula la similitud entre dos asignaturas a partir de nombre y contenidos."""
    nombre_a = str(subject_a.get("nombre") or "")
    nombre_b = str(subject_b.get("nombre") or "")
    contenidos_a = str(subject_a.get("contenidos") or "")
    contenidos_b = str(subject_b.get("contenidos") or "")

    similitud_nombre = compute_text_similarity(nombre_a, nombre_b)
    similitud_contenidos = compute_text_similarity(contenidos_a, contenidos_b)
    similitud_total = similitud_contenidos

    ects_signal = compute_ects_signal(
        subject_a.get("ects") if isinstance(subject_a.get("ects"), (int, float)) else None,
        subject_b.get("ects") if isinstance(subject_b.get("ects"), (int, float)) else None,
    )
    afinidad_interpretada = interpret_affinity(similitud_total, ects_signal)

    return {
        "similitud_nombre": similitud_nombre,
        "similitud_contenidos": similitud_contenidos,
        "similitud_total": similitud_total,
        "diferencia_ects": ects_signal["diferencia_ects"],
        "compatibilidad_ects": ects_signal["compatibilidad_ects"],
        "ects_compatibles": ects_signal["ects_compatibles"],
        "afinidad_interpretada": afinidad_interpretada,
    }
