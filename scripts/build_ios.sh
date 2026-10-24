#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
TASK_IOS=/private/tmp/atlas-ios-clean
TASK_CACHE=/private/tmp/atlas-swift-cache
mkdir -p "$TASK_IOS" "$TASK_CACHE" /private/tmp/atlas-ios-icons evidence
COPYFILE_DISABLE=1 cp native/Icon.swift /private/tmp/atlas-ios-icons/Icon.swift
CLANG_MODULE_CACHE_PATH="$TASK_CACHE" swift -module-cache-path "$TASK_CACHE" /private/tmp/atlas-ios-icons/Icon.swift /private/tmp/atlas-ios-icons --opaque
for TASK_SIZE in 20 29 40 58 60 76 80 87 120 152 167 180 1024; do
  sips -z "$TASK_SIZE" "$TASK_SIZE" /private/tmp/atlas-ios-icons/icon_1024x1024.png --out "ios/AtlasRAG/Assets.xcassets/AppIcon.appiconset/Icon-$TASK_SIZE.png" >/dev/null
done
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' ios/ "$TASK_IOS/"
xcodebuild -project "$TASK_IOS/AtlasRAG.xcodeproj" -scheme AtlasRAG -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /private/tmp/atlas-ios-derived CODE_SIGNING_ALLOWED=NO ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build > evidence/ios-build.txt 2>&1
mkdir -p dist
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' /private/tmp/atlas-ios-derived/Build/Products/Debug-iphonesimulator/AtlasRAG.app/ dist/AtlasRAG-Simulator.app/
xcodebuild -project "$TASK_IOS/AtlasRAG.xcodeproj" -scheme AtlasRAG -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath /private/tmp/atlas-ios-device CODE_SIGNING_ALLOWED=NO ARCHS=arm64 build > evidence/ios-device-build.txt 2>&1
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' /private/tmp/atlas-ios-device/Build/Products/Release-iphoneos/AtlasRAG.app/ dist/AtlasRAG-iOS-unsigned.app/
printf 'iPhone/iPad simulator and unsigned device builds completed.\n'
