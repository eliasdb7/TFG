"""Funciones para calcular similitud entre asignaturas."""

from __future__ import annotations

from src.semantic_similarity import compute_semantic_text_similarity


def compute_ects_signal(
    ects_a: float | None,
    ects_b: float | None,
) -> dict[str, float | str | bool | None]:
    """Calcula una senal auxiliar basada en la diferencia de ECTS."""
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
    semantic_similarity: float,
    ects_signal: dict[str, float | str | bool | None],
) -> str:
    """Devuelve una interpretacion textual inicial de la afinidad."""
    if semantic_similarity >= 0.75:
        base_affinity = "afinidad alta"
    elif semantic_similarity >= 0.50:
        base_affinity = "afinidad media"
    else:
        base_affinity = "afinidad baja"

    compatibility = ects_signal.get("compatibilidad_ects")
    if compatibility == "coincidencia_exacta":
        return f"{base_affinity} con ECTS coincidentes"
    if compatibility == "compatibles_con_margen":
        return f"{base_affinity} con ECTS proximos"
    if compatibility == "diferencia_relevante":
        return f"{base_affinity} con diferencia de ECTS"
    return f"{base_affinity} sin senal de ECTS"


def compute_subject_similarity(
    subject_a: dict[str, object],
    subject_b: dict[str, object],
) -> dict[str, object]:
    """Calcula la similitud entre dos asignaturas con V2 semantica."""
    contenidos_a = str(subject_a.get("contenidos") or "")
    contenidos_b = str(subject_b.get("contenidos") or "")

    semantic_result = compute_semantic_text_similarity(contenidos_a, contenidos_b)
    similitud_contenidos = semantic_result.score

    ects_signal = compute_ects_signal(
        subject_a.get("ects") if isinstance(subject_a.get("ects"), (int, float)) else None,
        subject_b.get("ects") if isinstance(subject_b.get("ects"), (int, float)) else None,
    )
    afinidad_interpretada = interpret_affinity(similitud_contenidos, ects_signal)
    fragmentos_mas_parecidos = [
        {
            "indice_origen": match.origin_index,
            "indice_destino": match.target_index,
            "score": match.score,
            "texto_origen": match.origin_text,
            "texto_destino": match.target_text,
        }
        for match in semantic_result.top_matches
    ]

    return {
        "similitud_contenidos": similitud_contenidos,
        "modelo_semantico": semantic_result.model_name,
        "backend_semantico": semantic_result.backend,
        "estrategia_segmentacion": semantic_result.chunking_strategy,
        "fragmentos_origen": semantic_result.origin_chunk_count,
        "fragmentos_destino": semantic_result.target_chunk_count,
        "media_maximos_origen": semantic_result.origin_best_match_mean,
        "media_maximos_destino": semantic_result.target_best_match_mean,
        "fragmentos_mas_parecidos": fragmentos_mas_parecidos,
        "diferencia_ects": ects_signal["diferencia_ects"],
        "compatibilidad_ects": ects_signal["compatibilidad_ects"],
        "ects_compatibles": ects_signal["ects_compatibles"],
        "afinidad_interpretada": afinidad_interpretada,
    }
