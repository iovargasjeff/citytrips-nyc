Construir un gráfico a partir de un archivo grande suele ser la parte fácil. El trabajo de ingeniería aparece después: identificar cuál es la publicación más reciente, detectar un mes ausente, distinguir un campo que todavía no existía de un valor cero, explicar las filas descartadas y evitar que una ejecución incompleta reemplace una versión pública válida.

CityTrips NYC resuelve ese recorrido para los registros mensuales de taxis amarillos de la NYC Taxi and Limousine Commission (TLC). Un pipeline en Python descarga y verifica archivos Parquet; dbt y DuckDB normalizan y agregan los datos; GitHub Actions ejecuta controles y reconstruye el producto; una interfaz React publica únicamente JSON agregado y geometrías GeoJSON simplificadas en GitHub Pages.

El snapshot visible al escribir este análisis cubre 33 meses, de enero de 2024 a septiembre de 2026. Los archivos de origen suman 123,471,721 filas. De ellas, 122,490,358 superaron las reglas analíticas y 981,363 se clasificaron como rechazadas. El objetivo no es presentar un número grande como prueba de calidad: es poder reconstruirlo, explicar cada etapa y mostrar sus límites.

**Repositorio:** [github.com/iovargasjeff/citytrips-nyc](https://github.com/iovargasjeff/citytrips-nyc)

**Dashboard:** [iovargasjeff.github.io/citytrips-nyc](https://iovargasjeff.github.io/citytrips-nyc/)

**Fuente:** [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)

## La pregunta de diseño: ¿qué debe poder demostrar el pipeline?

La primera decisión fue definir el resultado antes de escoger herramientas. El tablero debía responder preguntas descriptivas sobre demanda por mes, horario y zona, pero una ejecución también debía dejar evidencia suficiente para contestar preguntas operativas:

1. ¿Qué archivos y meses produjeron el snapshot que se está viendo?
2. ¿Cómo sabemos que una descarga llegó completa y que el archivo sigue correspondiendo a la versión publicada por la fuente?
3. ¿Qué significa una fila aceptada o rechazada, y se reconcilian ambas cantidades con el total recibido?
4. ¿Qué hacemos cuando cambia el esquema, por ejemplo cuando un campo aparece en los años más recientes?
5. ¿Qué recibe el navegador y qué permanece fuera del producto público?
6. ¿Qué impide que una ejecución fallida reemplace el último dashboard correcto?

Estas preguntas llevan a una arquitectura batch, con un warehouse efímero de DuckDB dentro del runner y artefactos estáticos como salida. La elección es deliberada: la TLC publica por mes y el producto no promete consultas en tiempo real. Un sistema distribuido con broker, servicio de base de datos permanente y API añadiría disponibilidad y operación que esta cadencia no necesita.

## Arquitectura: separar el procesamiento pesado del sitio público

El flujo empieza con los Parquet mensuales y los archivos de catálogo geográfico de TLC. Python descubre la ventana de datos, descarga y verifica fuentes. Después ejecuta `dbt build` contra DuckDB, que genera modelos analíticos y corre sus pruebas. La aplicación exporta los marts como JSON, simplifica los límites de zonas a GeoJSON y construye una web estática. GitHub Pages sirve esa web; el runner conserva los archivos de origen en su espacio de trabajo y en la caché de Actions, pero esos Parquet no se incluyen en el sitio.

![Diagrama de arquitectura de extremo a extremo de CityTrips NYC](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/srestyugln02rjakk1cv.png)

La frontera entre warehouse y frontend es importante. El navegador no consulta DuckDB, no descarga los viajes individuales y no necesita credenciales para acceder a una API. Recibe cinco productos acotados: `monthly.json`, `monthly_hour.json`, `zone_month.json`, `quality.json` y `taxi_zones.geojson`; el manifiesto público añade el corte temporal, el número de archivos y los datos de procedencia. Esta forma permite servir el dashboard desde un host estático y reduce la superficie operativa del producto.

También hace visible el compromiso elegido: el refresh reconstruye el conjunto completo de marts; el navegador ofrece una lectura rápida y descriptiva sobre agregados, no exploración arbitraria de filas. Si el uso futuro exigiera consultas ad hoc o una API transaccional, habría que cambiar esa frontera y su modelo de operación, no solo añadir un gráfico.

### ¿Por qué batch y no Kafka?

Kafka resuelve problemas de eventos: productores y consumidores desacoplados, flujos continuos, replay y latencia baja. En CityTrips NYC no hay una fuente de eventos por segundo ni varios consumidores independientes que necesiten reaccionar a cada viaje. La unidad natural de actualización es el archivo mensual. Incluir un broker aquí significaría operar tópicos, retención, consumidores y recuperación de offsets sin mejorar la frescura que ofrece la fuente. Si mañana la TLC entregara eventos continuos o hubiera varios productos con SLA de segundos, la evaluación cambiaría.

### ¿Por qué GitHub Actions y no Airflow o Luigi?

GitHub Actions ya ofrece el disparador mensual, una ejecución manual, caché y la integración de CI con el mismo repositorio que guarda el código. Para un pipeline pequeño, lineal y de un solo dueño, esa simplicidad reduce piezas que hay que vigilar. Airflow tendría sentido si el grafo incorporara dependencias con otros sistemas, backfills coordinados, calendarios de negocio, SLAs y observabilidad centralizada entre equipos. Luigi puede ser apropiado cuando se quiere expresar tareas Python y dependencias como un grafo ligero. Ninguno es “mejor” de forma universal: aquí el costo de incorporar un scheduler dedicado superaría el valor de sus capacidades adicionales.

No usamos servicios de AWS. La publicación pública utiliza GitHub Actions y GitHub Pages; el análisis local usa DuckDB. Para otro equipo, el criterio transferible no es copiar los nombres, sino elegir la menor plataforma que satisfaga frecuencia, recuperación, observabilidad y responsabilidades reales.

## Ingesta: descargar no es lo mismo que aceptar

La capa de ingesta está escrita en Python porque aquí importan tanto las solicitudes HTTP y el sistema de archivos como el análisis posterior. `parse_trip_sources` extrae del catálogo los enlaces cuyos nombres cumplen el patrón mensual esperado. Si la página no está disponible o no entrega enlaces, el fallback sondea los archivos públicos de CloudFront que enlaza TLC y retrocede desde el mes actual para localizar el último publicado. Luego comprueba la secuencia completa desde 2024: un hueco entre meses es un error explícito, no un intervalo silencioso del gráfico.

Cada Parquet se transmite a un archivo temporal `.part`, en bloques de 1 MiB, con tres intentos máximos. Antes de promoverlo al nombre final, Arrow lee los metadatos del Parquet. Si el proceso se interrumpe, se borra el temporal. Cuando la validación pasa, `os.replace` efectúa el cambio de nombre atómico. El manifiesto también se escribe primero a un temporal y después se reemplaza; así no queda un JSON truncado presentado como evidencia válida.

![Etapas de ingesta, verificación y promoción atómica](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/808xtpfpjk0r4knze27z.png)

El caché de Actions reduce descargas, pero no se acepta por su mera existencia. Para reutilizar una copia se comprueba que coincida la URL y que los validadores remotos disponibles —ETag, `Last-Modified` o tamaño— coincidan con el manifiesto previo. Además, se vuelve a calcular el SHA-256 local y se compara con el checksum registrado. Si no hay validadores comparables, cambió la fuente, falta el archivo o falla la suma de comprobación, se descarga de nuevo. Esta regla es más costosa que “si existe, úsalo”, pero evita convertir una caché antigua o dañada en una fuente de verdad.

El manifiesto de entrada registra mes, URL, ruta del archivo, número de filas, nombres de columnas, bytes, checksum y metadatos HTTP. También conserva los hashes del lookup y del ZIP de límites geográficos. Eso permite reconstruir qué combinación de datos produjo un snapshot y separar un cambio del dato de un cambio del código.

Hay una limitación importante: los checksums prueban identidad de bytes, no veracidad de cada observación. TLC indica que los registros son suministrados por proveedores tecnológicos y que la agencia no garantiza su exactitud o integridad completa. El pipeline puede detectar archivos corruptos, cambios de fuente y algunas incoherencias internas; no convierte por sí solo los datos reportados en una medición perfecta de todos los viajes de la ciudad.

## Evolución de esquema: “no reportado” no es “cero”

Los archivos recientes contienen `cbd_congestion_fee`, el cargo asociado con el programa de congestión; los registros de 2024 no traen esa columna. Si al leer un archivo antiguo el warehouse sustituyera la columna ausente por `0`, el tablero afirmaría que hubo una observación monetaria igual a cero. Esa afirmación no se desprende de la fuente. El staging tipa el campo como decimal y conserva `NULL` cuando la columna no existe.

La diferencia repercute en las métricas. El estado de cobertura puede ser `not_available`, `reported` o `partially_reported`. El primero describe disponibilidad del campo, no ausencia de cargos. El segundo requiere valores informados; el tercero advierte que solo una parte de las filas proporciona el dato. De ese modo, la interfaz puede mostrar tanto el valor agregado como el contexto que hace interpretable su cobertura.

Este patrón es aplicable a muchos dominios: un dato que empezó a recopilarse a mitad de una serie, un sensor que estuvo desconectado, una categoría añadida al catálogo o una columna opcional. Antes de rellenar un nulo, conviene preguntar si existe evidencia de que el valor era realmente cero. Si no la hay, la ausencia debe mantenerse visible o modelarse con una dimensión explícita de disponibilidad.

## dbt y DuckDB: hacer explícitos el grano y las reglas

DuckDB lee y transforma Parquet dentro del runner; dbt organiza las relaciones, documenta dependencias y ejecuta tests. El proyecto tiene capas con responsabilidades distintas:

- **Staging:** convierte nombres de columnas, tipos y timestamps a una forma estable; incorpora `source_month` y el lookup de zonas.
- **Intermediate:** enriquece cada viaje con borough y nombre de zona, calcula duración y asigna un motivo de rechazo o `NULL` cuando pasa las reglas.
- **Marts:** agregan los hechos al grano que necesita cada vista: mes, mes/distrito/día/hora, mes/zona y mes/calidad.

![Linaje de modelos dbt, granos y contratos de calidad](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/507sduze114y7757fqjf.png)

El grano se documenta porque una tabla sin una clave clara puede duplicar cifras durante una unión. `mart_zone_month`, por ejemplo, debe tener una sola fila por combinación de mes y `location_id`; `mart_monthly`, una fila por mes. Los tests comprueban unicidad y valores no nulos donde corresponde. En `mart_month_hour`, el nivel de detalle incluye mes, borough, día de semana y hora, por lo que esperar una sola fila por mes sería una prueba incorrecta.

Las reglas de calidad son concretas y rastreables. El modelo intermedio clasifica timestamps ausentes, un mes de recogida distinto al mes del archivo, hora de bajada anterior o igual a la recogida, duración superior a 24 horas, distancia ausente o negativa y zonas de recogida o bajada desconocidas. Se conserva `rejection_reason` para poder explicar la exclusión. Estas reglas representan un contrato analítico del proyecto, no una sentencia sobre fraude ni una garantía universal de que toda fila que pasa sea correcta.

La identidad de fila principal se expresa como una conciliación por mes:

```text
filas de origen = filas aceptadas + filas rechazadas
```

La prueba SQL singular de dbt busca precisamente meses donde falle esa igualdad. Otras pruebas comprueban `not_null`, `unique`, `accepted_values` y consistencia referencial. En vez de medir la calidad con un puntaje opaco, el usuario puede ver conteos, tasas y motivos que se relacionan con reglas en el código. Los tests de dbt se expresan como consultas que deben devolver cero filas para pasar; cuando hay fallas, es posible inspeccionar qué registros contradicen la aserción.

## Qué muestran las cifras de calidad

En el snapshot completo, 122,490,358 de 123,471,721 filas quedaron aceptadas y 981,363 se pusieron en cuarentena. La tasa calculada de rechazo es aproximadamente 0.8 %. No es correcto resumirlo como “99.2 % de datos limpios”: “aceptada” significa que la fila superó estas comprobaciones y quedó en el conjunto analítico, no que todos sus campos hayan sido confirmados contra una verdad externa.

Para septiembre de 2026, la tabla registra 3,876,044 filas de origen, 3,827,802 aceptadas y 48,242 rechazadas. La igualdad se sostiene y hace que el resumen mensual sea auditable. La tasa mensual puede cambiar por comportamiento del origen, por el esquema o por el umbral de una regla; revisar la tendencia es más útil que mirar un solo porcentaje. Si se modifica el contrato, conviene anotar la versión de la regla y evaluar el efecto de forma retrospectiva.

![Vista de calidad con filas de origen, aceptadas, rechazadas y manifiesto](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/9pxusmtyvcivin91wncl.jpeg)

La captura complementa, pero no reemplaza, el test. La prueba impide publicar cuando no se reconcilian los conteos; la pantalla ayuda a una persona a revisar qué ocurrió por mes y cuándo se construyó el snapshot. Son controles diferentes: uno automático y binario, otro exploratorio y contextual.

## Artefactos estáticos y decisiones de visualización

El pipeline exporta los marts ordenados por claves cronológicas y dimensiones antes de serializarlos. SQL no garantiza un orden de resultados si no se solicita explícitamente. Ordenar `mart_monthly` por `month`, por ejemplo, evita conectar en una línea enero de 2026 con abril de 2024 por el orden incidental de ejecución.

La aplicación recibe los agregados, filtra por año, mes y borough y presenta tres vistas. El panorama combina indicadores de viajes registrados, promedio diario, duración típica y cobertura del cargo; muestra una tendencia por día calendario y una matriz de hora por día de la semana. La tasa diaria permite comparar meses de distinta duración sin confundir 28 y 31 días. La marca de enero de 2025 ubica el inicio del cargo por congestión como referencia temporal, no como estimación de impacto.

![Vista general del dashboard con filtros, KPIs, tendencia y patrón horario](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/b9ywafm8yakv99j5990l.png)

La vista espacial relaciona `LocationID` con el catálogo y los límites de zonas TLC. El GeoJSON se lleva a EPSG:4326 y simplifica geometrías antes de publicarse; la reducción preserva la topología para evitar que un borde simplificado se autointersecte. La pantalla permite comparar volumen agregado por zona y un ranking de los principales orígenes. El mapa describe dónde se registran recogidas, no la residencia de pasajeros ni la demanda total de movilidad de la ciudad.

![Mapa de zonas TLC y ranking de orígenes con mayor volumen](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/n530jgra6usu8wvhzakn.png)

La tercera vista presenta calidad y manifiesto. Hacer visible el origen y el corte temporal evita que un número aislado parezca “actual” sin indicar hasta qué mes llega. En particular, la interfaz explica que la ausencia del campo de cargo en 2024 significa “sin dato reportado”, mientras que un cero es un valor reportado. El detalle de la página y los archivos distribuidos coinciden con las fuentes que el pipeline produjo.

## CI/CD: separar integración de refresh de datos

El repositorio usa dos rutas. CI se ejecuta en cambios de `main` y pull requests: configura Python 3.12, sincroniza las dependencias fijadas en `uv.lock`, corre Ruff y Pytest; en otro job instala Node.js 22 y ejecuta lint, tests y build del dashboard. Así los cambios al frontend y al pipeline se validan con la misma fuente de verdad: el código versionado.

El workflow de publicación puede dispararse manualmente y también se programa para el día 10 de cada mes a las 10:15, hora de Lima. Recupera la caché de fuentes, sincroniza dependencias, ejecuta `citytrips-refresh`, instala dependencias web, vuelve a ejecutar lint/tests/build y empaqueta `web/dist` como artefacto de Pages. El job `deploy` depende del build; si cualquier etapa falla, no recibe un artefacto nuevo para publicar. Sus permisos son acotados a `pages: write` e `id-token: write`, mientras que los pasos de construcción solo necesitan lectura del repo.

![Separación entre CI y publicación condicionada a validaciones](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/tt7rla9cmdvg9kg49lxk.png)

![Ejecución de GitHub Actions con los pasos de build y deploy en verde](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/u7dlia7nrcew70albsce.png)

La captura corresponde a una ejecución manual completada: el job de build y el despliegue finalizaron con éxito; el resumen del frontend muestra dos archivos de test y siete resultados aprobados. Es evidencia de una ejecución, no una promesa de que todas las futuras terminarán igual. La señal operativa más importante es que la versión anterior permanece publicada si el siguiente intento falla antes de desplegar.

El mismo `citytrips-refresh` ejecuta ingesta, build de dbt y exportación de datos, lo que reduce diferencias entre desarrollo local y publicación. Aun así, una ejecución local completa descarga el historial desde 2024 si no existe caché, por lo que requiere red, espacio y tiempo. Los ejemplos de tests de la web usan el sample ilustrativo del repositorio; los datos publicados son regenerados por el workflow y el manifiesto los distingue.

## Pensar el costo como una curva, no como un precio aislado

Esta solución evita pagar y operar una base de datos, un broker o un scheduler que permanezca activo entre refreshes. Eso no significa que procesar 123 millones de filas sea gratuito: existe consumo de runner, transferencia de archivos, almacenamiento de caché y tiempo de espera si una ejecución completa debe repetirse. Como no se publica una medición de consumo por ejecución, no atribuyo un precio ni una mejora porcentual ficticia.

Las métricas operativas que convendría seguir son duración de descarga y transformación, bytes transferidos cuando hay caché fría, tamaño de los marts, memoria pico del runner, meses procesados y número de reintentos. Si la duración empezara a acercarse al límite del runner o la ventana mensual dejara de ser suficiente, primero mediríamos qué etapa domina y si una mejora de lectura/particionado resuelve el problema. Solo después compararíamos procesamiento incremental o almacenamiento persistente. La pregunta no es “¿podemos añadir otra herramienta?”, sino qué punto de la curva de costo o de frescura obliga a hacerlo.

La salida estática también es una decisión de costo y resiliencia: las consultas de lectura no arrancan un backend por cada usuario, pero la interfaz queda limitada a las agregaciones que el pipeline preparó. Un nuevo gráfico puede exigir cambios al mart y una publicación completa. Si los usuarios necesitaran combinar dimensiones no previstas, el costo de precomputar todas las combinaciones podría superar el de operar un servicio de consulta; esa es una señal concreta para revaluar el contrato del frontend.

## Reproducir el pipeline

Los requisitos son Python 3.12 o 3.13, `uv` y Node.js 22. Desde la raíz del repositorio:

```powershell
uv sync --locked --all-groups
uv run ruff check .
uv run pytest
```

Para reconstruir los datos públicos desde 2024 y regenerar los marts:

```powershell
uv run citytrips-refresh --start-year 2024 --output web/public/data
```

La primera ejecución descarga las fuentes TLC que cubren ese intervalo; las siguientes pueden reutilizar los archivos de `data/` si coinciden con los validadores remotos y sus checksums. Para revisar el frontend:

```powershell
Set-Location web
npm ci
npm run lint
npm test
npm run build
```

La aplicación se puede iniciar con `npm run dev`. El proyecto no requiere credenciales cloud para ejecutar estas tareas. GitHub Pages sí debe habilitarse como origen de despliegue “GitHub Actions” en la configuración del repositorio.

## Qué valida cada capa (y qué no)

| Capa | Garantía que intenta dar | Límite de esa garantía |
| --- | --- | --- |
| HTTP y SHA-256 | La copia está íntegra y puede atribuirse a una versión de fuente | No demuestra exactitud semántica del proveedor |
| Validación Parquet y ZIP | El archivo se puede leer y tiene estructura esperada | No detecta todos los errores dentro de cada campo |
| Pruebas dbt | El grano, valores esperados y conciliación se mantienen | No convierten los umbrales elegidos en verdad universal |
| CI | Los cambios de código pasan pruebas antes de integrarse | No prueba cada nueva publicación mensual automáticamente en todos los entornos posibles |
| Manifiesto | El corte y los archivos usados quedan descritos | No sustituye a un catálogo institucional con linaje y gobierno formal |
| Dashboard | Hace explorables los agregados y su cobertura | No ofrece filas de viaje ni permite inferencia causal |

Pensar las garantías de esta manera ayuda a evitar el lenguaje inflado de “dato confiable”. La confianza se construye por capas y cada una tiene un alcance específico. Un checksum detecta una diferencia de bytes; una prueba de reconciliación encuentra un total inconsistente; una revisión de negocio decide si la regla de rechazo refleja la pregunta analítica.

## Límites y siguiente evolución

El refresh es batch y de periodicidad mensual. La actualidad máxima está condicionada por el momento en que TLC publica archivos completos, no por la frecuencia del job. El proceso vuelve a construir marts sobre el conjunto disponible; la caché limita transferencias repetidas, pero no convierte el warehouse en un almacenamiento analítico persistente. A medida que crezca el histórico, convendría medir duración, uso de disco y memoria del runner, y plantear particiones incrementales solo si el beneficio supera la complejidad añadida.

El segundo límite es analítico. El dashboard sitúa el comienzo del programa de congestión en enero de 2025, pero una variación de viajes antes o después no identifica causalidad. Calendario, clima, turismo, cambios de oferta y composición de viajes pueden alterar la demanda. Una evaluación causal exigiría una pregunta más estrecha, un diseño de comparación apropiado, métricas predefinidas y análisis de sensibilidad; el dashboard actual no pretende hacer eso.

El tercer límite proviene de la fuente: el dataset registra viajes reportados y sus categorías, no cada dimensión de la movilidad urbana. Las tasas describen los registros disponibles y pasan por reglas de este proyecto. Antes de trasladar resultados a una decisión de política pública, hay que revisar documentación, cobertura temporal y advertencias de TLC.

Si el producto creciera, las mejoras más valiosas serían versionar formalmente los contratos de datos, mantener un historial de cambios de reglas, publicar métricas de duración/rechazo por ejecución y generar reportes de diferencias entre snapshots. Para alta frecuencia o varios productos consumidores, podríamos evaluar un scheduler especializado, almacenamiento persistente o streaming. Esas decisiones seguirían una necesidad medible; no se añaden por prestigio tecnológico.

## Cierre

CityTrips NYC es útil no porque use muchas herramientas, sino porque sus piezas dejan rastros verificables: archivos identificados, checksums, modelos con granos explícitos, tests que detectan conciliaciones rotas, artefactos pequeños y una publicación condicionada a que el build termine correctamente. El usuario puede explorar la serie, y el equipo puede explicar qué hay detrás de ella.

Ese patrón se puede adaptar a otras fuentes periódicas: automatizar descubrimiento, aceptar archivos solo después de validarlos, modelar cambios de esquema sin inventar datos, definir salidas al grano que necesita la interfaz y hacer que el despliegue dependa de pruebas. La herramienta concreta puede cambiar; las preguntas de procedencia, contrato, recuperación y comunicación de límites siguen siendo las mismas.

## Referencias

- [Datos de viajes TLC y notas sobre su procedencia](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [MTA: Central Business District Tolling Program](https://www.mta.info/document/165006)
- [dbt: data tests](https://docs.getdbt.com/docs/build/data-tests)
- [DuckDB: lectura y escritura de Parquet](https://duckdb.org/docs/stable/data/parquet/overview)
- [GitHub: workflows personalizados para Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub: despliegue automático de sitios](https://docs.github.com/en/get-started/start-your-journey/deploying-your-website-automatically)
- [Código, tests y archivos de automatización](https://github.com/iovargasjeff/citytrips-nyc)
