"""Punto de entrada principal para la V1 del proyecto."""

from __future__ import annotations

from src.pipeline import run_pipeline


def main() -> None:
    """Ejecuta la V1.2 del pipeline con entrada básica por consola."""
    default_origin_url = "https://www.example.com"

    print("Herramienta V1 de apoyo a convalidaciones SICUE")
    user_origin_url = input(
        f"Introduce la URL de la asignatura origen [{default_origin_url}]: "
    ).strip()
    url_origen = user_origin_url or default_origin_url

    user_destination_urls = input(
        "Introduce URLs destino separadas por coma o pulsa Enter para omitirlas: "
    ).strip()
    if user_destination_urls:
        urls_destino = [
            url.strip() for url in user_destination_urls.split(",") if url.strip()
        ]
    else:
        urls_destino = []

    if urls_destino:
        print("\nSe procesarán las siguientes URLs destino:")
        for url_destino in urls_destino:
            print(f"- {url_destino}")
    else:
        print("\nNo se han indicado URLs destino. En esta ejecución solo se analizará la asignatura origen.")

    print("\nEjecutando comparación inicial del pipeline.\n")
    run_pipeline(url_origen, urls_destino)


if __name__ == "__main__":
    main()
