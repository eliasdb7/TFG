"""Funciones de extracción de información académica desde HTML."""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag


NAME_META_KEYS = (
    "og:title",
    "twitter:title",
    "dc.title",
    "dcterms.title",
    "title",
)

CONTENT_SECTION_KEYWORDS = (
    "contenidos",
    "contenido",
    "temario",
    "programa",
    "programa de la asignatura",
    "bloques tematicos",
    "bloque tematico",
    "descriptor",
    "descripcion de contenidos",
    "contenidos teoricos",
    "contenidos practicos",
    "programa detallado",
)

NOISY_NAME_PATTERNS = (
    r"\|\s*.+$",
    r"\s+-\s+universidad.+$",
    r"\s+-\s+gu[ií]a docente.+$",
)

ACADEMIC_INFO_MARKERS = (
    "codigo asignatura",
    "créditos ects",
    "creditos ects",
    "créditos",
    "creditos",
    "temporalidad",
    "caracter",
    "carácter",
)


def clean_text(text: str) -> str:
    """Limpia un texto conservando una lectura natural.

    Args:
        text: Texto original extraído del HTML.

    Returns:
        Texto sin tabulaciones, con espacios normalizados y sin saltos
        de línea excesivos.
    """
    cleaned_text = text.replace("\t", " ").replace("\r", "\n")
    cleaned_text = re.sub(r"\n\s*\n+", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \xa0]+", " ", cleaned_text)
    cleaned_text = re.sub(r" *\n *", "\n", cleaned_text)
    return cleaned_text.strip()


def normalize_label(text: str) -> str:
    """Normaliza un texto corto para comparaciones flexibles."""
    normalized_text = clean_text(text).lower()
    replacements = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
        }
    )
    normalized_text = normalized_text.translate(replacements)
    normalized_text = re.sub(r"[:\-–]+$", "", normalized_text).strip()
    return normalized_text


def cleanup_subject_name(name: str) -> str:
    """Elimina ruido frecuente en el nombre de la asignatura."""
    cleaned_name = clean_text(name)
    for pattern in NOISY_NAME_PATTERNS:
        cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)
    return cleaned_name.strip(" -|")


def is_generic_degree_name(text: str) -> bool:
    """Indica si el texto parece el nombre de una titulación y no de una asignatura."""
    normalized_text = normalize_label(text)
    generic_prefixes = (
        "grado en ",
        "doble grado en ",
        "master en ",
        "máster en ",
    )
    return normalized_text.startswith(generic_prefixes) or "universidad de" in normalized_text


def get_visible_text(tag: Tag) -> str:
    """Obtiene el texto visible de una etiqueta HTML."""
    return clean_text(tag.get_text(separator=" ", strip=True))


def get_meta_name_candidates(soup: BeautifulSoup) -> list[str]:
    """Recupera posibles nombres de la asignatura desde metadatos."""
    candidates: list[str] = []
    for meta in soup.find_all("meta"):
        meta_name = normalize_label(meta.get("name", "") or meta.get("property", ""))
        if meta_name not in NAME_META_KEYS:
            continue

        content = meta.get("content")
        if content:
            candidates.append(content)

    return candidates


def find_name_near_academic_markers(soup: BeautifulSoup) -> str | None:
    """Busca el nombre en encabezados próximos a campos académicos de la ficha."""
    for marker in ACADEMIC_INFO_MARKERS:
        marker_node = soup.find(
            string=lambda value, expected=marker: bool(value)
            and expected in normalize_label(value)
        )
        if not marker_node:
            continue

        marker_tag = marker_node.parent if isinstance(marker_node.parent, Tag) else None
        if not marker_tag:
            continue

        for heading in marker_tag.find_all_previous(["h1", "h2", "h3", "h4"], limit=5):
            heading_text = cleanup_subject_name(get_visible_text(heading))
            if not heading_text or is_generic_degree_name(heading_text):
                continue
            return heading_text

    return None


def extract_subject_name(html: str) -> str | None:
    """Extrae el nombre de la asignatura desde un documento HTML.

    El orden de búsqueda es:
    `h1`, `h2`, `title` y finalmente metadatos conocidos.
    """
    soup = BeautifulSoup(html, "html.parser")

    contextual_name = find_name_near_academic_markers(soup)
    if contextual_name:
        return contextual_name

    for tag_name in ("h1", "h2"):
        for tag in soup.find_all(tag_name):
            text = cleanup_subject_name(get_visible_text(tag))
            if not text or is_generic_degree_name(text):
                continue
            return text

    for tag_name in ("h3", "h4"):
        for tag in soup.find_all(tag_name):
            text = cleanup_subject_name(get_visible_text(tag))
            if not text or is_generic_degree_name(text):
                continue
            return text

    if soup.title and soup.title.string:
        title_text = cleanup_subject_name(soup.title.string)
        if title_text and not is_generic_degree_name(title_text):
            return title_text

    for candidate in get_meta_name_candidates(soup):
        candidate_text = cleanup_subject_name(candidate)
        if candidate_text and not is_generic_degree_name(candidate_text):
            return candidate_text

    return None


