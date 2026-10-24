#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
export UV_CACHE_DIR="${TMPDIR:-/private/tmp}/atlas-uv-cache"
export UV_LINK_MODE=copy
if ! command -v uv >/dev/null; then
  print -u2 'Instala uv desde https://docs.astral.sh/uv/getting-started/installation/ y repite este script.'
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.14 .venv; fi
uv pip install --python .venv/bin/python -r requirements.lock.txt
if ! command -v Rscript >/dev/null && [[ ! -x /opt/homebrew/bin/Rscript ]]; then
  if command -v brew >/dev/null; then HOMEBREW_NO_AUTO_UPDATE=1 brew install r
  else print -u2 'Instala R para Apple Silicon desde https://mac.r-project.org/bin/macosx/'; exit 1
  fi
fi
./scripts/build_app.sh
