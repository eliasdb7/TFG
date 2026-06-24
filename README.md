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

## Flujo de entrada actual

La versión actual asume que:

- la asignatura de origen se introduce siempre mediante una guía docente de Uniovi
- la asignatura de destino puede introducirse de tres formas:
  - URL de guía docente
  - contenidos pegados manualmente por consola
  - PDF local de la guía docente

## Cómo funciona la similitud en la V1

La versión actual calcula una similitud inicial basada principalmente en:

- similitud del bloque de contenidos

La puntuación principal se calcula mediante:

- limpieza y normalización de texto
- vectorización `TF-IDF`
- `cosine similarity`

La puntuación final actual es:

- `100%` similitud de contenidos

Además, se muestran como señales auxiliares:

- similitud del nombre de la asignatura
- compatibilidad de créditos ECTS

Además, los créditos ECTS se analizan como una señal auxiliar:

- coincidencia exacta
- compatibilidad con margen
- diferencia relevante

Esta señal todavía no modifica el valor numérico de similitud, pero sí se utiliza para generar una interpretación textual de afinidad.

## Estrategia de scraping

La herramienta utiliza una arquitectura de scraping por capas:

- `uniovi_ajax_html`: estrategia específica para la asignatura de origen en Uniovi.
- `generic_html`: descarga HTML general para guías donde la información ya está presente en la página.
- estrategias técnicas de destino: se activan cuando la guía requiere un tratamiento especial por el formato de publicación.

Actualmente se incluyen estrategias de destino para patrones como:

- `snapshot_api_html`: visor con API JSON snapshot
- `embedded_base64_pdf`: página HTML que incrusta un PDF en base64

Además, el sistema incluye una vía básica para PDFs accesibles por URL directa:

- `remote_pdf`: descarga el PDF, extrae su texto y genera un HTML sintético para reutilizar el extractor actual

Si una guía de destino no dispone todavía de una estrategia especial, el sistema intenta primero el scraping genérico. Si la guía está en PDF, el sistema intenta una extracción básica de texto. Si no puede extraerse texto legible, el pipeline lo informa mediante warnings.

## Resultados guardados

En cada ejecución con comparaciones destino, la herramienta guarda:

- `resultados/logs_pipeline.txt`: traza técnica del pipeline
- `resultados/resultados_comparacion.json`: resultado completo estructurado
- `resultados/resultados_comparacion.csv`: resumen tabular para análisis y memoria

## Módulos principales de `src/`

- `scraper.py`: descarga HTML y aplica estrategias específicas por tipo de fuente cuando es necesario
- `input_sources.py`: gestiona la entrada interactiva de origen Uniovi y destino por URL, texto manual o PDF local
- `extractor.py`: realiza una extracción básica de nombre, ECTS y contenidos
- `text_processing.py`: incluye una normalización inicial del texto
- `similarity.py`: reserva el espacio para la futura lógica de similitud
  Actualmente calcula similitud TF-IDF por contenidos, similitud auxiliar de nombre, señal auxiliar de ECTS y afinidad interpretativa.
- `decision.py`: reserva el espacio para la futura lógica de decisión
- `pipeline.py`: coordina el flujo de descarga, extracción y salida por consola
- `utils.py`: reúne utilidades auxiliares
- `dev_logger.py`: documenta cada paso del pipeline con mensajes reutilizables para la memoria del TFG
