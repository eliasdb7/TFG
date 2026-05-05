"""Funciones para la descarga del contenido HTML."""

from __future__ import annotations

import json
import re

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


def extract_uniovi_ajax_urls(html: str) -> tuple[str | None, str | None]:
    """Extrae las URLs AJAX usadas por UniOvi para cargar la guía docente."""
    ajax_urls = re.findall(r"A\.io\.request\('([^']+)'", html)
    if len(ajax_urls) < 2:
        return None, None

    metadata_url = ajax_urls[0]
    guide_url = ajax_urls[1]
    return metadata_url, guide_url


def fetch_uniovi_guide_html(
    html: str,
    session: requests.Session,
) -> str | None:
    """Recupera el HTML dinámico de la guía docente en páginas de UniOvi.

    Algunas fichas de asignatura de la Universidad de Oviedo cargan la guía
    docente real mediante peticiones AJAX. Esta función intenta resolver ese
    contenido adicional y devolverlo como HTML.
    """
    metadata_url, guide_url = extract_uniovi_ajax_urls(html)
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


def enrich_uniovi_html(html: str, session: requests.Session) -> str:
    """Añade al HTML principal la guía docente dinámica de UniOvi cuando exista."""
    try:
        guide_html = fetch_uniovi_guide_html(html, session)
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return html

    if not guide_html:
        return html

    wrapper = (
        '\n<section id="codex-uniovi-guia-docente">'
        '<h2>Guía docente cargada dinámicamente</h2>'
        f"{guide_html}</section>\n"
    )
    if "</body>" in html:
        return html.replace("</body>", f"{wrapper}</body>", 1)
    return f"{html}\n{wrapper}"


def fetch_html(url: str) -> str:
    """Descarga y devuelve el HTML de una URL.

    Args:
        url: Dirección web de la guía docente.

    Returns:
        El contenido HTML de la página.

    Raises:
        requests.RequestException: Si ocurre un error en la petición HTTP.
    """
    session = build_session()
    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    html = response.text

    if "uniovi.es" in response.url:
        html = enrich_uniovi_html(html, session)

    return html
