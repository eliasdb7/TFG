# TFG - Convalidaciones SICUE con NLP

Este `README.md` describe el estado de la rama `version_01` y documenta la version funcional 01 del proyecto.

Trabajo Fin de Grado orientado al desarrollo de una herramienta de apoyo a convalidaciones SICUE entre universidades españolas mediante comparación automática de guías docentes.

## Version 01

La `version_01` corresponde a la primera version funcional del proyecto.

Su objetivo es ofrecer una herramienta base, ejecutada por consola, capaz de:

- recibir una asignatura de origen desde una guía docente de Uniovi
- recibir una asignatura de destino por URL, texto manual o PDF local
- extraer nombre, ECTS y contenidos cuando sea posible
- calcular una similitud léxica inicial entre asignaturas
- guardar resultados y trazas para análisis posterior

Esta version debe entenderse como una base operativa y validable del TFG, no como la version definitiva del sistema.

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

## Alcance de esta version

La `version_01` incluye:

- entrada interactiva por consola
- asignatura de origen siempre asociada a Uniovi
- asignatura de destino por tres vias:
  - URL de guía docente
  - texto manual pegado por consola
  - PDF local
- scraping HTML con soporte de estrategias por tipo de fuente
- extracción heurística de nombre, ECTS y contenidos
- comparación léxica basada en `TF-IDF` y similitud coseno
- guardado de resultados en `JSON`, `CSV` y log técnico

La `version_01` no incluye:

- embeddings
- similitud semántica profunda
- recuperación avanzada
- modelos de IA o LLMs
- decisión final automática de convalidación
- interfaz gráfica

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

## Diferencia frente a versiones posteriores

Esta rama `version_01` debe leerse como una version léxica, heurística y orientada a validación funcional.

Si en versiones posteriores se incorporan nuevas capacidades, estas no forman parte de la `version_01`. En particular, quedan fuera de esta versión:

- similitud semántica basada en embeddings
- comparación por fragmentos semánticos
- reranking o modelos más complejos de comparación
- ampliaciones experimentales que cambien el criterio principal de similitud

Por tanto, cualquier lectura de este `README.md` debe asumir que el comportamiento documentado aquí describe exclusivamente la version funcional 01.

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

Los resultados de esta version registran también:

- modo de entrada de la asignatura origen y destino
- referencia de entrada usada en destino
- estrategia de scraping aplicada cuando procede

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

## Estado actual de la version 01

En el cierre de esta version funcional, el proyecto ya permite ejecutar comparaciones manuales útiles y reproducibles.

Los siguientes aspectos quedan explícitamente abiertos para iteraciones futuras:

- ampliar la robustez frente a más formatos reales de guías docentes
- refinar la extracción de contenidos en PDFs complejos
- diseñar una lógica de decisión final de convalidación
- evaluar si en futuras versiones conviene añadir una capa semántica
