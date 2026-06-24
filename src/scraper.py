"""Funciones para la descarga del contenido HTML."""

from __future__ import annotations

import base64
import html
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


class UnsupportedGuideFormatError(ValueError):
    """Se lanza cuando la guía encontrada no pertenece al alcance actual."""


@dataclass(frozen=True)
class ScraperStrategy:
    """Define una estrategia de scraping para un portal concreto."""

    name: str
    description: str
    host_patterns: tuple[str, ...]
    direct_fetcher: Callable[[str, requests.Session], str | None] | None = None
    html_enricher: Callable[[str, requests.Session, str], str] | None = None


@dataclass(frozen=True)
class FetchResult:
    """Representa el resultado de una descarga HTML."""

    url: str
    html: str
    strategy_name: str
    strategy_description: str


# HTTP session

def build_session() -> requests.Session:
    """Crea una sesión HTTP con cabeceras y reintentos básicos."""
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


def matches_host(url: str, host_patterns: tuple[str, ...]) -> bool:
    """Comprueba si una URL pertenece a alguno de los dominios esperados."""
    netloc = urlparse(url).netloc.lower()
    return any(pattern in netloc for pattern in host_patterns)


def wrap_html_section(section_id: str, heading: str, content_html: str) -> str:
    """Envuelve un bloque HTML enriquecido para integrarlo en la página."""
    return (
        f'\n<section id="{section_id}">'
        f"<h2>{html.escape(heading)}</h2>"
        f"{content_html}</section>\n"
    )


# PDF helpers

def normalize_pdf_lines(pdf_text: str) -> list[str]:
    """Normaliza el texto extraído de un PDF en líneas útiles."""
    raw_lines = pdf_text.replace("\r", "\n").split("\n")
    return [line.strip() for line in raw_lines if line.strip()]


def normalize_heading_label(text: str) -> str:
    """Normaliza un texto corto para compararlo como encabezado."""
    normalized = text.strip().lower()
    replacements = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
        }
    )
    normalized = normalized.translate(replacements)
    return re.sub(r"\s+", " ", normalized)


def canonicalize_pdf_heading(line: str) -> str:
    """Devuelve una versión canónica de ciertos encabezados de PDF."""
    normalized = normalize_heading_label(line)

    if normalized in {
        "contenidos",
        "contenido",
        "contenidos o bloques tematicos",
        "contenidos o bloques temáticos",
        "bloques tematicos",
        "bloques temáticos",
        "bloques de contenido",
    }:
        return "Contenidos"
    if "bloques de contenido" in normalized:
        return "Contenidos"
    if normalized == "guia docente":
        return "Guía docente"
    if normalized in {
        "datos basicos de la asignatura",
        "datos básicos de la asignatura",
    }:
        return "Datos básicos de la asignatura"
    if normalized in {
        "objetivos y resultados del aprendizaje",
        "resultados del aprendizaje",
    }:
        return "Resultados del aprendizaje"
    if normalized == "actividades formativas y horas lectivas":
        return "Actividades formativas"
    if normalized == "metodologia":
        return "Metodología"
    if normalized == "metodologia de enseñanza-aprendizaje":
        return "Metodología"
    if normalized == "metodologia de ensenanza-aprendizaje":
        return "Metodología"
    if normalized == "evaluacion":
        return "Evaluación"
    if normalized == "sistemas y criterios de evaluacion y calificacion":
        return "Evaluación"
    if normalized == "bibliografia":
        return "Bibliografía"

    return line


def is_pdf_section_heading(line: str) -> bool:
    """Indica si una línea del PDF parece un encabezado de sección."""
    normalized = normalize_heading_label(line)
    exact_headings = {
        "contenidos",
        "contenido",
        "contenidos o bloques tematicos",
        "bloques tematicos",
        "bloques de contenido",
        "temario",
        "programa",
        "programa de la asignatura",
        "competencias",
        "datos basicos de la asignatura",
        "resultados del aprendizaje",
        "objetivos y resultados del aprendizaje",
        "actividades formativas y horas lectivas",
        "metodologia",
        "metodologia de ensenanza-aprendizaje",
        "evaluacion",
        "sistemas y criterios de evaluacion y calificacion",
        "bibliografia",
        "guia docente",
        "objetivos",
    }
    heading_prefixes = (
        "contenidos ",
        "temario ",
        "programa ",
        "competencias ",
        "objetivos ",
        "resultados del aprendizaje ",
        "metodologia ",
        "evaluacion ",
        "bibliografia ",
    )

    if normalized in exact_headings:
        return True

    if "bloques de contenido" in normalized:
        return True

    if normalized.startswith(heading_prefixes) and len(line) <= 120:
        return True

    if (
        len(line) <= 120
        and not line.endswith(".")
        and re.fullmatch(r"[A-ZÁÉÍÓÚÜÑa-záéíóúüñ0-9/() ,:+-]+", line)
        and any(keyword in normalized for keyword in ("contenidos", "temario", "programa", "metodologia", "evaluacion"))
    ):
        return True

    if line.isupper() and len(line) <= 100 and not line.endswith("."):
        return True

    return False