def parse_ects_value(text: str) -> float | None:
    """Intenta convertir una cadena numérica a créditos ECTS."""
    normalized_text = text.strip().replace(",", ".")
    try:
        return float(normalized_text)
    except ValueError:
        return None


def is_valid_ects(value: float | None) -> bool:
    """Valida que el valor encontrado sea razonable como número de ECTS."""
    if value is None:
        return False
    return 0.5 <= value <= 60


def extract_ects_from_label_text(text: str) -> float | None:
    """Busca créditos ECTS en cadenas que contienen etiquetas académicas."""
    patterns = (
        r"cr[eé]ditos?\s*ects?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        r"ects?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        r"cr[eé]ditos?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
    )

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        ects = parse_ects_value(match.group(1))
        if is_valid_ects(ects):
            return ects

    return None


def extract_ects(html: str) -> float | None:
    """Extrae el número de créditos ECTS desde un documento HTML."""
    soup = BeautifulSoup(html, "html.parser")

    candidate_tags = soup.find_all(
        [
            "dt",
            "dd",
            "li",
            "p",
            "div",
            "span",
            "td",
            "th",
            "strong",
            "b",
        ]
    )

    for tag in candidate_tags:
        text = get_visible_text(tag)
        if not text:
            continue

        normalized_text = normalize_label(text)
        if "creditos" not in normalized_text and "ects" not in normalized_text:
            continue

        ects = extract_ects_from_label_text(text)
        if is_valid_ects(ects):
            return ects

    full_text = get_visible_text(soup.body) if soup.body else get_visible_text(soup)
    isolated_match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*ects\b",
        full_text,
        flags=re.IGNORECASE,
    )
    if isolated_match:
        ects = parse_ects_value(isolated_match.group(1))
        if is_valid_ects(ects):
            return ects

    return None


def is_content_heading(text: str) -> bool:
    """Indica si un texto parece un encabezado de contenidos."""
    normalized_text = normalize_label(text)
    return any(keyword in normalized_text for keyword in CONTENT_SECTION_KEYWORDS)


def is_potential_section_label(tag: Tag) -> bool:
    """Indica si una etiqueta puede actuar como título de una sección de contenido."""
    text = get_visible_text(tag)
    if not text or len(text) > 100:
        return False
    return is_content_heading(text)


def iter_section_nodes(start_tag: Tag, allowed_heading_names: Iterable[str]) -> list[Tag]:
    """Recorre los nodos de una sección hasta el siguiente encabezado equivalente."""
    collected_nodes: list[Tag] = []

    for sibling in start_tag.next_siblings:
        if isinstance(sibling, NavigableString):
            text = clean_text(str(sibling))
            if text:
                wrapper = BeautifulSoup(f"<p>{text}</p>", "html.parser").p
                if wrapper:
                    collected_nodes.append(wrapper)
            continue

        if not isinstance(sibling, Tag):
            continue

        if sibling.name in allowed_heading_names and is_content_heading(get_visible_text(sibling)):
            break

        if sibling.name in allowed_heading_names:
            break

        collected_nodes.append(sibling)

    return collected_nodes


def extract_section_from_heading(heading_tag: Tag) -> str | None:
    """Extrae el texto asociado a un encabezado de contenidos."""
    heading_name = heading_tag.name.lower()
    allowed_heading_names = {heading_name}

    section_nodes = iter_section_nodes(heading_tag, allowed_heading_names)
    section_parts = [get_visible_text(node) for node in section_nodes]
    section_text = clean_text("\n".join(part for part in section_parts if part))
    return section_text or None


