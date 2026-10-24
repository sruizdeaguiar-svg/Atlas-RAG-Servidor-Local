# Atlas RAG Local 1.1.4

- Contexto predeterminado de los motores gestionados: **65.536 tokens**, en escritorio e iPad, en todos los selectores. El contexto efectivo aparece junto al modelo. Los límites propios del motor/modelo siguen aplicándose.
- Salida de R ampliada a **32 MiB por ejecución**, sin el recorte anterior a 200.000 caracteres. Se habilita la impresión completa de R; si se alcanza el límite se marca el análisis como incompleto. El resultado se conserva en la pantalla, TXT y ZIP.
- R admite hasta **256 variables seleccionadas**, frente a las 20 anteriores. Es el mismo máximo que admite el lector de tablas.
- La interpretación con IA recibe todos los resultados guardados de R; se elimina el recorte silencioso a 20.000 caracteres.
- Los errores de contexto del motor tienen un mensaje específico. No se vuelcan respuestas del motor que puedan contener datos privados.
- El tiempo de espera para inferencia local pasa a 10 minutos, para permitir respuestas de modelos grandes.
- La estimación de RAM continúa siendo informativa por defecto; su bloqueo sigue siendo opcional.

Se mantienen los permisos, el aislamiento de documentos/R y la validación HTTPS de la 1.1.3. Estos cambios no amplían el acceso a datos ni habilitan envíos a la nube.

Validación: 70 pruebas automatizadas aprobadas, incluido R real con 25 variables; 30 comprobaciones HTTP/HTTPS aisladas aprobadas. Se utilizan datos ficticios.

Prueba física en iPad: ejecución de R sobre el CSV ficticio de temperaturas e interpretación con Qwen3.5 9B en LM Studio, cargado con 65.536 tokens. Respuesta recibida sin HTTP 400.
