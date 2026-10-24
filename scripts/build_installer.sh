#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
TASK_INSTALLER=/private/tmp/atlas-installer
TASK_APP="$TASK_INSTALLER/image/Atlas RAG.app"
mkdir -p "$TASK_INSTALLER/image" dist
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' "$HOME/Applications/Atlas RAG.app/" "$TASK_APP/"
# Distribution must not retain the development workspace or one-off migration tools.
rm -f "$TASK_APP/Contents/Resources/source.path"
find "$TASK_APP/Contents/Resources/runtime/scripts" -type f ! -name control.py ! -name engine_entry.py -delete
COPYFILE_DISABLE=1 cp LICENSE NOTICE "$TASK_APP/Contents/Resources/"
cat > "$TASK_INSTALLER/image/LEEME.txt" <<'TXT'
Atlas RAG Local — Apple Silicon, macOS 27 o posterior (compilación verificada).
Arrastra Atlas RAG a Aplicaciones, ábrela y completa Configuración inicial.
Elige la unidad externa para la base de datos y crea tu administrador.
R y los motores de IA se detectan en el Mac; no se incluyen modelos.
R: https://mac.r-project.org/
Código, licencia Apache 2.0 e instrucciones: https://github.com/sruizdeaguiar-svg/Atlas-RAG-Servidor-Local
La firma disponible es de desarrollo. Este paquete no está notarizado para distribución general.
Los datos y las credenciales del desarrollador no se incluyen.
TXT
ln -sfn /Applications "$TASK_INSTALLER/image/Aplicaciones"
TASK_SIGN="${ATLAS_CODESIGN_IDENTITY:-$(security find-identity -v -p codesigning | awk '/Apple Development:/ {print $2; exit}')}"
xattr -cr "$TASK_APP"
codesign --force --deep --sign "${TASK_SIGN:--}" "$TASK_APP"
codesign --verify --deep --strict "$TASK_APP"
COPYFILE_DISABLE=1 pkgbuild --component "$TASK_APP" --install-location /Applications --identifier local.atlas.rag.installer --version 1.1.5 dist/Atlas-RAG-1.1.5-arm64.pkg
hdiutil create -ov -format UDZO -volname 'Atlas RAG Local' -srcfolder "$TASK_INSTALLER/image" dist/Atlas-RAG-1.1.5-arm64.dmg
shasum -a 256 dist/Atlas-RAG-1.1.5-arm64.pkg dist/Atlas-RAG-1.1.5-arm64.dmg > dist/SHA256SUMS-mac.txt
