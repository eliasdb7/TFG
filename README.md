# TFG - Convalidaciones SICUE con NLP

Trabajo Fin de Grado orientado al desarrollo de una herramienta de apoyo a convalidaciones SICUE entre universidades españolas mediante comparación automática de guías docentes.

## Estructura
- `src/`: código fuente
- `docs/`: notas, diseño y documentación
- `figuras/`: figuras para la memoria
- `resultados/`: salidas generadas
- `Archivos/`: materiales de apoyo no versionados
- `data/`: datos de trabajo no versionados

## Ejecución inicial

1. Instalar dependencias:
   `pip install -r requirements.txt`
2. Ejecutar la versión base:
   `python main.py`

## Estrategia de scraping

La herramienta utiliza una arquitectura de scraping por capas:

- `generic_html`: descarga HTML general para guías donde la información ya está presente en la página.
- adaptadores específicos por portal: se activan cuando una universidad publica sus guías mediante estructuras no estándar, como AJAX o APIs JSON.

Actualmente se incluyen adaptadores para:

- `uniovi_ajax_html`: Universidad de Oviedo
- `unileon_snapshot_api`: Universidad de León

Si una universidad de destino no dispone todavía de adaptador, el sistema intenta primero el scraping genérico. Si la guía está en PDF, el sistema informa de que ese formato aún no está soportado en la versión actual.

## Módulos principales de `src/`

- `scraper.py`: descarga HTML y aplica estrategias específicas por universidad cuando es necesario
- `extractor.py`: realiza una extracción básica de nombre, ECTS y contenidos
- `text_processing.py`: incluye una normalización inicial del texto
- `similarity.py`: reserva el espacio para la futura lógica de similitud
- `decision.py`: reserva el espacio para la futura lógica de decisión
- `pipeline.py`: coordina el flujo de descarga, extracción y salida por consola
- `utils.py`: reúne utilidades auxiliares
- `dev_logger.py`: documenta cada paso del pipeline con mensajes reutilizables para la memoria del TFG
