#!/bin/zsh
set -euo pipefail
TASK_APP="$HOME/Applications/Atlas RAG.app"
if [[ ! -d "$TASK_APP" ]]; then
  print -u2 'Primero ejecuta scripts/install.sh desde este proyecto.'
  exit 1
fi
open "$TASK_APP"