def is_pdf_hours_line(line: str) -> bool:
    """Indica si una línea del PDF corresponde a horas/carga docente."""
    normalized = normalize_heading_label(line)

    if "creditos u horas" in normalized:
        return True

    patterns = (
        r"^\d+(?:[.,]\d+)?\s*horas?\s*:\s*.*$",
        r"^\d+(?:[.,]\d+)?\s*horas?$",
        r"^\d+t\s*\d+p$",
        r"^\d+\s*t\s*\d+\s*p$",
        r"^total de clases,\s*creditos?\s*u\s*horas?$",
    )
    return any(re.match(pattern, normalized) for pattern in patterns)


def strip_pdf_hours_fragment(line: str) -> str:
    """Elimina de una línea el fragmento de horas cuando aparece incrustado."""
    cleaned_line = re.sub(
        r"\s+\d+(?:[.,]\d+)?\s*horas?\s*:\s*\d+\s*t\s*[+y]\s*\d+\s*p\b.*$",
        "",
        line,
        flags=re.IGNORECASE,
    )
    cleaned_line = re.sub(
        r"\s+\d+(?:[.,]\d+)?\s*horas?\s*:\s*.*$",
        "",
        cleaned_line,
        flags=re.IGNORECASE,
    )
    cleaned_line = re.sub(
        r"\btotal de clases,\s*cr[eé]ditos?\s*u\s*horas?\b",
        "",
        cleaned_line,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s{2,}", " ", cleaned_line).strip(" :-\t")


def infer_pdf_subject_name(lines: list[str], fallback_title: str) -> str:
    """Intenta inferir el nombre de la asignatura desde el texto del PDF."""
    explicit_label_patterns = (
        r"^nombre\s+asignatura\s*:\s*(.+)$",
        r"^nombre\s+de\s+la\s+asignatura\s*:\s*(.+)$",
        r"^asignatura\s*:\s*(.+)$",
        r"^denominacion\s*:\s*(.+)$",
        r"^denominación\s*:\s*(.+)$",
        r"^materia\s*:\s*(.+)$",
    )
    skip_prefixes = (
        "guía docente",
        "guia docente",
        "universidad de",
        "grado en",
        "doble grado en",
        "curso academico",
        "curso académico",
        "aprobada en",
    )
    generic_exact_lines = {
        "datos basicos de la asignatura",
        "guia docente",
        "universidad de alcala",
        "universidad de alcala",
        "programa de la asignatura",
    }

    for line in lines[:40]:
        for pattern in explicit_label_patterns:
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip(" .:-")
            if candidate:
                return candidate

    for line in lines[:25]:
        normalized = normalize_heading_label(line)
        if len(line) < 4 or len(line) > 120:
            continue
        if normalized in generic_exact_lines:
            continue
        if any(normalized.startswith(prefix) for prefix in skip_prefixes):
            continue
        if re.fullmatch(r"[A-Z0-9./ -]+", line) and len(line.split()) <= 2:
            continue
        if re.fullmatch(r"\d+(?:er|º|o|a)?\s*curso.*", normalized):
            continue
        return line

    return fallback_title


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extrae el texto de un PDF usando `pypdf`."""
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise UnsupportedGuideFormatError(
            "La guía está en PDF, pero falta la dependencia 'pypdf' para procesarla."
        ) from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_pages: list[str] = []
    for page in reader.pages:
        extracted_pages.append(page.extract_text() or "")

    text = "\n".join(extracted_pages).strip()
    if not text:
        raise UnsupportedGuideFormatError(
            "No se ha podido extraer texto legible del PDF de la guía docente."
        )

    return text


def build_pdf_html(pdf_text: str, pdf_title: str | None = None) -> str:
    """Convierte texto de PDF a un HTML simple reutilizable por el extractor."""
    lines = normalize_pdf_lines(pdf_text)
    fallback_title = (pdf_title or "Guía docente PDF").replace(".pdf", "").strip()
    subject_name = infer_pdf_subject_name(lines, fallback_title)

    body_parts: list[str] = [f"<h1>{html.escape(subject_name)}</h1>"]
    current_section_open = False

    for line in lines:
        cleaned_line = strip_pdf_hours_fragment(line)
        if not cleaned_line:
            continue

        if is_pdf_hours_line(cleaned_line):
            continue

        if is_pdf_section_heading(cleaned_line):
            heading_text = canonicalize_pdf_heading(cleaned_line)
            if normalize_heading_label(heading_text) == "guia docente":
                continue
            if current_section_open:
                body_parts.append("</section>")
            body_parts.append(f"<section><h2>{html.escape(heading_text)}</h2>")
            current_section_open = True
            continue

        body_parts.append(f"<p>{html.escape(cleaned_line)}</p>")

    if current_section_open:
        body_parts.append("</section>")

    body_html = "".join(body_parts)
    return (
        "<html><head>"
        f"<title>{html.escape(subject_name)}</title>"
        "</head><body><main>"
        f"{body_html}"
        "</main></body></html>"
    )


def build_pdf_html_from_bytes(pdf_bytes: bytes, pdf_title: str | None = None) -> str:
    """Extrae el texto de un PDF y lo transforma en un HTML sintético."""
    pdf_text = extract_text_from_pdf_bytes(pdf_bytes)
    return build_pdf_html(pdf_text, pdf_title=pdf_title)


def build_pdf_html_from_file(pdf_path: str | Path) -> str:
    """Extrae el texto de un PDF local y lo transforma en HTML sintético."""
    local_path = Path(pdf_path)
    pdf_bytes = local_path.read_bytes()
    return build_pdf_html_from_bytes(pdf_bytes, pdf_title=local_path.name)


# Uniovi origin strategy

def extract_uniovi_ajax_urls(html_text: str) -> tuple[str | None, str | None]:
    """Extrae las URLs AJAX usadas por UniOvi para cargar la guía docente."""
    ajax_urls = re.findall(r"A\.io\.request\('([^']+)'", html_text)
    if len(ajax_urls) < 2:
        return None, None

    return ajax_urls[0], ajax_urls[1]


def fetch_uniovi_guide_html(
    html_text: str,
    session: requests.Session,
) -> str | None:
    """Recupera el HTML dinámico de la guía docente en páginas de UniOvi."""
    metadata_url, guide_url = extract_uniovi_ajax_urls(html_text)
    if not metadata_url or not guide_url:
        return None

    metadata_response = session.get(
        metadata_url,
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=(10, 30),
    )
    metadata_response.raise_for_status()

    guides = json.loads(metadata_response.text)
    if not guides:
        return None

    guide_id = guides[0].get("guiaDocenteId")
    if not guide_id:
        return None

    guide_response = session.post(
        guide_url,
        data={"_es_uniovi_sies_web_UnioviSiesWebPortlet_guiaDocenteId": guide_id},
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=(10, 30),
    )
    guide_response.raise_for_status()

    return guide_response.text.strip() or None


def enrich_uniovi_html(html_text: str, session: requests.Session, _: str) -> str:
    """Añade al HTML principal la guía docente dinámica de UniOvi cuando exista."""
    try:
        guide_html = fetch_uniovi_guide_html(html_text, session)
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return html_text

    if not guide_html:
        return html_text

    wrapper = wrap_html_section(
        "codex-uniovi-guia-docente",
        "Guía docente cargada dinámicamente",
        guide_html,
    )
    if "</body>" in html_text:
        return html_text.replace("</body>", f"{wrapper}</body>", 1)
    return f"{html_text}\n{wrapper}"


# Generic destination strategies

def fetch_embedded_base64_pdf_html(url: str, session: requests.Session) -> str | None:
    """Recupera una guía cuando la página incrusta un PDF en base64."""
    parsed_url = urlparse(url)
    if "uah.es" not in parsed_url.netloc.lower():
        return None
    if "/descarga-de-ficheros/" not in parsed_url.path:
        return None

    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    html_text = response.text

    match = re.search(
        r'<embed[^>]+title="([^"]+)"[^>]+src="data:application/pdf;base64,([^"]+)"',
        html_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    pdf_title = match.group(1).strip()
    pdf_base64 = match.group(2).strip()
    pdf_bytes = base64.b64decode(pdf_base64)
    return build_pdf_html_from_bytes(pdf_bytes, pdf_title=pdf_title)


def parse_snapshot_api_reference(url: str) -> tuple[str, str] | None:
    """Extrae curso académico y código de asignatura desde una URL snapshot."""
    match = re.search(r"/snapshots/([^/]+)/([^/?#]+)", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def get_snapshot_api_subject_title(snapshot_data: dict[str, object]) -> str | None:
    """Obtiene el nombre de la asignatura desde una respuesta JSON snapshot."""
    i18n_entries = snapshot_data.get("i18n")
    if not isinstance(i18n_entries, list):
        return None

    preferred_entry = None
    for entry in i18n_entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        lang = str(entry.get("lang") or "").strip().lower()
        if name and lang == "es":
            preferred_entry = entry
            break
        if name and preferred_entry is None:
            preferred_entry = entry

    if not preferred_entry:
        return None

    return str(preferred_entry.get("name") or "").strip() or None


def build_snapshot_api_contents_html(contents: object) -> str:
    """Convierte la lista de contenidos snapshot a HTML académico simple."""
    if not isinstance(contents, list):
        return "<p>No se han encontrado contenidos estructurados.</p>"

    filtered_contents: list[dict[str, object]] = []
    for entry in contents:
        if not isinstance(entry, dict):
            continue
        lang = str(entry.get("lang") or "").strip().lower()
        if lang == "es":
            filtered_contents.append(entry)

    if not filtered_contents:
        filtered_contents = [entry for entry in contents if isinstance(entry, dict)]

    filtered_contents.sort(key=lambda item: item.get("sequence") or 0)

    items_html: list[str] = []
    for entry in filtered_contents:
        title = str(entry.get("description") or "").strip()
        details = str(entry.get("comments") or "").strip()
        if not title and not details:
            continue

        title_html = f"<strong>{html.escape(title)}</strong>" if title else ""
        details_html = html.escape(details)
        items_html.append(f"<li>{title_html} {details_html}</li>".strip())

    if not items_html:
        return "<p>No se han encontrado contenidos estructurados.</p>"

    return "<ul>" + "".join(items_html) + "</ul>"


def build_snapshot_api_response_html(snapshot_data: dict[str, object]) -> str:
    """Transforma una respuesta snapshot JSON en HTML reutilizable por el extractor."""
    title = get_snapshot_api_subject_title(snapshot_data) or "Asignatura sin título"
    credits = str(snapshot_data.get("credits") or "").strip()

    i18n_entries = snapshot_data.get("i18n")
    degree = ""
    school = ""
    if isinstance(i18n_entries, list):
        for entry in i18n_entries:
            if not isinstance(entry, dict):
                continue
            lang = str(entry.get("lang") or "").strip().lower()
            if lang != "es":
                continue
            degree = str(entry.get("degree") or "").strip()
            school = str(entry.get("school") or "").strip()
            if degree or school:
                break

    credits_html = (
        f"<p><strong>Créditos ECTS:</strong> {html.escape(credits)}</p>"
        if credits
        else ""
    )
    degree_html = (
        f"<p><strong>Titulación:</strong> {html.escape(degree)}</p>"
        if degree
        else ""
    )
    school_html = f"<p><strong>Centro:</strong> {html.escape(school)}</p>" if school else ""
    contents_html = build_snapshot_api_contents_html(snapshot_data.get("contents"))

    return (
        "<html><head>"
        f"<title>{html.escape(title)}</title>"
        "</head><body>"
        "<main>"
        f"<h1>{html.escape(title)}</h1>"
        f"{degree_html}"
        f"{school_html}"
        f"{credits_html}"
        "<section>"
        "<h2>Contenidos</h2>"
        f"{contents_html}"
        "</section>"
        "</main>"
        "</body></html>"
    )


def fetch_snapshot_api_html(url: str, session: requests.Session) -> str | None:
    """Recupera y convierte a HTML una guía disponible a través de snapshot JSON."""
    parsed_parts = parse_snapshot_api_reference(url)
    if not parsed_parts:
        return None

    academic_year, subject_code = parsed_parts
    api_url = f"https://guiadocenteapi.unileon.es/snapshots/{academic_year}/{subject_code}"
    response = session.get(
        api_url,
        headers={"Accept": "application/json"},
        timeout=(10, 30),
    )
    response.raise_for_status()

    payload = response.json()
    snapshot_data = payload.get("data")
    if not isinstance(snapshot_data, dict):
        return None

    return build_snapshot_api_response_html(snapshot_data)


SCRAPER_STRATEGIES = (
    ScraperStrategy(
        name="embedded_base64_pdf",
        description="Página HTML que incrusta la guía docente como PDF en base64.",
        host_patterns=("uah.es",),
        direct_fetcher=fetch_embedded_base64_pdf_html,
    ),
    ScraperStrategy(
        name="snapshot_api_html",
        description="Visor con API JSON snapshot que requiere reconstrucción a HTML académico.",
        host_patterns=("visor-guiadocente.unileon.es",),
        direct_fetcher=fetch_snapshot_api_html,
    ),
    ScraperStrategy(
        name="uniovi_ajax_html",
        description="Ficha HTML con guía docente cargada dinámicamente por AJAX en UniOvi.",
        host_patterns=("uniovi.es",),
        html_enricher=enrich_uniovi_html,
    ),
)


def get_matching_strategies(url: str) -> list[ScraperStrategy]:
    """Devuelve las estrategias aplicables a una URL."""
    return [
        strategy
        for strategy in SCRAPER_STRATEGIES
        if matches_host(url, strategy.host_patterns)
    ]


def fetch_with_direct_strategy(
    url: str,
    session: requests.Session,
    strategies: list[ScraperStrategy],
) -> FetchResult | None:
    """Intenta obtener el contenido con una estrategia específica de portal."""
    for strategy in strategies:
        if strategy.direct_fetcher is None:
            continue

        html_text = strategy.direct_fetcher(url, session)
        if html_text:
            return FetchResult(
                url=url,
                html=html_text,
                strategy_name=strategy.name,
                strategy_description=strategy.description,
            )

    return None


def enrich_with_strategies(
    url: str,
    html_text: str,
    session: requests.Session,
    strategies: list[ScraperStrategy],
) -> FetchResult:
    """Aplica enriquecimientos específicos sobre el HTML ya descargado."""
    enriched_html = html_text
    applied_strategy: ScraperStrategy | None = None
    for strategy in strategies:
        if strategy.html_enricher is None:
            continue
        candidate_html = strategy.html_enricher(enriched_html, session, url)
        if candidate_html != enriched_html:
            applied_strategy = strategy
        enriched_html = candidate_html

    if applied_strategy is not None:
        return FetchResult(
            url=url,
            html=enriched_html,
            strategy_name=applied_strategy.name,
            strategy_description=applied_strategy.description,
        )

    return FetchResult(
        url=url,
        html=enriched_html,
        strategy_name="generic_html",
        strategy_description="Descarga HTML genérica sin adaptador específico.",
    )


def ensure_supported_html_response(response: requests.Response) -> None:
    """Verifica que la respuesta descargada siga dentro del alcance actual."""
    content_type = response.headers.get("content-type", "").lower()
    parsed_url = urlparse(response.url)

    if parsed_url.path.lower().endswith(".pdf") or "application/pdf" in content_type:
        raise UnsupportedGuideFormatError("PDF_DIRECT_RESPONSE")


def fetch_page(url: str) -> FetchResult:
    """Descarga una guía docente aplicando estrategias específicas y fallback genérico."""
    session = build_session()
    strategies = get_matching_strategies(url)

    direct_result = fetch_with_direct_strategy(url, session, strategies)
    if direct_result is not None:
        return direct_result

    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    try:
        ensure_supported_html_response(response)
    except UnsupportedGuideFormatError as exc:
        if str(exc) != "PDF_DIRECT_RESPONSE":
            raise

        pdf_title = response.url.rsplit("/", maxsplit=1)[-1]
        pdf_html = build_pdf_html_from_bytes(response.content, pdf_title=pdf_title)
        return FetchResult(
            url=response.url,
            html=pdf_html,
            strategy_name="remote_pdf",
            strategy_description="Extracción básica de texto desde un PDF accesible por URL directa.",
        )

    html_text = response.text

    return enrich_with_strategies(response.url, html_text, session, strategies)


def fetch_html(url: str) -> str:
    """Descarga y devuelve el HTML de una URL.

    Esta función se mantiene por compatibilidad con el resto del proyecto.
    """
    return fetch_page(url).html
