"""Registro simple y estructurado del proceso del pipeline."""

from __future__ import annotations

from pathlib import Path


LOG_FILE_PATH = Path("resultados/logs_pipeline.txt")


def log_step(step_name: str, description: str) -> None:
    """Muestra un paso del pipeline y lo guarda opcionalmente en un fichero.

    Los mensajes se redactan en un tono académico sencillo para poder
    reutilizarse en la memoria del TFG.

    Args:
        step_name: Nombre breve del paso del proceso.
        description: Descripción del objetivo del paso.
    """
    message = f"[STEP] {step_name}\nDescripción: {description}\n"
    print(message)

    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")


def reset_log() -> None:
    """Reinicia el fichero de trazas del pipeline si existe."""
    if LOG_FILE_PATH.exists():
        LOG_FILE_PATH.unlink()
