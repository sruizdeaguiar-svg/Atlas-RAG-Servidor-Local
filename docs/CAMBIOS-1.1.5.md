# Atlas RAG Local 1.1.5

- Corrige la detección de llama.cpp: se comparan los números de compilación de los motores detectados y se elige el más reciente. En el Mac de prueba, Atlas estaba usando la compilación 10815, que rechazaba la arquitectura Flint, en vez de la 11840 instalada. Las rutas configuradas explícitamente se conservan.
- Los fallos de arquitectura de llama muestran la arquitectura incompatible y una indicación para actualizar el motor o elegir un modelo compatible.
- Corrige oMLX: el parámetro `--memory-guard` respeta la opción de Atlas. Con el bloqueo desactivado se usa `off`; con el bloqueo activado se usa `safe`. Antes se imponía `safe` siempre y oMLX respondía HTTP 507 aunque el usuario hubiera desactivado el bloqueo en Atlas.
- No se cambian los límites de Metal ni los ajustes globales de macOS. Los errores reales de asignación del motor siguen aplicándose.
- Se mantienen el contexto predeterminado de 65.536 tokens y la ampliación de variables y salida de R de 1.1.4.

73 pruebas automatizadas aprobadas. Los cambios se ejecutan en el servidor del Mac y se aplican también al cliente iPad 1.1.4, que no necesita modificaciones nativas.

Pruebas reales con datos ficticios: Flint UD-IQ3_XXS cargó en llama en 18,5 s y respondió «media 22, muestra 3». Gemma 4 26B A4B QAT MLX 4bit cargó en oMLX en 13,4 s sin HTTP 507 y respondió correctamente a la misma prueba. Ambos con contexto configurado de 65.536. Se verificó el cierre de los motores tras la prueba.
