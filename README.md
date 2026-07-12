# TFG - Convalidaciones SICUE con NLP

Este `README.md` describe el estado de la rama `version_02`.

Trabajo Fin de Grado orientado al desarrollo de una herramienta de apoyo a convalidaciones SICUE entre universidades espanolas mediante comparacion automatica de guias docentes.

## Estructura
- `src/`: codigo fuente
- `docs/`: notas, diseno y documentacion
- `figuras/`: figuras para la memoria
- `resultados/`: salidas generadas
- `Archivos/`: materiales de apoyo no versionados
- `data/`: datos de trabajo no versionados

## Ejecucion inicial

1. Instalar dependencias:
   `pip install -r requirements.txt`
2. Ejecutar la version base:
   `python main.py`

## Flujo de entrada actual

La version actual asume que:

- la asignatura de origen se introduce siempre mediante una guia docente de Uniovi
- las asignaturas de destino pueden introducirse una a una en numero variable
- cada asignatura destino puede introducirse de tres formas:
  - URL de guia docente
  - contenidos pegados manualmente por consola
  - PDF local de la guia docente

## Como funciona la similitud en la V2

La version actual mantiene el pipeline de extraccion de la V1, pero sustituye el motor de comparacion por una comparacion semantica de contenidos.

La herramienta calcula:

- una similitud semantica de contenidos mediante embeddings multilingues
- una senal auxiliar de compatibilidad ECTS
- una afinidad interpretada derivada de la similitud semantica y del contexto ECTS
- una capa de explicabilidad basada en los fragmentos origen/destino mas cercanos
- un ranking final cuando se comparan varias asignaturas destino

La puntuacion principal de la V2 es:

- `100%` similitud semantica de contenidos

En esta version ya no se utiliza:

- similitud del nombre de la asignatura
- similitud lexica TF-IDF como parte del resultado principal
- una "similitud total" separada de la semantica

Los ECTS no alteran el valor numerico principal, pero si ayudan a contextualizar el resultado final.

## Motor semantico de la V2

La V2 utiliza un modelo multilingue de `sentence-transformers` para representar semanticamente los contenidos de las asignaturas.

La estrategia general es:

- limpiar el texto de contenidos
- segmentarlo en fragmentos manejables
- generar embeddings para cada fragmento
- comparar origen y destino mediante similitud coseno en el espacio semantico
- agregar los mejores emparejamientos de forma bidireccional mediante una media recortada inferior

Esto permite detectar afinidad entre asignaturas aunque los contenidos no coincidan literalmente en el vocabulario utilizado.

La interpretacion actual del porcentaje semantico sigue estos umbrales:

- `>= 62%`: afinidad alta
- `>= 47%` y `< 62%`: afinidad media
- `< 47%`: afinidad baja

La salida tambien conserva una capa de explicabilidad con los fragmentos origen/destino mas cercanos que sostienen el resultado.

## Estrategia de scraping

La herramienta utiliza una arquitectura de scraping por capas:

- `uniovi_ajax_html`: estrategia especifica para la asignatura de origen en Uniovi
- `generic_html`: descarga HTML general para guias donde la informacion ya esta presente en la pagina
- estrategias tecnicas de destino: se activan cuando la guia requiere un tratamiento especial por el formato de publicacion

Actualmente se incluyen estrategias de destino para patrones como:

- `snapshot_api_html`: visor con API JSON snapshot
- `embedded_base64_pdf`: pagina HTML que incrusta un PDF en base64

Ademas, el sistema incluye una via basica para PDFs accesibles por URL directa:

- `remote_pdf`: descarga el PDF, extrae su texto y genera un HTML sintetico para reutilizar el extractor actual

Si una guia de destino no dispone todavia de una estrategia especial, el sistema intenta primero el scraping generico. Si la guia esta en PDF, el sistema intenta una extraccion basica de texto. Si no puede extraerse texto legible, el pipeline lo informa mediante warnings.

## Resultados guardados

En cada ejecucion con comparaciones destino, la herramienta guarda:

- `resultados/logs_pipeline.txt`: traza tecnica del pipeline
- `resultados/resultados_comparacion.json`: resultado completo estructurado
- `resultados/resultados_comparacion.csv`: resumen tabular para analisis y memoria

La V2 guarda ademas metadatos tecnicos del calculo semantico, como:

- similitud semantica de contenidos
- modelo semantico utilizado
- backend de embeddings
- estrategia de segmentacion
- numero de fragmentos de origen y destino
- pares de fragmentos mas parecidos para justificar el resultado
- posicion en el ranking final de destinos comparados
- modo de entrada utilizado para cada destino
- referencia original usada para cada comparacion

Ademas, el trabajo incluye artefactos de validacion y analisis en:

- `resultados/validacion_v01/`
- `resultados/validacion_v02/`

## Modulos principales de `src/`

- `scraper.py`: descarga HTML y aplica estrategias especificas por tipo de fuente cuando es necesario
- `input_sources.py`: gestiona la entrada interactiva de origen Uniovi y destino por URL, texto manual o PDF local
- `extractor.py`: realiza una extraccion basica de nombre, ECTS y contenidos
- `text_processing.py`: incluye una normalizacion inicial del texto
- `semantic_similarity.py`: genera embeddings, segmenta contenidos y calcula la similitud semantica principal de la V2
- `similarity.py`: coordina la comparacion semantica principal, la senal ECTS y la afinidad interpretativa
- `decision.py`: reserva el espacio para la futura logica de decision
- `pipeline.py`: coordina el flujo de descarga, extraccion y salida por consola
- `utils.py`: reune utilidades auxiliares
- `dev_logger.py`: documenta cada paso del pipeline con mensajes reutilizables para la memoria del TFG