def extract_section_from_inline_label(label_tag: Tag) -> str | None:
    """Extrae texto cuando el título de sección aparece en `strong` o `b`."""
    parent = label_tag.parent if isinstance(label_tag.parent, Tag) else None
    if not parent:
        return None

    label_text = get_visible_text(label_tag)
    parent_text = get_visible_text(parent)
    if not parent_text:
        return None

    remainder = clean_text(parent_text.replace(label_text, "", 1))
    if remainder:
        return remainder

    following_parts: list[str] = []
    for sibling in parent.next_siblings:
        if isinstance(sibling, NavigableString):
            text = clean_text(str(sibling))
            if text:
                following_parts.append(text)
            continue

        if not isinstance(sibling, Tag):
            continue

        sibling_text = get_visible_text(sibling)
        if not sibling_text:
            continue
        if sibling.name in {"h1", "h2", "h3", "h4", "h5"}:
            break
        if sibling.name in {"strong", "b"} and is_content_heading(sibling_text):
            break

        following_parts.append(sibling_text)

    section_text = clean_text("\n".join(following_parts))
    return section_text or None


def extract_section_from_container_label(label_tag: Tag) -> str | None:
    """Extrae contenido cuando el título de sección está en un contenedor tipo `div`."""
    anchors: list[Tag] = []
    current = label_tag
    for _ in range(3):
        if isinstance(current, Tag):
            anchors.append(current)
        parent = current.parent if isinstance(current.parent, Tag) else None
        if not parent:
            break
        current = parent

    for anchor in anchors:
        collected_parts: list[str] = []
        for sibling in anchor.next_siblings:
            if isinstance(sibling, NavigableString):
                text = clean_text(str(sibling))
                if text:
                    collected_parts.append(text)
                continue

            if not isinstance(sibling, Tag):
                continue

            next_label = sibling.find(
                lambda tag: isinstance(tag, Tag) and is_potential_section_label(tag)
            )
            if next_label:
                break

            sibling_text = get_visible_text(sibling)
            if sibling_text:
                collected_parts.append(sibling_text)

        section_text = clean_text("\n".join(collected_parts))
        if section_text:
            return section_text

    return None


def get_relevant_body_text(soup: BeautifulSoup) -> str | None:
    """Obtiene un texto general del cuerpo evitando ruido evidente."""
    fallback_soup = BeautifulSoup(str(soup), "html.parser")

    for tag in fallback_soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    preferred_container = fallback_soup.find(["main", "article"])
    if preferred_container:
        text = get_visible_text(preferred_container)
        return text or None

    if fallback_soup.body:
        text = get_visible_text(fallback_soup.body)
        return text or None

    text = get_visible_text(fallback_soup)
    return text or None


def extract_contents(html: str) -> str | None:
    """Extrae la sección de contenidos o temario desde un documento HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for heading_name in ("h1", "h2", "h3", "h4", "h5"):
        for heading_tag in soup.find_all(heading_name):
            heading_text = get_visible_text(heading_tag)
            if not is_content_heading(heading_text):
                continue

            section_text = extract_section_from_heading(heading_tag)
            if section_text:
                return section_text

    for label_name in ("strong", "b"):
        for label_tag in soup.find_all(label_name):
            label_text = get_visible_text(label_tag)
            if not is_content_heading(label_text):
                continue

            section_text = extract_section_from_inline_label(label_tag)
            if section_text:
                return section_text

    for label_name in ("div", "span", "p"):
        for label_tag in soup.find_all(label_name):
            if not is_potential_section_label(label_tag):
                continue

            section_text = extract_section_from_container_label(label_tag)
            if section_text:
                return section_text

    return None


def extract_basic_info(html: str, url: str | None = None) -> dict[str, object]:
    """Extrae la información principal de una guía docente HTML.

    Args:
        html: Contenido HTML descargado.
        url: URL de origen del documento, si se desea conservar.

    Returns:
        Diccionario con URL, nombre, créditos ECTS, contenidos y warnings.
    """
    warnings: list[str] = []

    nombre = extract_subject_name(html)
    if not nombre:
        warnings.append("No se ha podido extraer el nombre de la asignatura.")

    ects = extract_ects(html)
    if ects is None:
        warnings.append("No se ha podido identificar el número de créditos ECTS.")

    contenidos = extract_contents(html)
    if not contenidos:
        warnings.append("No se ha encontrado una sección clara de contenidos/temario.")
        soup = BeautifulSoup(html, "html.parser")
        contenidos = get_relevant_body_text(soup)
        if contenidos:
            warnings.append("Se ha utilizado texto general de la página como fallback para contenidos.")

    if contenidos:
        contenidos = clean_text(contenidos)
    else:
        warnings.append("No se ha podido extraer contenido textual relevante de la página.")

    return {
        "url": url,
        "nombre": nombre,
        "ects": ects,
        "contenidos": contenidos,
        "warnings": warnings,
    }
