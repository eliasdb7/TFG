"""Definición del pipeline principal de la herramienta."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import requests

from src.dev_logger import log_step, reset_log
from src.extractor import extract_basic_info
from src.semantic_similarity import SemanticSimilarityError
from src.scraper import UnsupportedGuideFormatError, build_pdf_html_from_file, fetch_page
from src.similarity import compute_subject_similarity
from src.text_processing import clean_text
from src.utils import truncate_text


RESULTS_JSON_PATH = Path("resultados/resultados_comparacion.json")
RESULTS_CSV_PATH = Path("resultados/resultados_comparacion.csv")


def display_extraction_result(label: str, info: dict[str, object]) -> None:
    """Muestra por consola el resultado de la extracción de una asignatura."""
    print(f"{label}:")
    print(f"- Modo de entrada: {info.get('modo_entrada')}")
    print(f"- Referencia de entrada: {info.get('referencia_entrada')}")
    if info.get("url"):
        print(f"- URL procesada: {info.get('url')}")
    print(f"- Estrategia de scraping: {info.get('estrategia_scraping')}")
    print(f"- Nombre extraído: {info.get('nombre')}")
    print(f"- Créditos extraídos: {info.get('ects')}")
    print(
        f"- Contenidos (primeros 500 caracteres): "
        f"{truncate_text(str(info.get('contenidos') or ''), 500)}"
    )

    warnings = info.get("warnings", [])
    print("- Warnings:")
    if isinstance(warnings, list) and warnings:
        for warning in warnings:
            print(f"  * {warning}")
    else:
        print("  * Ninguno")
    print()


def display_comparison_result(
    index: int,
    subject_origin: dict[str, object],
    subject_target: dict[str, object],
    similarity_result: dict[str, object],
) -> None:
    """Muestra por consola el resultado de una comparación."""
    print("=" * 50)
    print(f"Comparación {index}")
    print(f"Origen: {subject_origin.get('nombre')}")
    print(f"Destino: {subject_target.get('nombre')}")
    print(f"ECTS origen: {subject_origin.get('ects')}")
    print(f"ECTS destino: {subject_target.get('ects')}")
    print(f"Similitud semantica de contenidos: {similarity_result['similitud_contenidos'] * 100:.1f}%")
    print(f"Modelo semántico: {similarity_result['modelo_semantico']}")
    print(
        f"Fragmentos semánticos origen/destino: "
        f"{similarity_result['fragmentos_origen']} / {similarity_result['fragmentos_destino']}"
    )
    print(f"Compatibilidad ECTS: {similarity_result['compatibilidad_ects']}")
    print(f"Afinidad interpretada: {similarity_result['afinidad_interpretada']}")
    top_matches = similarity_result.get("fragmentos_mas_parecidos", [])
    if isinstance(top_matches, list) and top_matches:
        print("Fragmentos mas parecidos:")
        for match_index, match in enumerate(top_matches[:3], start=1):
            if not isinstance(match, dict):
                continue
            score = float(match.get("score") or 0.0)
            origin_text = truncate_text(str(match.get("texto_origen") or ""), 160)
            target_text = truncate_text(str(match.get("texto_destino") or ""), 160)
            print(f"  {match_index}. Coincidencia: {score * 100:.1f}%")
            print(f"     - Origen: {origin_text}")
            print(f"     - Destino: {target_text}")
    print("=" * 50)
    print()


def display_ranking_summary(comparisons: list[dict[str, object]]) -> None:
    """Muestra un ranking final cuando hay varias asignaturas destino."""
    if len(comparisons) <= 1:
        return

    print("=" * 50)
    print("Ranking final de afinidad")
    for comparison in comparisons:
        ranking_position = comparison.get("ranking_posicion")
        subject_target = comparison.get("asignatura_destino", {})
        similarity = comparison.get("similitud", {})
        if not isinstance(subject_target, dict) or not isinstance(similarity, dict):
            continue
        print(
            f"{ranking_position}. "
            f"{subject_target.get('nombre')} | "
            f"{float(similarity.get('similitud_contenidos') or 0.0) * 100:.1f}% | "
            f"{similarity.get('afinidad_interpretada')}"
        )
    print("=" * 50)
    print()


def ensure_results_directory() -> None:
    """Garantiza la existencia del directorio de resultados."""
    Path("resultados").mkdir(parents=True, exist_ok=True)


def build_explainability_summary(matches: object, *, limit: int = 3) -> str:
    """Construye un resumen corto de los fragmentos mas parecidos para CSV."""
    if not isinstance(matches, list):
        return ""

    parts: list[str] = []
    for match in matches[:limit]:
        if not isinstance(match, dict):
            continue
        score = float(match.get("score") or 0.0)
        origin_text = truncate_text(str(match.get("texto_origen") or ""), 60)
        target_text = truncate_text(str(match.get("texto_destino") or ""), 60)
        parts.append(
            f"{score * 100:.1f}% | O: {origin_text} | D: {target_text}"
        )

    return " || ".join(parts)


def save_comparison_results(
    subject_origin: dict[str, object],
    comparisons: list[dict[str, object]],
) -> None:
    """Guarda los resultados de la comparación en JSON y CSV."""
    ensure_results_directory()

    json_payload = {
        "asignatura_origen": subject_origin,
        "comparaciones": comparisons,
    }
    with RESULTS_JSON_PATH.open("w", encoding="utf-8") as json_file:
        json.dump(json_payload, json_file, ensure_ascii=False, indent=2)

    csv_rows: list[dict[str, object]] = []
    for comparison in comparisons:
        subject_target = comparison["asignatura_destino"]
        similarity = comparison["similitud"]
        csv_rows.append(
            {
                "ranking_posicion": comparison.get("ranking_posicion"),
                "origen_url": subject_origin.get("url"),
                "origen_modo_entrada": subject_origin.get("modo_entrada"),
                "origen_nombre": subject_origin.get("nombre"),
                "origen_ects": subject_origin.get("ects"),
                "destino_url": subject_target.get("url"),
                "destino_modo_entrada": subject_target.get("modo_entrada"),
                "destino_referencia_entrada": subject_target.get("referencia_entrada"),
                "destino_nombre": subject_target.get("nombre"),
                "destino_ects": subject_target.get("ects"),
                "estrategia_destino": subject_target.get("estrategia_scraping"),
                "similitud_contenidos": similarity.get("similitud_contenidos"),
                "modelo_semantico": similarity.get("modelo_semantico"),
                "backend_semantico": similarity.get("backend_semantico"),
                "estrategia_segmentacion": similarity.get("estrategia_segmentacion"),
                "fragmentos_origen": similarity.get("fragmentos_origen"),
                "fragmentos_destino": similarity.get("fragmentos_destino"),
                "explicabilidad_resumen": build_explainability_summary(
                    similarity.get("fragmentos_mas_parecidos")
                ),
                "diferencia_ects": similarity.get("diferencia_ects"),
                "compatibilidad_ects": similarity.get("compatibilidad_ects"),
                "afinidad_interpretada": similarity.get("afinidad_interpretada"),
            }
        )

    with RESULTS_CSV_PATH.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "ranking_posicion",
                "origen_url",
                "origen_modo_entrada",
                "origen_nombre",
                "origen_ects",
                "destino_url",
                "destino_modo_entrada",
                "destino_referencia_entrada",
                "destino_nombre",
                "destino_ects",
                "estrategia_destino",
                "similitud_contenidos",
                "modelo_semantico",
                "backend_semantico",
                "estrategia_segmentacion",
                "fragmentos_origen",
                "fragmentos_destino",
                "explicabilidad_resumen",
                "diferencia_ects",
                "compatibilidad_ects",
                "afinidad_interpretada",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)


def rank_comparisons(comparisons: list[dict[str, object]]) -> list[dict[str, object]]:
    """Ordena las comparaciones de mayor a menor similitud semantica."""
    ranked = sorted(
        comparisons,
        key=lambda comparison: float(
            (
                comparison.get("similitud", {})
                if isinstance(comparison.get("similitud"), dict)
                else {}
            ).get("similitud_contenidos")
            or 0.0
        ),
        reverse=True,
    )

    for ranking_position, comparison in enumerate(ranked, start=1):
        comparison["ranking_posicion"] = ranking_position

    return ranked


def log_fallback_usage(info: dict[str, object]) -> None:
    """Registra en el log cuando la extracción usa un fallback de contenidos."""
    warnings = info.get("warnings", [])
    if not isinstance(warnings, list):
        return

    for warning in warnings:
        if "fallback" in str(warning).lower():
            log_step(
                "Uso de fallback",
                "No se ha localizado una sección explícita de contenidos, por lo que se emplea texto general de la página como aproximación inicial.",
            )
            break


def process_url_subject(
    url: str,
    label: str,
    *,
    input_mode: str,
) -> dict[str, object]:
    """Descarga y procesa una guía docente individual."""
    log_step(
        "Descarga HTML",
        "Se realiza una petición HTTP a la URL seleccionada para obtener el contenido HTML de la guía docente.",
    )
    try:
        fetch_result = fetch_page(url)
        html = fetch_result.html
    except UnsupportedGuideFormatError as exc:
        log_step(
            "Formato no soportado",
            "La URL analizada apunta a un formato de guía docente que todavía no está soportado en la versión actual del proyecto.",
        )
        info = {
            "url": url,
            "modo_entrada": input_mode,
            "referencia_entrada": url,
            "estrategia_scraping": "unsupported_format",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                str(exc),
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info
    except requests.Timeout:
        log_step(
            "Error de descarga",
            "La descarga ha superado el tiempo de espera configurado, por lo que no se ha podido analizar la página en esta ejecución.",
        )
        info = {
            "url": url,
            "modo_entrada": input_mode,
            "referencia_entrada": url,
            "estrategia_scraping": "download_timeout",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                "La descarga ha excedido el tiempo de espera configurado.",
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info
    except requests.RequestException as exc:
        log_step(
            "Error de descarga",
            "Se ha producido un error HTTP o de conexión al intentar recuperar la guía docente.",
        )
        info = {
            "url": url,
            "modo_entrada": input_mode,
            "referencia_entrada": url,
            "estrategia_scraping": "download_error",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                f"No se ha podido descargar la URL: {exc}",
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info

    log_step(
        "Inicio de extracción",
        "Se inicia el análisis estructural del HTML para localizar la información académica principal de la asignatura.",
    )
    log_step(
        "Extracción de nombre",
        "Se busca el nombre de la asignatura priorizando encabezados principales y, en segundo término, el título de la página y sus metadatos.",
    )
    log_step(
        "Extracción de créditos",
        "Se buscan referencias explícitas a créditos ECTS mediante patrones textuales frecuentes en guías docentes universitarias.",
    )
    log_step(
        "Extracción de contenidos",
        "Se intenta localizar una sección de contenidos o temario a partir de encabezados y etiquetas resaltadas dentro del documento HTML.",
    )
    log_step(
        "Selección de estrategia",
        "Se aplica una estrategia específica del portal si existe; en caso contrario, se utiliza el scraping HTML genérico como mecanismo base.",
    )

    info = extract_basic_info(html, url=url)
    info["modo_entrada"] = input_mode
    info["referencia_entrada"] = url
    info["estrategia_scraping"] = fetch_result.strategy_name
    contents = str(info.get("contenidos") or "")
    info["contenidos"] = clean_text(contents) if contents else ""
    log_fallback_usage(info)

    display_extraction_result(label, info)
    return info


def process_manual_subject(
    subject_data: dict[str, object],
    label: str,
) -> dict[str, object]:
    """Procesa una asignatura destino introducida manualmente por consola."""
    log_step(
        "Entrada manual de destino",
        "La asignatura destino se introduce manualmente por consola mediante nombre opcional, ECTS opcionales y un bloque de contenidos pegado por el usuario.",
    )

    contents = clean_text(str(subject_data.get("contenidos") or ""))
    warnings: list[str] = []
    if not contents:
        warnings.append("No se ha proporcionado contenido textual para la asignatura destino.")

    ects_value = subject_data.get("ects")
    ects = ects_value if isinstance(ects_value, (int, float)) else None
    if subject_data.get("ects") not in (None, "") and ects is None:
        warnings.append("El valor de ECTS introducido manualmente no es valido.")

    info = {
        "url": None,
        "modo_entrada": "manual_text",
        "referencia_entrada": subject_data.get("source_reference") or "console_manual_text",
        "estrategia_scraping": "manual_text",
        "nombre": subject_data.get("nombre"),
        "ects": ects,
        "contenidos": contents,
        "warnings": warnings,
    }
    display_extraction_result(label, info)
    return info


def process_local_pdf_subject(
    subject_data: dict[str, object],
    label: str,
) -> dict[str, object]:
    """Procesa una asignatura destino a partir de un PDF local."""
    pdf_path = str(subject_data.get("pdf_path") or "")
    log_step(
        "Lectura de PDF local",
        "La asignatura destino se obtiene a partir de un PDF local cuyo texto se transforma en un HTML sintético para reutilizar el extractor actual.",
    )

    try:
        html = build_pdf_html_from_file(pdf_path)
    except FileNotFoundError:
        info = {
            "url": None,
            "modo_entrada": "local_pdf",
            "referencia_entrada": pdf_path,
            "estrategia_scraping": "local_pdf",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                "No se ha encontrado el archivo PDF indicado.",
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info
    except OSError as exc:
        info = {
            "url": None,
            "modo_entrada": "local_pdf",
            "referencia_entrada": pdf_path,
            "estrategia_scraping": "local_pdf",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                f"No se ha podido leer el PDF local: {exc}",
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info
    except UnsupportedGuideFormatError as exc:
        info = {
            "url": None,
            "modo_entrada": "local_pdf",
            "referencia_entrada": pdf_path,
            "estrategia_scraping": "local_pdf",
            "nombre": None,
            "ects": None,
            "contenidos": None,
            "warnings": [
                str(exc),
                "No se ha podido procesar la asignatura en esta ejecución.",
            ],
        }
        display_extraction_result(label, info)
        return info

    info = extract_basic_info(html)
    info["modo_entrada"] = "local_pdf"
    info["referencia_entrada"] = pdf_path
    info["estrategia_scraping"] = "local_pdf"
    contents = str(info.get("contenidos") or "")
    info["contenidos"] = clean_text(contents) if contents else ""
    log_fallback_usage(info)

    display_extraction_result(label, info)
    return info


def process_target_request(
    target_request: dict[str, object],
    label: str,
) -> dict[str, object]:
    """Procesa una asignatura destino según su modo de entrada."""
    input_mode = str(target_request.get("input_mode") or "url")
    if input_mode == "url":
        return process_url_subject(
            str(target_request.get("url") or ""),
            label,
            input_mode="url",
        )
    if input_mode == "manual_text":
        return process_manual_subject(target_request, label)
    if input_mode == "local_pdf":
        return process_local_pdf_subject(target_request, label)

    info = {
        "url": None,
        "modo_entrada": input_mode,
        "referencia_entrada": target_request.get("source_reference"),
        "estrategia_scraping": "unsupported_input_mode",
        "nombre": None,
        "ects": None,
        "contenidos": None,
        "warnings": [
            f"El modo de entrada '{input_mode}' no está soportado.",
            "No se ha podido procesar la asignatura en esta ejecución.",
        ],
    }
    display_extraction_result(label, info)
    return info


def run_pipeline(url_origen: str, target_requests: list[dict[str, object]]) -> None:
    """Ejecuta el flujo base de la V2 para una asignatura origen y una o varias destino.

    Args:
        url_origen: URL de la asignatura de origen.
        target_requests: Lista de descriptores de asignaturas destino.
    """
    reset_log()
    print("Iniciando pipeline de comparación de asignaturas.\n")

    subject_origin = process_url_subject(
        url_origen,
        "Asignatura origen",
        input_mode="uniovi_url",
    )
    subject_targets: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []

    for index, target_request in enumerate(target_requests, start=1):
        subject_target = process_target_request(
            target_request,
            f"Asignatura destino {index}",
        )
        subject_targets.append(subject_target)

    if not subject_targets:
        print("No hay asignaturas destino para comparar.\n")

    for index, subject_target in enumerate(subject_targets, start=1):
        log_step(
            "Limpieza de texto",
            "Se normalizan los contenidos extraidos de origen y destino para reducir ruido antes de la comparacion semantica.",
        )
        log_step(
            "Segmentación semántica",
            "Los contenidos de origen y destino se dividen en fragmentos manejables para construir una representación semántica más robusta ante diferencias de redacción.",
        )
        log_step(
            "Generación de embeddings",
            "Cada fragmento de contenido se transforma en un embedding semántico multilingüe para comparar asignaturas más allá de la coincidencia literal de palabras.",
        )
        log_step(
            "Cálculo de similitud semántica",
            "La puntuación principal de la V2 se obtiene comparando los embeddings de origen y destino en un espacio semántico mediante similitud coseno.",
        )
        log_step(
            "Explicabilidad del resultado",
            "Se recuperan los fragmentos de origen y destino con mayor cercania semantica para justificar el porcentaje obtenido y facilitar la interpretacion del resultado.",
        )
        log_step(
            "Análisis auxiliar de ECTS",
            "Se mantiene una señal complementaria basada en la diferencia de créditos ECTS, sin incorporarla al valor numérico principal de similitud.",
        )
        try:
            similarity_result = compute_subject_similarity(subject_origin, subject_target)
        except SemanticSimilarityError as exc:
            log_step(
                "Error de similitud semántica",
                "No se ha podido completar la comparación semántica porque el modelo de embeddings no está disponible o no ha podido cargarse correctamente.",
            )
            print(f"No se ha podido calcular la similitud semántica: {exc}\n")
            return
        log_step(
            "Interpretación de afinidad",
            "Se transforma la puntuación semántica principal en una salida interpretativa inicial de afinidad entre asignaturas.",
        )
        display_comparison_result(index, subject_origin, subject_target, similarity_result)
        comparisons.append(
            {
                "indice_entrada": index,
                "asignatura_destino": subject_target,
                "similitud": similarity_result,
            }
        )

    if comparisons:
        comparisons = rank_comparisons(comparisons)
        display_ranking_summary(comparisons)
        save_comparison_results(subject_origin, comparisons)
        print(f"Resultados guardados en: {RESULTS_JSON_PATH}")
        print(f"Resumen tabular guardado en: {RESULTS_CSV_PATH}\n")

    log_step(
        "Decisión final",
        "La clasificación final de convalidación todavía no se aplica en esta versión, ya que esta fase se centra en mejorar la comparación semántica de contenidos.",
    )
    # print("Pipeline base finalizado.")
