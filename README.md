# TFG - Herramienta de apoyo a convalidaciones SICUE

Este repositorio contiene el desarrollo del Trabajo Fin de Grado orientado a comparar asignaturas universitarias a partir de sus guias docentes para apoyar procesos de movilidad SICUE.

El estado actual de `master` corresponde a la version final implementada en el proyecto:

- origen siempre introducido mediante guia docente de la Universidad de Oviedo
- uno o varios destinos introducidos por URL, texto manual o PDF local
- scraping y extraccion documental
- comparacion semantica de contenidos
- explicabilidad basada en fragmentos proximos
- ranking final de varias asignaturas destino

## Objetivo del proyecto

La herramienta busca reducir el esfuerzo preliminar de analisis cuando un estudiante necesita valorar la afinidad entre una asignatura de origen y una o varias asignaturas de destino. El sistema no toma decisiones de convalidacion, sino que ofrece una ayuda tecnica para priorizar comparaciones y justificar el resultado obtenido.

## Que hace actualmente

- recupera la asignatura de origen desde una URL de Uniovi
- admite destinos por URL de guia docente, texto pegado manualmente o PDF local
- extrae nombre, contenidos y creditos ECTS cuando estan disponibles
- representa semanticamente los contenidos con `sentence-transformers`
- calcula una similitud semantica principal basada al `100%` en contenidos
- conserva los ECTS como senal auxiliar de contexto
- muestra fragmentos origen-destino proximos para explicar la afinidad
- ordena varios destinos por porcentaje de similitud y genera un ranking final
- exporta resultados en consola, `JSON`, `CSV` y log tecnico

## Estructura del repositorio

- `main.py`: punto de entrada interactivo
- `src/`: modulos del pipeline
- `docs/`: memoria, notas tecnicas y registros de desarrollo
- `figuras/`: material grafico de apoyo
- `resultados/`: resultados de comparacion y validacion
- `data/`: conjuntos de apoyo y validacion
- `models/`: recursos descargados o persistidos localmente por el motor semantico

## Requisitos

- Python 3.10 o superior recomendado
- dependencias de `requirements.txt`
- conexion a internet para scraping y, en la primera ejecucion semantica, para descargar el modelo si no existe en cache local

Dependencias principales:

- `requests`
- `beautifulsoup4`
- `scikit-learn`
- `pypdf`
- `sentence-transformers`

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python main.py
```

## Flujo de uso

1. Introducir la asignatura de origen mediante una URL de guia docente de Uniovi.
2. Elegir cuantas asignaturas destino se quieren comparar.
3. Para cada destino, seleccionar uno de estos modos:
   - URL de guia docente
   - texto manual pegado por consola
   - PDF local
4. Revisar la salida por consola y los ficheros generados en `resultados/`.

## Comparacion semantica

La version actual reutiliza el pipeline documental de la V01, pero sustituye la comparacion lexica principal por una comparacion semantica de contenidos.

El proceso general es:

1. limpieza basica del texto
2. segmentacion en fragmentos manejables
3. generacion de `embeddings` multilingues
4. calculo de similitud coseno entre fragmentos
5. agregacion bidireccional mediante una media recortada inferior
6. interpretacion final del porcentaje y generacion del ranking

Umbrales interpretativos actuales:

- `>= 62%`: afinidad alta
- `>= 47%` y `< 62%`: afinidad media
- `< 47%`: afinidad baja

## Estrategias de entrada y scraping

La arquitectura distingue entre:

- una estrategia especifica para la asignatura de origen en Uniovi: `uniovi_ajax_html`
- estrategias tecnicas generales para destinos segun el tipo de fuente

Entre las estrategias de destino actualmente soportadas se encuentran:

- `generic_html`
- `snapshot_api_html`
- `embedded_base64_pdf`
- `remote_pdf`
- procesamiento de PDF local suministrado por el usuario

## Salidas generadas

Cada ejecucion puede generar, segun el caso:

- `resultados/logs_pipeline.txt`
- `resultados/resultados_comparacion.json`
- `resultados/resultados_comparacion.csv`

La salida incluye, entre otros, estos campos:

- modo de entrada
- referencia de origen y destino
- estrategia de scraping utilizada
- similitud semantica de contenidos
- afinidad interpretada
- compatibilidad ECTS
- fragmentos mas proximos para explicabilidad
- posicion en ranking cuando hay varios destinos

## Validacion y trazabilidad

El repositorio conserva:

- registros tecnicos en `docs/dev_logs/`
- resultados de validacion en `resultados/`
- materiales utilizados en la memoria del TFG

Las ramas historicas principales son:

- `version_01`: comparativa lexica y pipeline documental base
- `version_02`: evolucion semantica del comparador
- `master`: estado integrado mas reciente del proyecto

## Limitaciones actuales

- la asignatura de origen debe pertenecer a Uniovi
- la calidad del resultado depende de la calidad de extraccion del apartado de contenidos
- no todos los portales universitarios publican sus guias con la misma estructura
- la herramienta apoya la revision academica, pero no sustituye la decision final del profesorado responsable

## Como contribuir

El proyecto nace como desarrollo academico de TFG, pero puede seguir ampliandose. Si se retoma su evolucion, es recomendable:

1. trabajar sobre ramas especificas
2. documentar los cambios tecnicos en `docs/dev_logs/`
3. repetir las pruebas manuales y de validacion cuando cambie el comportamiento del pipeline
4. mantener actualizados `README.md`, resultados y memoria cuando proceda

## Licencia y contacto

Actualmente el repositorio no incorpora un fichero `LICENSE` especifico. Si se desea abrir el proyecto a reutilizacion externa de forma formal, el siguiente paso recomendable es definir una licencia explicita acorde con el uso que se quiera permitir.

Como canal de referencia, el repositorio remoto asociado es:

- [github.com/eliasdb7/TFG](https://github.com/eliasdb7/TFG)

## Contexto academico

Este repositorio debe entenderse como soporte tecnico y documental del TFG. La herramienta implementada sirve para apoyar el analisis preliminar de afinidad entre asignaturas, pero la decision final sobre una posible convalidacion o reconocimiento academico sigue correspondiendo al profesorado o a la instancia academica competente.
