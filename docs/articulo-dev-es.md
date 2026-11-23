# De 123 millones de viajes a un tablero público: un pipeline de datos reproducible con Python, dbt y DuckDB

¿Cómo se convierte una colección de archivos Parquet de varios gigabytes en una historia que una persona pueda explorar en el navegador? Para responderlo construimos CityTrips NYC: una solución abierta que toma registros de taxis amarillos de la NYC Taxi and Limousine Commission (TLC), los transforma con dbt y DuckDB y publica un tablero estático en GitHub Pages.

La versión desplegada cubre 33 meses, de enero de 2024 a septiembre de 2026. Los archivos de origen suman 123,471,721 filas. El tablero presenta tendencias, actividad por hora y día, orígenes por zona TLC y controles de calidad. La idea técnica central es mantener una ruta de datos reproducible y publicar únicamente agregados, nunca las filas individuales del viaje.

**Código:** [github.com/iovargasjeff/citytrips-nyc](https://github.com/iovargasjeff/citytrips-nyc)  
**Demo:** [iovargasjeff.github.io/citytrips-nyc](https://iovargasjeff.github.io/citytrips-nyc/)

## El problema no era solo leer Parquet

La TLC publica archivos mensuales de viajes y un diccionario de zonas. Es un buen conjunto de datos para análisis urbano, pero una publicación de varios años plantea retos que una demo de una sola tabla oculta:

- El tamaño total es mucho mayor que el artefacto final que necesita un sitio estático.
- Los meses publicados cambian con el tiempo y la página del catálogo puede bloquear descargas automatizadas.
- El esquema evoluciona. En el dataset reciente aparece `cbd_congestion_fee`; los archivos anteriores no contienen esa columna.
- Los códigos de zona solo tienen sentido si se relacionan con un catálogo geográfico versionado.
- Un tablero necesita explicar qué parte del dato se aceptó, qué se descartó y qué métricas sencillamente no existían todavía.

Por eso separamos el flujo en ingesta, transformación, publicación y visualización. La automatización vuelve a construir una versión completa desde fuentes públicas y solo reemplaza el sitio si terminan correctamente sus validaciones.

## 1. Descubrir y fijar la procedencia de cada fuente

La ingesta consulta el catálogo oficial y obtiene la secuencia de archivos mensuales disponibles. Si el catálogo HTML responde con acceso denegado, el proceso comprueba los nombres mensuales contra el espejo público de CloudFront que enlaza la TLC. No intenta adivinar meses posteriores: exige una secuencia completa y termina con error si encuentra un hueco.

Cada descarga se escribe primero en un archivo temporal. Después se abre con el lector Parquet, se comprueban sus columnas y filas y se calcula SHA-256. Solo entonces se mueve al caché con su nombre final y se registra en un manifiesto: mes, URL de origen, número de filas, columnas, tamaño y checksum. Una interrupción no deja un archivo parcial presentado como válido.

La recarga también es idempotente. El workflow restaura una caché de GitHub Actions, pero no confía en ella ciegamente: contrasta metadatos HTTP y checksum con el archivo local antes de reutilizarlo. Si el origen cambió, descarga y verifica una nueva copia. Los registros originales no se guardan en Git ni se entregan al navegador.

## 2. Normalizar el cambio de esquema con dbt

El campo del cargo por congestión demuestra por qué “columna ausente” y “cero dólares” no significan lo mismo. En la capa staging, una columna que no existe en un mes se representa como `NULL`, con el mismo tipo decimal que usa la columna cuando está disponible. De esta manera, el modelo conserva la diferencia entre:

- no reportado por la versión del archivo;
- reportado con importe cero;
- reportado con un importe positivo.

dbt construye modelos de staging y hechos y luego cuatro marts de consumo: mensual, mes por distrito/día/hora, zona por mes y calidad mensual. DuckDB ejecuta las transformaciones de manera local en el runner; no hace falta aprovisionar un clúster ni mantener un servidor de base de datos para servir los gráficos.

Las pruebas comprueban claves de zona, meses válidos, rangos de duración y distancia y conciliación de filas. La regla de contabilidad principal es:

```text
filas del archivo de origen = filas aceptadas + filas rechazadas
```

Las pruebas no sustituyen el análisis. Por ejemplo, una duración de 23 horas puede ser técnicamente positiva y aun así poco creíble para un viaje de taxi. Por eso el pipeline conserva motivos de rechazo separados y el dashboard presenta el resumen mensual de calidad.

## 3. Publicar el resultado con una frontera pequeña

El pipeline exporta JSON agregado para las series y GeoJSON para las zonas. El navegador descarga esos archivos estáticos desde GitHub Pages. Esta frontera evita exponer las filas de cada viaje, elimina la necesidad de una API propia y permite que la aplicación siga funcionando como un sitio rápido y público.

La interfaz tiene tres vistas: panorama, zonas y calidad. En el panorama se compara el promedio de viajes por día calendario para no confundir meses de 28 y 31 días. La cuadrícula por hora agrupa por día de la semana y hora de recogida. La vista espacial usa límites de zona de TLC y mantiene la correspondencia entre el nombre geográfico y el identificador numérico del viaje.

La serie temporal se exporta ordenada por mes. Esto parece un detalle de implementación, pero el orden de filas de una consulta SQL no está garantizado sin `ORDER BY`; una línea que conectara meses en orden arbitrario contaría una historia falsa aunque cada punto tuviera el valor correcto. La selección del cliente vuelve a ordenar defensivamente antes de dibujar la tendencia.

La comparación cerca del inicio del cargo por congestión en enero de 2025 es descriptiva. No demostramos que una intervención haya causado una variación observada: estacionalidad, clima, turismo, cambios de oferta y otras condiciones también influyen.

## 4. Automatizar validación y despliegue

GitHub Actions ejecuta CI al proponer o integrar cambios. El workflow mensual, programado para el día 10, reconstruye datos, corre `dbt build`, ejecuta las pruebas de Python y JavaScript, compila la aplicación y publica el artefacto en Pages. También se puede iniciar manualmente desde la pestaña Actions.

Hay dos decisiones operativas importantes. Primero, el workflow no publica si falla una descarga, un test o el build. Segundo, el despliegue estático reemplaza una versión completa del sitio: una ejecución rota deja accesible el último resultado correcto, en vez de sustituirlo por una salida a medias. Los permisos del job de despliegue están limitados a Pages y a leer el repositorio.

El dataset consolidado se procesa dentro de Actions, pero el navegador recibe solamente los agregados. Eso mantiene bajo el tamaño del sitio público y hace que compartir la demo sea tan simple como abrir un enlace.

## Ejecutarlo localmente

Con Python 3.12, `uv` y Node.js instalados:

```bash
uv sync --locked --all-groups
uv run citytrips-refresh --start-year 2024 --output web/public/data
cd web
npm ci
npm run dev
```

Para validar los modelos localmente se puede ejecutar `uv run dbt build --project-dir dbt --profiles-dir dbt --target-path target` desde la raíz. `uv run pytest`, `uv run ruff check .`, `npm test`, `npm run lint` y `npm run build` cubren las capas de código y de presentación.

## Lo que funcionó y lo que falta vigilar

La fuente mensual permitió recomponer la serie sin subir más de cien millones de filas al repositorio. El manifiesto y el checksum hacen visible qué datos generaron la publicación, y dbt ofrece una ubicación explícita para los cambios de esquema y reglas analíticas.

El mayor límite es la escala temporal del proceso: una recarga completa tarda más de lo que tardaría una consulta sobre una base analítica persistente, aunque la caché reduce las transferencias cuando los archivos no cambian. Si el equipo necesitara actualizaciones diarias, más fuentes o consultas exploratorias sobre filas individuales, convendría evaluar almacenamiento columnar persistente y procesamiento incremental. Para una publicación mensual reproducible, un pipeline batch con DuckDB mantiene menos piezas operativas.

Antes de interpretar los indicadores, revisa la fecha de corte, los meses publicados y la cobertura de cada columna. En particular, “sin dato” no es sinónimo de cero y una correlación temporal no demuestra causalidad.

## Conclusión

CityTrips NYC conecta procedencia, modelos analíticos, controles de calidad y visualización en una ruta que se puede volver a ejecutar. La lección más útil del proyecto es concreta: un agregado atractivo solo merece confianza cuando el equipo puede explicar qué archivos lo generaron, cómo cambió su esquema y qué registros quedaron fuera. El manifiesto, las pruebas de dbt y el despliegue condicionado hacen visible esa evidencia junto con el dashboard.

El repositorio deja una base reproducible para adaptar el mismo patrón a otra fuente mensual: detectar publicaciones, validar archivos, modelar con tests y servir una salida pequeña desde una página pública.

## Referencias

- [Catálogo y diccionarios de TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Pruebas de datos de dbt](https://docs.getdbt.com/docs/build/data-tests)
- [DuckDB: lectura de Parquet](https://duckdb.org/docs/stable/data/parquet/overview)
- [Despliegue de GitHub Pages con GitHub Actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Repositorio y guía para reproducir el pipeline](https://github.com/iovargasjeff/citytrips-nyc)
