# Guion audiovisual — CityTrips NYC

**Idioma:** español  
**Formato:** horizontal 16:9 para YouTube  
**Duración del render:** 3:20.9 (máximo de entrega: 4:59)  
**Audiencia:** estudiantes y equipos que quieren construir una solución pública de ingeniería de datos.  
**Título propuesto:** *De 123 millones de viajes a un dashboard reproducible | Python + dbt + DuckDB*

## Guion de locución y escenas

| Tiempo | Visual | Locución |
| --- | --- | --- |
| 0:00–0:17 | Abrir con el dashboard real. Contador 123.5 M, mapa y línea temporal. | ¿Cómo pasamos de más de ciento veintitrés millones de viajes a una página que cualquiera pueda explorar? En este recorrido te enseño CityTrips NYC: datos públicos, transformación reproducible y un dashboard que se actualiza solo. |
| 0:17–0:41 | Diagrama que conecta TLC, ingesta, dbt, DuckDB, JSON y Pages. | La fuente son los registros mensuales de taxis amarillos de la Taxi and Limousine Commission de Nueva York. Construimos un pipeline batch con Python, dbt y DuckDB. GitHub Actions valida cada paso y publica los resultados en GitHub Pages, sin depender de AWS ni de un servidor que tengamos que mantener encendido. |
| 0:41–1:07 | Vista de archivos Parquet, mes como llave, checksum animado. Mostrar manifiesto. | La ingesta descubre los meses disponibles y descarga cada Parquet a un archivo temporal. Comprueba que se pueda leer, registra las filas y calcula un checksum SHA-256. Solo un archivo completo y verificado entra al caché. Si la TLC bloquea el catálogo automatizado, el flujo confirma los meses en su espejo público de archivos. |
| 1:07–1:28 | Iconos de schema antigua/nueva; `cbd_congestion_fee` aparece en nueva. | También hay evolución de esquema. Los archivos recientes incluyen el campo del cargo por congestión; los antiguos no. En vez de convertir lo que falta en cero, lo conservamos como desconocido. Así distinguimos “no reportado”, “reportado como cero” y “reportado con un importe”. |
| 1:28–1:54 | Staging → hechos → cuatro marts. Sobreimpresión de reconciliación de filas. | Después, dbt normaliza columnas y construye modelos mensuales, por hora, por zona y de calidad. DuckDB hace el trabajo analítico dentro del runner. Las pruebas verifican fechas, zonas, duración, distancia y una regla clave: filas de origen equivalen a filas aceptadas más filas rechazadas. Cada mes deja evidencia de qué se validó. |
| 1:54–2:21 | Pasar por las vistas overview, hourly heatmap, mapa TLC y quality. | El navegador no descarga los viajes individuales. Solo recibe agregados JSON y los límites GeoJSON de las zonas. En el tablero podemos filtrar por año, mes y distrito; comparar demanda promedio por día calendario; explorar patrones por hora; y revisar dónde se concentran los orígenes. La serie cronológica se ordena explícitamente para que los meses no salten de lugar. |
| 2:21–2:39 | Marcar enero de 2025 en la línea, aparece texto “descriptivo ≠ causal”. | La línea también señala el inicio del cargo por congestión en enero de 2025. Es una referencia temporal, no una prueba de causa y efecto: la estacionalidad, el turismo y otras condiciones también pueden cambiar la demanda. |
| 2:39–3:01 | Captura Actions: CI verde, workflow mensual, despliegue Pages. | Cada cambio pasa por pruebas de Python, dbt y React. Una vez al mes, Actions reconstruye el conjunto, compila el sitio y publica la nueva versión. Si falla una validación, conserva la última publicación correcta. La ejecución se puede repetir desde Actions cuando hace falta. |
| 3:01–3:21 | Pantalla dividida con repo y demo; cierre con URLs en texto. | El resultado procesa treinta y tres meses de datos TLC y publica una página abierta para inspección. El repositorio contiene el código, las pruebas y la guía para reproducirlo. Explora la demo, revisa el manifiesto y adapta el pipeline a tu propio problema de datos. |

## Recursos de producción

- Capturar la demo pública en [CityTrips NYC](https://iovargasjeff.github.io/citytrips-nyc/) y el repositorio en [GitHub](https://github.com/iovargasjeff/citytrips-nyc).
- Mostrar datos verificados: corte sep-2026, 33 archivos mensuales y 123,471,721 filas de origen. Confirmar los valores actuales con `web/public/data/manifest.json` justo antes de exportar.
- No mostrar credenciales, nombres de integrantes que no hayan autorizado su aparición ni filas individuales de viajes.
- Incluir subtítulos en español, texto de pantalla de alto contraste y un cierre con ambos enlaces.
- Exportar MP4 1920×1080 a 30 fps. Medir la duración final con `ffprobe` y mantenerla en 4:59 o menos.
- Si se publica en YouTube, añadir título, descripción, créditos de datos a NYC TLC y enlace al código; seleccionar visibilidad pública.
