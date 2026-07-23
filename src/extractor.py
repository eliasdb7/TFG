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

SUBJECT_NAME_LABELS = (
    "asignatura",
    "subject",
    "nombre de la asignatura",
    "nombre asignatura",
    "course name",
    "course title",
    "module title",
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

HIGH_PRIORITY_CONTENT_SECTION_KEYWORDS = (
    "programa de contenidos teoricos y practicos",
    "programa de contenidos teóricos y prácticos",
    "programa de contenidos",
    "contenidos teoricos y practicos",
    "contenidos teóricos y prácticos",
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

GENERIC_SUBJECT_NAME_EXACTS = {
    "consulta de guias docentes",
    "informacion del plan docente",
    "teaching plan information",
    "datos de la asignatura",
    "general information",
    "academic year",
    "academic year of degree",
    "estudia",
    "relacionados",
    "guia docente cargada dinamicamente",
}


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
    cleaned_name = re.sub(
        r"^gu[ií]a docente de\s+",
        "",
        cleaned_name,
        flags=re.IGNORECASE,
    )
    cleaned_name = re.sub(r"\s*\(\d+\)\s*$", "", cleaned_name)
    return cleaned_name.strip(" -|")


def is_generic_subject_name(text: str) -> bool:
    """Indica si un texto parece un encabezado genérico y no una asignatura."""
    normalized_text = normalize_label(text)
    if not normalized_text:
        return True

    if is_generic_degree_name(text):
        return True

    if normalized_text in GENERIC_SUBJECT_NAME_EXACTS:
        return True

    if re.fullmatch(r"(curso|ano academico|academic year)(?:\s+\w+)?\s*:?\s*\d{4}(?:/\d{2,4})?", normalized_text):
        return True

    if re.fullmatch(r"\d{4}(?:/\d{2,4})?", normalized_text):
        return True

    return False


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


def score_subject_name_candidate(text: str, *, tag: Tag | None = None, base_score: int = 0) -> int:
    """Calcula una puntuación simple para elegir el nombre más plausible."""
    score = base_score
    cleaned_text = cleanup_subject_name(text)

    if re.search(r"\b\d{4,6}\s*[-–]\s*[^\W_]", cleaned_text):
        score += 12

    if 4 <= len(cleaned_text) <= 120:
        score += 6

    if tag is None:
        return score

    current_tag: Tag | None = tag
    for _ in range(6):
        if current_tag is None:
            break

        class_names = {
            str(class_name).strip().lower()
            for class_name in current_tag.get("class", [])
            if str(class_name).strip()
        }

        if {"active", "show", "current", "selected"} & class_names:
            score += 20

        if "tab-pane" in class_names and "active" not in class_names and "show" not in class_names:
            score -= 15

        if current_tag.has_attr("hidden") or str(current_tag.get("aria-hidden", "")).lower() == "true":
            score -= 20

        parent = current_tag.parent
        current_tag = parent if isinstance(parent, Tag) else None

    return score


def collect_best_candidate(
    candidates: list[tuple[str, int]],
    text: str,
    *,
    tag: Tag | None = None,
    base_score: int = 0,
) -> None:
    """Añade un candidato de nombre si parece válido."""
    candidate_text = cleanup_subject_name(text)
    if not candidate_text or is_generic_subject_name(candidate_text):
        return

    score = score_subject_name_candidate(candidate_text, tag=tag, base_score=base_score)
    candidates.append((candidate_text, score))


def collect_name_candidates_near_academic_markers(soup: BeautifulSoup) -> list[tuple[str, int]]:
    """Busca nombres en encabezados próximos a campos académicos de la ficha."""
    candidates: list[tuple[str, int]] = []
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
            collect_best_candidate(
                candidates,
                get_visible_text(heading),
                tag=heading,
                base_score=85,
            )

    return candidates


def iter_non_empty_following_tags(start_tag: Tag, *, limit: int = 3) -> list[Tag]:
    """Recupera las siguientes etiquetas con texto visible a partir de una etiqueta dada."""
    following_tags: list[Tag] = []
    for sibling in start_tag.next_siblings:
        if not isinstance(sibling, Tag):
            continue

        sibling_text = get_visible_text(sibling)
        if not sibling_text:
            continue

        following_tags.append(sibling)
        if len(following_tags) >= limit:
            break

    return following_tags


def collect_subject_name_candidates_from_labels(soup: BeautifulSoup) -> list[tuple[str, int]]:
    """Busca nombres junto a etiquetas explícitas tipo `Asignatura:` o `Subject:`."""
    candidates: list[tuple[str, int]] = []
    label_tags = soup.find_all(["dt", "th", "td", "strong", "b", "label", "div", "span", "p"])

    for label_tag in label_tags:
        label_text = get_visible_text(label_tag)
        if normalize_label(label_text) not in SUBJECT_NAME_LABELS:
            continue

        parent_tag = label_tag.parent if isinstance(label_tag.parent, Tag) else None
        if parent_tag:
            parent_text = get_visible_text(parent_tag)
            parent_remainder = clean_text(parent_text.replace(label_text, "", 1))
            if parent_remainder:
                collect_best_candidate(
                    candidates,
                    parent_remainder,
                    tag=parent_tag,
                    base_score=110,
                )

        if parent_tag and parent_tag.name == "dt":
            next_dd = parent_tag.find_next_sibling("dd")
            if isinstance(next_dd, Tag):
                collect_best_candidate(candidates, get_visible_text(next_dd), tag=next_dd, base_score=110)

        if parent_tag and parent_tag.name in {"th", "td"}:
            next_cell = parent_tag.find_next_sibling(["td", "th"])
            if isinstance(next_cell, Tag):
                collect_best_candidate(candidates, get_visible_text(next_cell), tag=next_cell, base_score=110)

        for sibling_tag in iter_non_empty_following_tags(label_tag):
            collect_best_candidate(candidates, get_visible_text(sibling_tag), tag=sibling_tag, base_score=100)

        if parent_tag:
            for sibling_tag in iter_non_empty_following_tags(parent_tag):
                collect_best_candidate(candidates, get_visible_text(sibling_tag), tag=sibling_tag, base_score=110)

    return candidates


def pick_best_subject_name(candidates: list[tuple[str, int]]) -> str | None:
    """Elige el candidato de mayor puntuación."""
    if not candidates:
        return None

    best_by_normalized_text: dict[str, tuple[str, int]] = {}
    occurrences_by_normalized_text: dict[str, int] = {}
    for text, score in candidates:
        normalized_text = normalize_label(text)
        occurrences_by_normalized_text[normalized_text] = (
            occurrences_by_normalized_text.get(normalized_text, 0) + 1
        )
        previous = best_by_normalized_text.get(normalized_text)
        if previous is None or score > previous[1] or (
            score == previous[1] and len(text) < len(previous[0])
        ):
            best_by_normalized_text[normalized_text] = (text, score)

    ranked_candidates = sorted(
        (
            (
                text,
                score + (occurrences_by_normalized_text.get(normalized_text, 0) - 1) * 10,
                occurrences_by_normalized_text.get(normalized_text, 0),
            )
            for normalized_text, (text, score) in best_by_normalized_text.items()
        ),
        key=lambda item: (item[1], item[2], -len(item[0])),
        reverse=True,
    )
    return ranked_candidates[0][0]


def extract_subject_name(html: str) -> str | None:
    """Extrae el nombre de la asignatura desde un documento HTML."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, int]] = []

    candidates.extend(collect_subject_name_candidates_from_labels(soup))
    candidates.extend(collect_name_candidates_near_academic_markers(soup))

    heading_scores = {
        "h1": 80,
        "h2": 75,
        "h3": 60,
        "h4": 55,
    }
    for tag_name, base_score in heading_scores.items():
        for tag in soup.find_all(tag_name):
            collect_best_candidate(
                candidates,
                get_visible_text(tag),
                tag=tag,
                base_score=base_score,
            )

    if soup.title and soup.title.string:
        collect_best_candidate(candidates, soup.title.string, base_score=70)

    for candidate in get_meta_name_candidates(soup):
        collect_best_candidate(candidates, candidate, base_score=65)

    return pick_best_subject_name(candidates)


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


def is_high_priority_content_heading(text: str) -> bool:
    """Indica si un encabezado corresponde al programa detallado de contenidos."""
    normalized_text = normalize_label(text)
    return any(
        keyword in normalized_text
        for keyword in HIGH_PRIORITY_CONTENT_SECTION_KEYWORDS
    )


def extract_contents_from_collapsible_section(soup: BeautifulSoup) -> str | None:
    """Extrae contenidos desde estructuras con etiquetas y paneles asociados.

    Este patrón es especialmente útil en portales como UniOvi, donde el título
    de la sección aparece en un bloque tipo `div.seccion` y el contenido real se
    encuentra en un `div.collapse` asociado mediante `data-target`, `href` o
    `aria-controls`.
    """
    candidate_tags = soup.find_all(["div", "button", "a"])

    for tag in candidate_tags:
        label_text = get_visible_text(tag)
        if not is_content_heading(label_text):
            continue

        collapse_ref = (
            tag.get("data-target")
            or tag.get("href")
            or tag.get("aria-controls")
        )
        if not collapse_ref:
            continue

        collapse_id = collapse_ref.lstrip("#").strip()
        if not collapse_id:
            continue

        collapse_tag = soup.find(id=collapse_id)
        if not isinstance(collapse_tag, Tag):
            continue

        section_text = get_visible_text(collapse_tag)
        if section_text:
            return section_text

    return None


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

    primary_pdf_section = soup.find("section", attrs={"data-primary-contents": "true"})
    if isinstance(primary_pdf_section, Tag):
        primary_heading = primary_pdf_section.find(["h1", "h2", "h3", "h4", "h5"])
        if isinstance(primary_heading, Tag):
            section_text = extract_section_from_heading(primary_heading)
            if section_text:
                return section_text

        section_text = get_visible_text(primary_pdf_section)
        if section_text:
            return section_text

    collapse_section_text = extract_contents_from_collapsible_section(soup)
    if collapse_section_text:
        return collapse_section_text

    for heading_name in ("h1", "h2", "h3", "h4", "h5"):
        for heading_tag in soup.find_all(heading_name):
            heading_text = get_visible_text(heading_tag)
            if not is_high_priority_content_heading(heading_text):
                continue

            section_text = extract_section_from_heading(heading_tag)
            if section_text:
                return section_text

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
