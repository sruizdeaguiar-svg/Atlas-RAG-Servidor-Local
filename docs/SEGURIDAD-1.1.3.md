# Revisión de seguridad — 1.1.3

[English](SECURITY-1.1.3.en.md) · [Política de seguridad](../SECURITY.md) · [README](../README.md)

Fecha: 24 de octubre de 2026. Este informe describe problemas confirmados y medidas implementadas. No asigna CVE ni constituye una certificación independiente de pentesting. Consulta en la publicación el estado final de instalación y pruebas de dispositivos.

## Problemas y correcciones

| Problema | Impacto y alcance | Corrección |
| --- | --- | --- |
| Límite de peticiones basado en Content-Length | Una petición por fragmentos podía superar el límite antes de validar JSON y consumir memoria. En una prueba aislada, un acceso de 43 MiB devolvió validación 422 en lugar de rechazo 413. No se demostró elusión de autenticación. | Middleware ASGI cuenta los bytes reales antes del análisis: 256 KiB para mutaciones normales y 42 MiB para subidas, también con fragmentos o longitud declarada incorrecta. |
| Extracción documental sin aislamiento de proceso ni suficientes límites de expansión | ZIP de Office, tablas enormes o errores del extractor podían agotar recursos. No se demostró ejecución remota de código. | Extracción en proceso separado con sandbox de macOS, sin red, lectura limitada al archivo/runtime y escritura solo temporal. Límites de CPU, tiempo, RSS del grupo y salida; límites de entradas, expansión, hojas y celdas. XML usa defusedxml. |
| Recursos de autenticación insuficientemente acotados | Muchos usuarios fallidos distintos podían ampliar la caché; hashes simultáneos podían agotar CPU. | Mapas acotados con caducidad, límites por usuario/IP y máximo de dos verificaciones de contraseña simultáneas. |
| Avisos conocidos en dependencias de motores Python externos | Las distribuciones inspeccionadas de oMLX y vLLM incluían versiones señaladas por las fuentes de vulnerabilidades. Su alcance depende del paquete y plataforma; un aviso no demuestra explotación mediante Atlas. | Los arranques gestionados usan dependencias aisladas: certifi 2026.10.23, filelock 4.2.1, setuptools 84.1.0, opentelemetry-api 1.45.1 y Pillow 13.0.0. Se conservan las instalaciones originales y se rechaza el arranque si faltan las dependencias requeridas. |
| Entorno heredado demasiado amplio por los motores | Un motor podía heredar credenciales ajenas presentes en el entorno del padre. No se observó filtración. | Se construye un entorno restringido en lugar de copiar variables arbitrarias. |

Las dependencias aisladas se reproducen con `scripts/prepare_engine_security.py` durante la compilación y se incluyen en el runtime de macOS. El ZIP de fuentes incluye el script, no las dependencias generadas. Es necesario verificar compatibilidad cuando se actualice el motor del fabricante.

**No se modifican las instalaciones originales de oMLX/vLLM.** Si se abren fuera de Atlas pueden usar sus versiones originales. Actualiza también las aplicaciones del fabricante. El escáner Python no cubre todo el código nativo de LM Studio, llama.cpp, R, frameworks de Apple ni sistema operativo.

## Correcciones funcionales de control de motores

Los selectores comparten activación explícita y operaciones serializadas. Un proveedor parado ya no se presenta silenciosamente como seleccionado. Se detiene la API restaurada por LM Studio antes de arrancar el listener dedicado; la parada cierra aplicación y ayudantes. La consulta de estado tolera salidas simultáneas y no confunde zombis con motores activos.

Son correcciones de fiabilidad. No se presentan como escalada de privilegios ni filtración confirmadas.

## Verificación y límites

- Pruebas de regresión de bytes reales, expansión Office, rechazo de entidades XML, lectura CSV/XLSX/DOCX bajo sandbox y controles existentes de permisos, OAuth, R y procesos.
- Ciclo real HTTPS con embeddings y respuestas de llama.cpp, oMLX, vLLM y LM Studio usando modelos pequeños instalados. Finalizó con los cuatro puertos dedicados cerrados y ningún proceso de LM Studio.
- La auditoría previa de dependencias fijadas de Atlas no tuvo avisos conocidos. Los inventarios corregidos de oMLX y vLLM tampoco tuvieron avisos conocidos en esta revisión. El resultado depende del escáner y su fuente en esa fecha; no demuestra ausencia de vulnerabilidades.
- El análisis estático señaló SQL dinámico. La revisión encontró parámetros enlazados para valores e identificadores de colección; las columnas de actualización proceden de llamadas internas, no de nombres recibidos del usuario. No se confirmó inyección explotable en esos puntos.
- No se certifican todos los modelos, dependencias nativas, versiones iOS, servicios externos ni componentes del sistema. La revisión no sustituye actualizaciones, copias ni una evaluación independiente.

Se mantienen permisos por colección en servidor, tokens de sesión almacenados como hash, hash de contraseñas, validación de origen/Host, permisos privados de credenciales, consentimiento para OpenAI, sandbox obligatorio de R y verificación de huella TLS en iOS. No se desactiva ninguna protección del sistema, autenticación ni validación de certificados.
