#!/usr/bin/env bash
# Regenerate every README demo GIF from staged fixtures.
# Requires: vhs, ttyd, ffmpeg on PATH + green-ui-kit harness installed.
set -euo pipefail
cd "$(dirname "$0")"
GREEN_DEMO="${GREEN_DEMO:-$HOME/.local/lib/green-demo.sh}"
[ -r "$GREEN_DEMO" ] || {
  echo "green-demo.sh not found — run green-ui-kit/install.sh" >&2
  exit 1
}
# shellcheck disable=SC1090
. "$GREEN_DEMO"
# Capture real user base before sandbox remaps HOME (vhs inherits this env).
REAL_PYTHONUSERBASE="$HOME/.local"
demo_sandbox "$PWD" # exports HOME + 4 XDG vars, runs fixtures/gen.sh
export PYTHONUSERBASE="$REAL_PYTHONUSERBASE"
export TOKEN_ORACLE_SKIP_BOOTSTRAP=1
# token-oracle demos do not need the isolated tmux server
for tape in scenes/*.tape; do
  demo_record "$tape"
done
