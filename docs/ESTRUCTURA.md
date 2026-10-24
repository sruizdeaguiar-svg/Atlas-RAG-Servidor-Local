# Estructura del proyecto

[English](STRUCTURE.en.md)

El repositorio y el ZIP de fuentes conservan la organización del código local.

```text
Atlas-RAG-Servidor-Local/
├── Abrir Atlas.command
├── LICENSE
├── NOTICE
├── README.md
├── requirements.txt
├── requirements.lock.txt
├── server/                  # API, RAG, usuarios, motores y análisis R
├── web/                     # Interfaz compartida por Mac, iPhone e iPad
├── native/                  # Aplicación y utilidades de macOS
├── ios/                     # SwiftUI, proyecto Xcode, iconos e instalación
│   └── releases/            # IPA sin firma; nunca perfiles personales
├── scripts/                 # Instalación, compilación y pruebas reproducibles
├── tests/                   # Pruebas automatizadas
└── docs/
    ├── ESTRUCTURA.md
    └── screenshots/         # Capturas con documentos ficticios
```

No se distribuyen las carpetas locales `datos/`, `var/`, `.chroma_db/`, `migration-backups/`, `.qa-external/`, las bibliotecas indexadas, credenciales, sesiones, certificados privados ni modelos. `.venv/`, `build/`, `dist/` y los paquetes `.app` se generan al instalar o compilar. Los instaladores se descargan por separado desde Releases.

Los scripts de migración de esta instalación concreta y sus informes privados no forman parte del paquete público. El asistente inicial crea un espacio nuevo y permite elegir la ubicación de sus datos.
