# Project structure

[Español](ESTRUCTURA.md) · [English README](../README.en.md) · [User guide](GUIDE.en.md)

The repository and source ZIP preserve the source project's directory layout.

```text
Atlas-RAG-Servidor-Local/
├── Abrir Atlas.command
├── LICENSE
├── NOTICE
├── README.md                # Spanish
├── README.en.md             # English
├── requirements.txt
├── requirements.lock.txt
├── server/                  # API, RAG, users, engines and R analysis
├── web/                     # Shared Mac, iPhone and iPad interface
├── native/                  # macOS application and native helpers
├── ios/                     # SwiftUI, Xcode project, icons and installation
│   └── releases/            # Unsigned IPA; no personal profiles
├── scripts/                 # Installation, builds and reproducible checks
├── tests/                   # Automated tests
└── docs/
    ├── ESTRUCTURA.md
    ├── STRUCTURE.en.md
    ├── GUIA.md
    ├── GUIDE.en.md
    └── screenshots/         # Screenshots with fictitious documents
```

Local `datos/`, `var/`, `.chroma_db/`, `migration-backups/` and `.qa-external/` directories, indexed libraries, credentials, sessions, private certificates and models are not distributed. `.venv/`, `build/`, `dist/` and `.app` bundles are generated during installation or builds. Installers are separate Release downloads.

Installation-specific migration scripts and private reports are excluded. Initial setup creates a new workspace and lets the user choose its data directory. The internal local-operations log is not public project documentation and is not included in source exports.
