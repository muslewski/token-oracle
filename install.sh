#!/bin/sh
# token-oracle installer.
#   curl -fsSL https://raw.githubusercontent.com/muslewski/token-oracle/main/install.sh | sh
# Installs the token-oracle Python CLI to your user environment. No sudo. No root writes.
set -eu

PKG="token-oracle"
say() { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

add_user_bins_to_path() {
  for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
    case ":$PATH:" in
      *":$d:"*) ;;
      *) [ -d "$d" ] && PATH="$d:$PATH" ;;
    esac
  done
  export PATH
}

say "🔮 installing $PKG ..."

if have uv; then
  say "→ using uv"
  uv tool install "$PKG"
elif have pipx; then
  say "→ using pipx"
  pipx install "$PKG"
elif have python3 || have python; then
  say "→ no uv/pipx found; installing uv (fast Python tool runner)"
  if curl -LsSf https://astral.sh/uv/install.sh | sh; then
    add_user_bins_to_path
    if have uv; then
      uv tool install "$PKG"
    else
      say "→ uv installed but not yet on PATH; using pip --user instead"
      python3 -m pip install --user "$PKG" 2>/dev/null || python -m pip install --user "$PKG"
    fi
  else
    say "→ uv bootstrap failed; using pip --user instead"
    python3 -m pip install --user "$PKG" 2>/dev/null || python -m pip install --user "$PKG"
  fi
else
  say "✗ $PKG needs Python >= 3.10 (not found)."
  say "  Install Python first: https://www.python.org/downloads/  then re-run."
  exit 1
fi

add_user_bins_to_path
say ""
if have token-oracle; then
  say "✓ installed: $(command -v token-oracle)"
  say ""
  say "next:"
  say "  token-oracle forecast     # time left before your cap"
  say "  token-oracle dash         # full-screen live dashboard"
  say "  token-oracle live-setup   # optional: real browser-verified numbers"
else
  say "✓ installed, but 'token-oracle' is not on PATH yet."
  say "  Add your user bin dir and reload your shell:"
  say '    export PATH="$HOME/.local/bin:$PATH"   # add to ~/.bashrc or ~/.zshrc'
  say "  Then:  token-oracle dash"
fi
