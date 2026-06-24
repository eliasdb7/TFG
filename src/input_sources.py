"""Helpers para recoger por consola las distintas entradas de la V1."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


MANUAL_TEXT_END_MARKER = "FIN"


def is_uniovi_url(url: str) -> bool:
    """Indica si una URL pertenece a la Universidad de Oviedo."""
    netloc = urlparse(url).netloc.lower()
    return "uniovi.es" in netloc


def parse_optional_float(raw_value: str) -> float | None:
    """Convierte una cadena en flotante o devuelve None si está vacía."""
    normalized = raw_value.strip()
    if not normalized:
        return None

    return float(normalized.replace(",", "."))


def prompt_origin_uniovi_url() -> str:
    """Solicita por consola la URL origen, que debe pertenecer a Uniovi."""
    while True:
        url = input(
            "Introduce la URL de la asignatura origen (guia docente Uniovi): "
        ).strip()
        if not url:
            print("Debes indicar una URL de origen.")
            continue
        if not is_uniovi_url(url):
            print("La asignatura origen debe pertenecer a la Universidad de Oviedo.")
            continue
        return url


def prompt_target_mode() -> str:
    """Solicita el modo de entrada de la asignatura destino."""
    print("\nSelecciona el modo de entrada de la asignatura destino:")
    print("1. URL de guia docente")
    print("2. Contenidos pegados manualmente")
    print("3. PDF local de la guia docente")

    while True:
        selected = input("Elige una opcion [1/2/3]: ").strip()
        if selected in {"1", "2", "3"}:
            return selected
        print("Opcion no valida. Introduce 1, 2 o 3.")


def prompt_target_url_request() -> dict[str, object]:
    """Solicita una URL destino y devuelve su descriptor interno."""
    while True:
        url = input("Introduce la URL de la asignatura destino: ").strip()
        if url:
            return {
                "input_mode": "url",
                "source_reference": url,
                "url": url,
            }
        print("Debes indicar una URL destino.")


def read_multiline_text(end_marker: str = MANUAL_TEXT_END_MARKER) -> str:
    """Lee texto multilínea por consola hasta encontrar el marcador final."""
    print(
        "\nPega los contenidos de la asignatura destino."
        f" Escribe {end_marker} en una linea independiente para terminar."
    )
    lines: list[str] = []
    while True:
        line = input()
        if line.strip().casefold() == end_marker.casefold():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def prompt_target_manual_text_request() -> dict[str, object]:
    """Solicita una asignatura destino mediante texto pegado por consola."""
    nombre = input(
        "Introduce el nombre de la asignatura destino (opcional): "
    ).strip() or None

    while True:
        raw_ects = input("Introduce los creditos ECTS destino (opcional): ").strip()
        try:
            ects = parse_optional_float(raw_ects)
            break
        except ValueError:
            print("El valor de ECTS no es valido. Usa un numero como 6 o 4,5.")

    contenidos = read_multiline_text()
    return {
        "input_mode": "manual_text",
        "source_reference": "console_manual_text",
        "nombre": nombre,
        "ects": ects,
        "contenidos": contenidos,
    }


def prompt_target_local_pdf_request() -> dict[str, object]:
    """Solicita una ruta local a un PDF destino."""
    while True:
        raw_path = input(
            "Introduce la ruta local del PDF de la asignatura destino: "
        ).strip()
        if not raw_path:
            print("Debes indicar una ruta local.")
            continue

        pdf_path = Path(raw_path).expanduser()
        return {
            "input_mode": "local_pdf",
            "source_reference": str(pdf_path),
            "pdf_path": str(pdf_path),
        }


def prompt_target_request() -> dict[str, object]:
    """Solicita la asignatura destino en cualquiera de los modos soportados."""
    selected_mode = prompt_target_mode()
    if selected_mode == "1":
        return prompt_target_url_request()
    if selected_mode == "2":
        return prompt_target_manual_text_request()
    return prompt_target_local_pdf_request()
