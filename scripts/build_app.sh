#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
TASK_PROJECT="$PWD"
.venv/bin/python -B scripts/prepare_engine_security.py
TASK_BUILD="/private/tmp/atlas-rag-build"
mkdir -p "$TASK_BUILD" build
COPYFILE_DISABLE=1 cp native/Atlas.swift "$TASK_BUILD/Atlas.swift"
COPYFILE_DISABLE=1 cp native/DocumentTools.swift "$TASK_BUILD/DocumentTools.swift"
swiftc -O "$TASK_BUILD/DocumentTools.swift" -o build/DocumentTools
COPYFILE_DISABLE=1 cp native/EngineTools.swift "$TASK_BUILD/EngineTools.swift"
swiftc -O "$TASK_BUILD/EngineTools.swift" -o build/EngineTools -framework AppKit
TASK_APP="$TASK_BUILD/Atlas RAG.app"
mkdir -p "$TASK_APP/Contents/MacOS" "$TASK_APP/Contents/Resources"
swiftc -O "$TASK_BUILD/Atlas.swift" -o "$TASK_APP/Contents/MacOS/AtlasRAG" -framework Cocoa -framework WebKit
TASK_RUNTIME="$TASK_APP/Contents/Resources/runtime"
mkdir -p "$TASK_RUNTIME"
for TASK_FOLDER in server scripts web build; do
  COPYFILE_DISABLE=1 rsync -a --exclude='._*' --exclude='__pycache__' --exclude='.pytest_cache' "$TASK_PROJECT/$TASK_FOLDER/" "$TASK_RUNTIME/$TASK_FOLDER/"
done
# Bundle a relocatable Python runtime; no external executable symlinks in the signed app.
TASK_PYTHON_BASE="$(.venv/bin/python -c 'import sys; print(sys.base_prefix)')"
mkdir -p "$TASK_RUNTIME/python"
COPYFILE_DISABLE=1 rsync -a --exclude='._*' --exclude='__pycache__' "$TASK_PYTHON_BASE/" "$TASK_RUNTIME/python/"
COPYFILE_DISABLE=1 rsync -a --exclude='._*' --exclude='__pycache__' .venv/lib/python3.14/site-packages/ "$TASK_RUNTIME/python/lib/python3.14/site-packages/"
if [[ -d "$TASK_RUNTIME/.venv" ]]; then rm -rf "$TASK_RUNTIME/.venv"; fi
printf '%s' "$TASK_PROJECT" > "$TASK_APP/Contents/Resources/source.path"
cat > "$TASK_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>CFBundleExecutable</key><string>AtlasRAG</string><key>CFBundleIdentifier</key><string>local.atlas.rag</string><key>CFBundleName</key><string>Atlas RAG</string><key>CFBundleDisplayName</key><string>Atlas RAG Local</string><key>CFBundleVersion</key><string>1</string><key>CFBundleShortVersionString</key><string>1.1.3</string><key>NSRemovableVolumesUsageDescription</key><string>Atlas indexes document folders that you select on external drives.</string><key>NSDocumentsFolderUsageDescription</key><string>Atlas accesses document folders you choose for indexing.</string><key>NSHighResolutionCapable</key><true/><key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict></dict></plist>
PLIST
mkdir -p "$TASK_BUILD/icon.iconset"
COPYFILE_DISABLE=1 cp native/Icon.swift "$TASK_BUILD/Icon.swift"
swift "$TASK_BUILD/Icon.swift" "$TASK_BUILD/icon.iconset"
cp "$TASK_BUILD/icon.iconset/icon_32x32.png" "$TASK_BUILD/icon.iconset/icon_16x16@2x.png"
cp "$TASK_BUILD/icon.iconset/icon_64x64.png" "$TASK_BUILD/icon.iconset/icon_32x32@2x.png"
rm "$TASK_BUILD/icon.iconset/icon_64x64.png"
cp "$TASK_BUILD/icon.iconset/icon_256x256.png" "$TASK_BUILD/icon.iconset/icon_128x128@2x.png"
cp "$TASK_BUILD/icon.iconset/icon_512x512.png" "$TASK_BUILD/icon.iconset/icon_256x256@2x.png"
cp "$TASK_BUILD/icon.iconset/icon_1024x1024.png" "$TASK_BUILD/icon.iconset/icon_512x512@2x.png"
rm "$TASK_BUILD/icon.iconset/icon_1024x1024.png"
iconutil -c icns "$TASK_BUILD/icon.iconset" -o "$TASK_APP/Contents/Resources/Atlas.icns"
/usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string Atlas' "$TASK_APP/Contents/Info.plist"
xattr -cr "$TASK_APP"
TASK_SIGN_IDENTITY="${ATLAS_CODESIGN_IDENTITY:-}"
if [[ -z "$TASK_SIGN_IDENTITY" ]]; then
  TASK_SIGN_IDENTITY="$(security find-identity -v -p codesigning | awk '/Apple Development:/ {print $2; exit}')"
fi
codesign --force --deep --sign "${TASK_SIGN_IDENTITY:--}" "$TASK_APP"
mkdir -p "$HOME/Applications"
COPYFILE_DISABLE=1 rsync -a --delete --delete-excluded --exclude="._*" "$TASK_APP/" "$HOME/Applications/Atlas RAG.app/"
COPYFILE_DISABLE=1 rsync -a --delete --delete-excluded --exclude="._*" "$TASK_APP/" "$TASK_PROJECT/Atlas RAG.app/"
xattr -cr "$HOME/Applications/Atlas RAG.app"
xattr -d com.apple.FinderInfo "$HOME/Applications/Atlas RAG.app" 2>/dev/null || true
codesign --verify --deep --strict "$HOME/Applications/Atlas RAG.app"
if [[ -d "$HOME/Desktop" && ! -e "$HOME/Desktop/Atlas RAG.app" && ! -L "$HOME/Desktop/Atlas RAG.app" ]]; then
  ln -s "$HOME/Applications/Atlas RAG.app" "$HOME/Desktop/Atlas RAG.app"
fi
printf 'Built %s\n' "$HOME/Applications/Atlas RAG.app"
