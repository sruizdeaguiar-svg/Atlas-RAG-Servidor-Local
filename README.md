# Atlas RAG Local

**Tus documentos, tus modelos y tus análisis, en tu Mac.**

Servidor RAG local con aplicación nativa para macOS y cliente universal para iPhone/iPad. Organiza carpetas independientes, indexa documentos, busca con referencias y realiza análisis reproducibles con R. Interfaz en español e inglés. Código bajo [Apache 2.0](LICENSE).

[Instalación macOS](#instalación-en-macos) · [iPhone/iPad](ios/INSTALL.md) · [Modelos y memoria](#motores-locales-y-memoria) · [Capturas](#pantallas)

![Colecciones de Atlas](docs/screenshots/colecciones.png)

## Funciones

- Colecciones independientes con navegador de carpetas del Mac y nombre automático, también desde el iPad.
- PDF con OCR, CSV, TSV, Excel, Word y texto; previsualización, descarga, edición de texto y papelera con copia.
- Búsqueda textual y semántica, embeddings locales de Apple, deduplicación y referencias al archivo original.
- llama.cpp, oMLX, vLLM y LM Studio: catálogo de modelos instalados, arranque, cambio exclusivo de modelo/motor y parada para liberar memoria.
- OpenAI mediante credencial propia u OAuth en cuentas elegibles, selector de modelos y nivel de razonamiento, con consentimiento por operación.
- R local: descriptivos, correlación, regresión, Welch, Wilcoxon, ANOVA y chi cuadrado; código revisable, resultados, gráfico y exportación ZIP.
- Usuarios administrador/editor/lector, permisos por colección y registro de actividad.
- Datos en una carpeta elegida, con prioridad para unidades externas; estadísticas de RAM y disco de la unidad de datos.
- Acceso privado por HTTPS desde iPhone/iPad, con emparejamiento y verificación del certificado del Mac.

## Instalación en macOS

### Instalador

Descarga el `.dmg` o `.pkg` de [Releases](https://github.com/sruizdeaguiar-svg/Atlas-RAG-Servidor-Local/releases). El DMG permite arrastrar **Atlas RAG** a Aplicaciones. El PKG instala la aplicación en `/Applications` mediante el instalador de macOS.

Esta compilación se ha verificado en **Apple Silicon con macOS 27**. El paquete usa firma de desarrollo y **no está notarizado** para distribución general. No se presenta como una versión de App Store ni se desactivan las protecciones de Gatekeeper. Para distribuir con confianza de Gatekeeper se necesita una firma Developer ID y notarización del responsable del proyecto; también puedes compilar desde el código.

1. Abre Atlas y completa **Configuración inicial**.
2. El asistente detecta unidades externas, propone la carpeta de datos, muestra espacio disponible y detecta R y los motores instalados. Puedes elegir otra carpeta con el navegador nativo.
3. Crea el primer administrador. La configuración inicial puede volver a abrirse desde **Servidor → Configuración inicial…**.
4. En Colecciones, elige una carpeta de documentos, guárdala y pulsa Indexar.
5. Para IA local, abre Modelos e IA y elige motor y modelo. Para OpenAI, conecta tu propia cuenta en el Mac.

R y los motores de IA se instalan aparte; no se incluyen pesos de modelos. Si falta R, instala la versión de Apple Silicon desde [R para macOS](https://mac.r-project.org/) o usa `brew install r` si ya dispones de Homebrew. El asistente detecta tanto R de Homebrew como R.framework.

Los datos no se alojan dentro del paquete `.app`. La unidad seleccionada contiene SQLite, índices, análisis, copias y registros. Las credenciales OAuth/API y la clave TLS se guardan en un almacén privado del usuario en el disco del sistema, separado de los documentos. Si falta la unidad externa elegida, Atlas avisa y evita crear otra base silenciosamente en el disco principal.

### Compilar desde el código

Necesitas Xcode/Command Line Tools, Python 3.14, [uv](https://docs.astral.sh/uv/) y R. Los scripts usan zsh y están preparados para Apple Silicon.

```sh
git clone https://github.com/sruizdeaguiar-svg/Atlas-RAG-Servidor-Local.git
cd Atlas-RAG-Servidor-Local
zsh scripts/install.sh
```

`install.sh` instala las dependencias Python, instala R con Homebrew si falta y Homebrew está disponible, y genera `~/Applications/Atlas RAG.app`. `scripts/build_app.sh` crea además el acceso del escritorio cuando no hay uno previo. No incluye ni descarga modelos de IA.

Para crear el instalador después de compilar:

```sh
zsh scripts/build_installer.sh
```

Los archivos y sus sumas SHA-256 se generan en `dist/`. Si no se proporciona identidad de firma, el proceso usa la identidad Apple Development disponible o firma ad hoc. La firma de distribución/notarización requiere configuración propia.

## iPhone y iPad

El directorio [`ios/`](ios/) contiene el proyecto Xcode, el código SwiftUI, los iconos, las instrucciones y un [IPA de dispositivo sin firmar](ios/releases/AtlasRAG-iOS-unsigned.ipa). La app requiere iOS/iPadOS 17 o posterior.

Para instalarla necesitas firmarla con tu propia cuenta de Apple mediante Xcode. El IPA sin firmar no puede instalarse directamente. No se publican perfiles, certificados privados ni identificadores de dispositivos del desarrollador. Sigue las [instrucciones de instalación y conexión](ios/INSTALL.md).

En el Mac, activa **Servidor → iPhone / iPad · Red local…**. Empareja el móvil con el enlace o QR, usa la misma red e inicia sesión en Atlas. La base de datos, R y los modelos permanecen en el Mac.

## Motores locales y memoria

La gestión automática está disponible para administradores. Detecta ejecutables y carpetas de modelos habituales; las carpetas pueden ajustarse en Modelos e IA. Abrir una pantalla no carga pesos. Elegir un motor inicia una instancia dedicada; vLLM necesita seleccionar primero un modelo. Elegir un modelo lo carga y conserva sus archivos en disco.

| Motor | Carga y contexto | Parada |
| --- | --- | --- |
| llama.cpp | GGUF instalado, contexto al arrancar | Termina el proceso y sus hijos |
| oMLX | Modelo local compatible, ajustes aislados | Descarga y termina el proceso |
| vLLM | Modelo compatible instalado, contexto y KV limitado | Termina el servidor y sus trabajadores |
| LM Studio | Catálogo de su CLI oficial y contexto de carga | Descarga el modelo, detiene la API y cierra también la aplicación |

Solo se mantiene un motor gestionado activo. Antes de cargar otro modelo o cambiar de servidor, Atlas termina el anterior. Temperatura, Top-P y máximo de salida se aplican por petición. Guardar un perfil gestionado permite recargar el contexto; los servidores externos conservan su propia configuración.

**Parar todos los motores de Atlas y liberar memoria** cierra los procesos gestionados. Para afectar a motores abiertos fuera de Atlas existe una acción separada que muestra la lista detectada y exige confirmación. Puede interrumpir otras consultas. No borra pesos ni vacía globalmente las cachés del sistema.

Los servicios propios escuchan en loopback, en los puertos 18880–18883. Atlas no toma control silenciosamente de una API externa de LM Studio ni de sus modelos activos. Comprueba una estimación de memoria antes de cargar; el contexto gestionado admite 512–32768 tokens. La compatibilidad depende de la arquitectura del modelo y de la versión instalada del motor.

### Embeddings por colección

En Añadir carpeta se eligen por separado el motor y el modelo de embeddings. Con la gestión automática activada, la elección se ejecuta en el Mac también desde el iPad: arranca el motor y carga el modelo, con indicación de carga, estado listo o error. Apple usa su modelo integrado según el idioma. El catálogo de embeddings está separado del de conversación.

Los modelos MoE requieren memoria para todos sus pesos, además del contexto y los buffers. La comprobación previa muestra los pesos, la estimación y la RAM disponible; no fuerza cargas ni detiene aplicaciones ajenas para hacerlas caber.

## Análisis y privacidad

La IA propone un plan y R calcula sobre una copia de los datos. El código, las variables y los resultados quedan disponibles para revisión humana. R se ejecuta con sandbox de macOS, sin red, con límites de tiempo, memoria y escritura. La adecuación del método y sus supuestos debe revisarla quien realiza el análisis.

Los documentos y embeddings se procesan localmente por defecto. Usar OpenAI puede enviar la pregunta y el contexto seleccionado; Atlas pide consentimiento para la operación. No se incluye ninguna credencial del desarrollador.

La aplicación móvil solicita red local, no contactos, fotos, micrófono, cámara ni localización. El QR puede leerse con la Cámara del sistema. La app comprueba la huella del certificado del Mac y no instala certificados raíz. Los permisos de usuarios y colecciones se comprueban en el servidor.

## Pantallas

Las capturas siguientes usan un espacio de pruebas con documentos ficticios.

### Colecciones

Biblioteca, estado de indexación, RAM de Atlas y espacio libre de la unidad de datos.

![Colecciones](docs/screenshots/colecciones.png)

### Buscar y conversar

Selección de colecciones, modo de búsqueda, proveedor, modelo y fuentes de los resultados.

![Búsqueda](docs/screenshots/busqueda.png)

### Análisis con R

Conjunto de datos, método estadístico, variables y preparación de un análisis reproducible.

![Análisis con R](docs/screenshots/analisis-r.png)

### Modelos e IA

Control de motores, parada, contexto, perfiles y conexiones locales/OpenAI.

![Modelos e IA](docs/screenshots/modelos.png)

### Usuarios y permisos

Roles y asignación de acceso a colecciones.

![Usuarios y permisos](docs/screenshots/usuarios.png)

### Actividad

Recursos del servidor, almacenamiento, trabajos y auditoría.

![Actividad](docs/screenshots/actividad.png)

## Comprobaciones

La aplicación se verificó con pruebas de seguridad, OAuth, perfiles, aislamiento de R, permisos y control de procesos; integración HTTP/HTTPS con documentos ficticios; respuestas reales de los cuatro motores con modelos pequeños; y navegación, creación de colección, indexación y búsqueda desde un iPad físico. La interfaz se revisó en seis pantallas y cinco tamaños.

Para ejecutar las pruebas unitarias:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q tests/test_*.py
```

Las pruebas de límites de R y procesos necesitan los permisos normales de macOS fuera de un sandbox de herramientas adicional. La integración usa estado y puertos aislados; consulta los scripts antes de ejecutarlos. No ejecutes pruebas sobre una biblioteca de producción.

## Estructura

[Árbol del proyecto y contenido del paquete sin datos](docs/ESTRUCTURA.md).

| Carpeta | Contenido |
| --- | --- |
| `server/` | API, usuarios, documentos, RAG, R, OAuth, red y motores |
| `web/` | Interfaz adaptable ES/EN |
| `native/` | Aplicación y ayudantes nativos de macOS |
| `ios/` | App universal, paquete sin firmar e instalación |
| `scripts/` | Instalación, compilación y verificaciones |
| `tests/` | Pruebas automatizadas |
| `docs/screenshots/` | Capturas públicas con datos ficticios |

Las bases de datos, credenciales, modelos, capturas privadas, perfiles de Apple y datos personales no forman parte del repositorio.

## Licencia

[Apache License 2.0](LICENSE). Copyright 2026 sruizdeaguiar-svg y colaboradores. Consulta [NOTICE](NOTICE). Los runtimes, dependencias y modelos de terceros conservan sus licencias; la licencia del proyecto no cambia esas condiciones.

![Vista de la aplicación Atlas RAG Local](docs/screenshots/colecciones.png)

### Actualización 1.1.2

Corregida la navegación con teclado físico en iPad: Tab avanza entre campos, botones y selectores; Mayús+Tab retrocede. Incluye la pantalla nativa de conexión y los formularios de la biblioteca. Verificado en un iPad físico y en los campos de acceso del navegador de escritorio.
