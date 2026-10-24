#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if (( $# < 2 )); then
  print 'Usage: scripts/install_ipad.sh DEVICE_UDID DEVELOPMENT_TEAM'
  exit 2
fi
TASK_DEVICE="$1"
TASK_TEAM="$2"
TASK_PROJECT=/private/tmp/atlas-ios-clean
mkdir -p "$TASK_PROJECT" evidence dist
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' ios/ "$TASK_PROJECT/"
xcodebuild -project "$TASK_PROJECT/AtlasRAG.xcodeproj" -scheme AtlasRAG -configuration Release -sdk iphoneos -destination "id=$TASK_DEVICE" -derivedDataPath /private/tmp/atlas-ipad-signed -allowProvisioningUpdates -allowProvisioningDeviceRegistration DEVELOPMENT_TEAM="$TASK_TEAM" CODE_SIGN_STYLE=Automatic build > evidence/ipad-signed-build.txt 2>&1
TASK_APP=/private/tmp/atlas-ipad-signed/Build/Products/Release-iphoneos/AtlasRAG.app
codesign --verify --deep --strict "$TASK_APP"
COPYFILE_DISABLE=1 rsync -a --delete --exclude='._*' "$TASK_APP/" dist/AtlasRAG-iPad.app/
xcrun devicectl device install app --device "$TASK_DEVICE" "$TASK_APP" --timeout 90 --json-output /private/tmp/atlas-ipad-install.json > evidence/ipad-install.txt 2>&1
xcrun devicectl device process launch --device "$TASK_DEVICE" local.atlas.rag.ios --timeout 30 --json-output /private/tmp/atlas-ipad-launch.json > evidence/ipad-launch.txt 2>&1
print 'Atlas installed and launched on the selected iPad.'
