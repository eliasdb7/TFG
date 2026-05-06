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

## Cómo funciona la similitud en la V1

La versión actual calcula una similitud inicial basada en:

- similitud del nombre de la asignatura
- similitud del bloque de contenidos

Ambas se calculan mediante:

- limpieza y normalización de texto
- vectorización `TF-IDF`
- `cosine similarity`

La combinación actual es:

- `30%` similitud del nombre
- `70%` similitud de contenidos

Además, los créditos ECTS se analizan como una señal auxiliar:

- coincidencia exacta
- compatibilidad con margen
- diferencia relevante

Esta señal todavía no modifica el valor numérico de similitud, pero sí se utiliza para generar una interpretación textual de afinidad.

## Estrategia de scraping

La herramienta utiliza una arquitectura de scraping por capas:

- `generic_html`: descarga HTML general para guías donde la información ya está presente en la página.
- adaptadores específicos por portal: se activan cuando una universidad publica sus guías mediante estructuras no estándar, como AJAX o APIs JSON.

Actualmente se incluyen adaptadores para:

- `uniovi_ajax_html`: Universidad de Oviedo
- `unileon_snapshot_api`: Universidad de León
- `uah_embedded_pdf`: Universidad de Alcalá cuando la guía se incrusta como PDF en una página HTML

Además, el sistema incluye una vía básica para PDFs accesibles por URL directa:

- `generic_pdf`: descarga el PDF, extrae su texto y genera un HTML sintético para reutilizar el extractor actual

Si una universidad de destino no dispone todavía de adaptador, el sistema intenta primero el scraping genérico. Si la guía está en PDF, el sistema intenta una extracción básica de texto. Si no puede extraerse texto legible, el pipeline lo informa mediante warnings.

## Resultados guardados

En cada ejecución con comparaciones destino, la herramienta guarda:

- `resultados/logs_pipeline.txt`: traza técnica del pipeline
- `resultados/resultados_comparacion.json`: resultado completo estructurado
- `resultados/resultados_comparacion.csv`: resumen tabular para análisis y memoria

## Módulos principales de `src/`

- `scraper.py`: descarga HTML y aplica estrategias específicas por universidad cuando es necesario
- `extractor.py`: realiza una extracción básica de nombre, ECTS y contenidos
- `text_processing.py`: incluye una normalización inicial del texto
- `similarity.py`: reserva el espacio para la futura lógica de similitud
  Actualmente calcula similitud TF-IDF, señal auxiliar de ECTS y afinidad interpretativa.
- `decision.py`: reserva el espacio para la futura lógica de decisión
- `pipeline.py`: coordina el flujo de descarga, extracción y salida por consola
- `utils.py`: reúne utilidades auxiliares
- `dev_logger.py`: documenta cada paso del pipeline con mensajes reutilizables para la memoria del TFG
