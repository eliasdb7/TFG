"""Punto de entrada principal para la V1 del proyecto."""

from __future__ import annotations

from src.input_sources import prompt_origin_uniovi_url, prompt_target_request
from src.pipeline import run_pipeline


def main() -> None:
    """Ejecuta la V1 del pipeline con origen Uniovi y un destino configurable."""
    print("Herramienta V1 de apoyo a convalidaciones SICUE")

    url_origen = prompt_origin_uniovi_url()
    destino = prompt_target_request()

    print("\nResumen de la ejecucion:")
    print(f"- URL origen Uniovi: {url_origen}")
    print(f"- Modo de entrada destino: {destino.get('input_mode')}")
    print(f"- Referencia destino: {destino.get('source_reference')}")

    print("\nEjecutando comparación inicial del pipeline.\n")
    run_pipeline(url_origen, [destino])


if __name__ == "__main__":
    main()
