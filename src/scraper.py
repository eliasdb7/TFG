"""Funciones para la descarga del contenido HTML."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
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


def parse_unileon_snapshot_url(url: str) -> tuple[str, str] | None:
    """Extrae curso académico y código de asignatura desde una URL de UniLeón."""
    match = re.search(r"/snapshots/([^/]+)/([^/?#]+)", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def get_unileon_subject_title(snapshot_data: dict[str, object]) -> str | None:
    """Obtiene el nombre de la asignatura desde el JSON de UniLeón."""
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


def build_unileon_contents_html(contents: object) -> str:
    """Convierte la lista de contenidos de UniLeón a HTML académico simple."""
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


def build_unileon_snapshot_html(snapshot_data: dict[str, object]) -> str:
    """Transforma el JSON de UniLeón en un HTML simple reutilizable por el extractor."""
    title = get_unileon_subject_title(snapshot_data) or "Asignatura sin título"
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
    contents_html = build_unileon_contents_html(snapshot_data.get("contents"))

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


def fetch_unileon_snapshot_html(url: str, session: requests.Session) -> str | None:
    """Recupera y convierte a HTML las guías del visor de UniLeón."""
    parsed_parts = parse_unileon_snapshot_url(url)
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

    return build_unileon_snapshot_html(snapshot_data)


SCRAPER_STRATEGIES = (
    ScraperStrategy(
        name="unileon_snapshot_api",
        description="Visor SPA con API JSON propia de la Universidad de León.",
        host_patterns=("visor-guiadocente.unileon.es",),
        direct_fetcher=fetch_unileon_snapshot_html,
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
        raise UnsupportedGuideFormatError(
            "La guía encontrada está en formato PDF y todavía no está soportada en la versión actual."
        )


def fetch_page(url: str) -> FetchResult:
    """Descarga una guía docente aplicando estrategias específicas y fallback genérico."""
    session = build_session()
    strategies = get_matching_strategies(url)

    direct_result = fetch_with_direct_strategy(url, session, strategies)
    if direct_result is not None:
        return direct_result

    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    ensure_supported_html_response(response)
    html_text = response.text

    return enrich_with_strategies(response.url, html_text, session, strategies)


def fetch_html(url: str) -> str:
    """Descarga y devuelve el HTML de una URL.

    Esta función se mantiene por compatibilidad con el resto del proyecto.
    """
    return fetch_page(url).html
