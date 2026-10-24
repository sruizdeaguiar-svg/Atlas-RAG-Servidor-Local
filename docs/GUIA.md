# Guía de uso y administración de Atlas

[English](GUIDE.en.md) · [README](../README.md) · [Estructura](ESTRUCTURA.md) · [Instalación iOS](../ios/INSTALL.md)

## Elegir la carpeta de datos

Usa Configuración inicial para elegir una carpeta con espacio suficiente. Atlas propone unidades externas cuando están disponibles. Esa carpeta guarda base de datos, índice documental, análisis, copias, papelera y registros. Los modelos permanecen en las carpetas de su motor. Un pequeño almacén privado de credenciales permanece en la cuenta del usuario del Mac.

El indicador de disco corresponde a la unidad de datos. La RAM disponible es otra métrica, del sistema completo. El RSS de Atlas incluye descendientes y puede contar páginas compartidas; no equivale a memoria física exclusiva. Cambiar la carpeta abre otro espacio, sin migrar el anterior. Conserva la carpeta original hasta verificar tus copias.

## Añadir e indexar una colección

1. En Colecciones, pulsa Añadir carpeta.
2. Usa el navegador: en Mac puede abrir el selector nativo; en iPad recorre carpetas del Mac, no del iPad.
3. La selección rellena la ruta y propone el nombre de la carpeta. Un nombre personalizado se conserva.
4. Elige motor y modelo de embeddings. Apple funciona localmente; los motores compatibles ofrecen sus modelos de embeddings instalados en un catálogo separado.
5. Guarda y pulsa Indexar. Consulta progreso y errores en Actividad.

Solo los administradores pueden explorar carpetas. Los datos internos y credenciales quedan excluidos. Se omiten enlaces simbólicos, archivos ocultos y metadatos AppleDouble. Se admiten PDF con texto u OCR, XLSX, CSV, TSV, DOCX y texto; convierte los XLS binarios antiguos a XLSX.

El límite por archivo es 40 MiB y por PDF, 500 páginas. Otros límites del extractor pueden rechazar documentos grandes o con estructuras inusuales; consulta el error de indexación. La indexación incremental calcula hashes y reemplaza cada documento atómicamente. Conserva los documentos indexados sin cambios y el trabajo completado al cancelar. Si falta la unidad, informa del error y mantiene el índice.

Cambiar el perfil de embeddings invalida el índice de esa colección y exige reconstruirlo. La búsqueda semántica compara solo perfiles y dimensiones coincidentes. Si cambia un endpoint externo manteniendo el nombre del modelo, reconstruye expresamente sus colecciones. Los embeddings de OpenAI están deshabilitados: la indexación permanece local.

## Buscar y preguntar a la biblioteca

Selecciona colecciones o deja la selección vacía para consultar todas las autorizadas. Elige búsqueda textual, semántica o híbrida. Los resultados semánticos dependen del modelo y de su cobertura lingüística; los perfiles Apple por idioma no garantizan equivalencia entre idiomas. La búsqueda vectorial recorre los vectores y está orientada a bibliotecas locales moderadas.

Selecciona motor y modelo antes de preguntar. Las referencias abren la previsualización o descarga de la fuente indexada. Reindexa los archivos modificados. Las conversaciones pertenecen al usuario y dejan de mostrarse si se revoca el acceso a sus fuentes. Revisa las respuestas generadas y sus referencias.

## Gestionar motores locales

Los administradores pueden activar la gestión automática en Modelos e IA. Configura ejecutables y carpetas de modelos y elige motor y modelo instalado. Abrir una pantalla no carga modelos. vLLM necesita un modelo antes de iniciar su API. También existe activación explícita de la selección actual.

La gestión automática detiene el motor anterior antes de cargar otro. Cambiar de modelo también libera el proceso anterior. La parada de LM Studio descarga modelos, detiene su API y cierra la aplicación. Las API gestionadas usan loopback, puertos 18880–18883. Las conexiones externas mantienen su propio ciclo salvo parada externa confirmada por un administrador.

El contexto afecta a la memoria al cargar un modelo gestionado. Temperatura, Top-P y máximo de salida se aplican por petición. Atlas estima la memoria incluyendo todos los pesos MoE, contexto y buffers. La estimación no bloquea la carga por defecto. Puedes activar el bloqueo opcional en Modelos e IA. Con él desactivado, macOS y el motor gestionan memoria y swap; los errores propios del motor siguen mostrándose.

Parar todos los motores de Atlas libera procesos gestionados sin borrar pesos. Parar motores externos detectados es una acción separada, con confirmación, que puede interrumpir consultas de otras aplicaciones.

## Conectar OpenAI

Configura tu propia credencial API o usa OAuth cuando esté disponible para tu cuenta. Completa la autorización en el Mac. Consulta el catálogo y selecciona un nivel de razonamiento compatible. La disponibilidad depende de tu cuenta y conexión. Atlas pide consentimiento antes de enviar pregunta o contexto. No incluyas credenciales en documentos, capturas, informes ni repositorio.

## Analizar datos con R

1. Elige un CSV, TSV o XLSX y su hoja, cuando corresponda.
2. Revisa columnas, tipos, ausentes y tamaño.
3. Describe el análisis para preparar un plan con IA o elige un método compatible manualmente.
4. Revisa variables, supuestos y código R antes de ejecutar.
5. Ejecuta, revisa resultados y gráficos y solicita interpretación con IA si la necesitas.
6. Exporta el ZIP con código, copia CSV, hash y esquema de origen, resultados, gráficos y `sessionInfo()`.

Se admiten descriptivos, correlación de Pearson, regresión lineal, Welch de dos grupos, Wilcoxon, ANOVA y chi cuadrado. La IA propone un plan estructurado validado; no ejecuta R arbitrario ni instala paquetes pedidos por documentos. El método y su interpretación requieren revisión humana; correlación no demuestra causalidad.

R trabaja sobre una copia, bajo sandbox obligatorio de macOS, sin red ni acceso a archivos ajenos. CPU, tiempo, memoria, tamaño de salida y concurrencia están limitados. Si falla el sandbox, no se ejecuta.

## Usuarios, archivos y copias

El primer administrador crea usuarios y asigna acceso a colecciones. Lectores y editores comienzan sin permisos. Para indexar, editar o ejecutar R, un editor necesita permiso explícito de edición. Los lectores solo consultan y descargan documentos autorizados. Desactivar una cuenta o cambiar su contraseña invalida sesiones.

La edición de texto conserva copia y comprueba conflictos. La papelera guarda archivos y metadatos de restauración en la carpeta de datos; la recuperación es manual en esta versión. Mantén copias regulares y protege por separado las exportaciones. Los ZIP y documentos descargados ya no están bajo el control de permisos del servidor.

## iPhone/iPad y resolución de problemas

Activa HTTPS de red local en el Mac, empareja con el enlace o QR vigente e inicia sesión en Atlas. La app verifica la huella del certificado y solicita solo acceso a red local. El navegador de carpetas y los cambios de motor se ejecutan en el Mac con los mismos permisos que en escritorio.

Si falla la conexión, comprueba servidor activo, red local accesible, URL vigente y permiso de red local en iOS. Verifica en el Mac cualquier cambio de huella antes de emparejar de nuevo. No desactives la verificación ni publiques el servicio mediante un puerto del router.

Si falla un motor, revisa estado, registros, ejecutable, carpetas de modelos y memoria. Un modelo instalado puede ser incompatible con el motor. En errores de indexación, revisa formato, tamaño y límites. Las pruebas de desarrollo deben usar documentos ficticios y estado aislado; no ejecutes integración destructiva contra tu biblioteca.
