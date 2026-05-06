"""Definición del pipeline principal de la herramienta."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import requests

from src.dev_logger import log_step, reset_log
from src.extractor import extract_basic_info
from src.scraper import UnsupportedGuideFormatError, fetch_page
from src.similarity import compute_subject_similarity
from src.text_processing import clean_text
from src.utils import truncate_text


RESULTS_JSON_PATH = Path("resultados/resultados_comparacion.json")
RESULTS_CSV_PATH = Path("resultados/resultados_comparacion.csv")


def display_extraction_result(label: str, info: dict[str, object]) -> None:
    """Muestra por consola el resultado de la extracción de una asignatura."""
    print(f"{label}:")
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
    similarity_result: dict[str, float | str | bool | None],
) -> None:
    """Muestra por consola el resultado de una comparación."""
    print("=" * 50)
    print(f"Comparación {index}")
    print(f"Origen: {subject_origin.get('nombre')}")
    print(f"Destino: {subject_target.get('nombre')}")
    print(f"ECTS origen: {subject_origin.get('ects')}")
    print(f"ECTS destino: {subject_target.get('ects')}")
    print(f"Similitud nombre: {similarity_result['similitud_nombre'] * 100:.1f}%")
    print(f"Similitud contenidos: {similarity_result['similitud_contenidos'] * 100:.1f}%")
    print(f"Similitud total: {similarity_result['similitud_total'] * 100:.1f}%")
    print(f"Compatibilidad ECTS: {similarity_result['compatibilidad_ects']}")
    print(f"Afinidad interpretada: {similarity_result['afinidad_interpretada']}")
    print("=" * 50)
    print()


def ensure_results_directory() -> None:
    """Garantiza la existencia del directorio de resultados."""
    Path("resultados").mkdir(parents=True, exist_ok=True)


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
                "origen_url": subject_origin.get("url"),
                "origen_nombre": subject_origin.get("nombre"),
                "origen_ects": subject_origin.get("ects"),
                "destino_url": subject_target.get("url"),
                "destino_nombre": subject_target.get("nombre"),
                "destino_ects": subject_target.get("ects"),
                "estrategia_destino": subject_target.get("estrategia_scraping"),
                "similitud_nombre": similarity.get("similitud_nombre"),
                "similitud_contenidos": similarity.get("similitud_contenidos"),
                "similitud_total": similarity.get("similitud_total"),
                "diferencia_ects": similarity.get("diferencia_ects"),
                "compatibilidad_ects": similarity.get("compatibilidad_ects"),
                "afinidad_interpretada": similarity.get("afinidad_interpretada"),
            }
        )

    with RESULTS_CSV_PATH.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "origen_url",
                "origen_nombre",
                "origen_ects",
                "destino_url",
                "destino_nombre",
                "destino_ects",
                "estrategia_destino",
                "similitud_nombre",
                "similitud_contenidos",
                "similitud_total",
                "diferencia_ects",
                "compatibilidad_ects",
                "afinidad_interpretada",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)


def process_subject(url: str, label: str) -> dict[str, object]:
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
    info["estrategia_scraping"] = fetch_result.strategy_name
    contents = str(info.get("contenidos") or "")
    info["contenidos"] = clean_text(contents) if contents else ""

    warnings = info.get("warnings", [])
    if isinstance(warnings, list):
        for warning in warnings:
            if "fallback" in warning.lower():
                log_step(
                    "Uso de fallback",
                    "No se ha localizado una sección explícita de contenidos, por lo que se emplea texto general de la página como aproximación inicial.",
                )
                break

    display_extraction_result(label, info)
    return info


def run_pipeline(url_origen: str, urls_destino: list[str]) -> None:
    """Ejecuta el flujo base de la V1.2 para una asignatura origen y varias destino.

    Args:
        url_origen: URL de la asignatura de origen.
        urls_destino: Lista de URLs de asignaturas de destino.
    """
    reset_log()
    print("Iniciando pipeline de comparación de asignaturas.\n")

    subject_origin = process_subject(url_origen, "Asignatura origen")
    subject_targets: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []

    for index, url_destino in enumerate(urls_destino, start=1):
        subject_target = process_subject(url_destino, f"Asignatura destino {index}")
        subject_targets.append(subject_target)

    if not subject_targets:
        print("No hay asignaturas destino para comparar.\n")

    for index, subject_target in enumerate(subject_targets, start=1):
        log_step(
            "Limpieza de texto",
            "Se normalizan los textos de nombre y contenidos para reducir ruido antes de calcular la similitud textual.",
        )
        log_step(
            "Cálculo de similitud de nombre",
            "Se compara el nombre de la asignatura origen con el nombre de la asignatura destino mediante representación TF-IDF y similitud coseno.",
        )
        log_step(
            "Cálculo de similitud de contenidos",
            "Se comparan los contenidos de ambas asignaturas mediante representación TF-IDF y similitud coseno.",
        )
        similarity_result = compute_subject_similarity(subject_origin, subject_target)
        log_step(
            "Cálculo de similitud total",
            "Se combina la similitud del nombre y la similitud de contenidos en una puntuación global ponderada.",
        )
        log_step(
            "Análisis auxiliar de ECTS",
            "Se calcula una señal complementaria basada en la diferencia de créditos ECTS, sin incorporarla todavía al valor numérico final de similitud.",
        )
        log_step(
            "Interpretación de afinidad",
            "Se transforma la puntuación numérica en una salida interpretativa inicial de afinidad entre asignaturas.",
        )
        display_comparison_result(index, subject_origin, subject_target, similarity_result)
        comparisons.append(
            {
                "indice": index,
                "asignatura_destino": subject_target,
                "similitud": similarity_result,
            }
        )

    if comparisons:
        save_comparison_results(subject_origin, comparisons)
        print(f"Resultados guardados en: {RESULTS_JSON_PATH}")
        print(f"Resumen tabular guardado en: {RESULTS_CSV_PATH}\n")

    log_step(
        "Decisión final",
        "La clasificación final de convalidación todavía no se aplica en esta versión, ya que en esta fase solo se calcula una similitud inicial.",
    )
    # print("Pipeline base finalizado.")
