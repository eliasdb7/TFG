"""Punto de entrada principal para la V2 del proyecto."""

from __future__ import annotations

from src.input_sources import prompt_origin_uniovi_url, prompt_target_requests
from src.pipeline import run_pipeline


def main() -> None:
    """Ejecuta la V2 del pipeline con origen Uniovi y uno o varios destinos."""
    print("Herramienta V2 de apoyo a convalidaciones SICUE")

    url_origen = prompt_origin_uniovi_url()
    destinos = prompt_target_requests()

    print("\nResumen de la ejecucion:")
    print(f"- URL origen Uniovi: {url_origen}")
    print(f"- Numero de asignaturas destino: {len(destinos)}")
    for index, destino in enumerate(destinos, start=1):
        print(
            f"- Destino {index}: modo={destino.get('input_mode')} | "
            f"referencia={destino.get('source_reference')}"
        )

    print("\nEjecutando comparación semántica del pipeline.\n")
    run_pipeline(url_origen, destinos)


if __name__ == "__main__":
    main()
