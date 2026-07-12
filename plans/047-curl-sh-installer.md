# Plan 047 — `curl | sh` one-line installer

**Status:** TODO
**Priority:** P2 (Phase 2 "make it spread" — the non-Node one-liner)
**Effort:** S
**Risk:** medium (a piped-to-shell installer must be safe: no sudo, no `rm`, no
destructive ops; user-local installs only)
**Written against commit:** (stamp `git rev-parse --short HEAD` at execution)
**Files in scope (NEW):** `install.sh` (repo root)
**Do NOT touch:** any Python, `README.md` (plan 049 documents this), `npm/`.

---

## Why this matters

Not everyone has Node (`npx`) or wants it. The other universal one-liner is
`curl -fsSL .../install.sh | sh`. Unlike the npx shim — which must NOT mutate the
user's environment silently — this script is explicitly run by the user to
install, so it MAY bootstrap `uv` and perform a persistent install.

## Design (read before coding)

Strategy, first match wins:

1. **`uv` present** → `uv tool install token-oracle` (isolated, on PATH).
2. **`pipx` present** → `pipx install token-oracle`.
3. **neither, but Python present** → install `uv` via its official installer
   (the user opted into an installer by running this), add its bin dir to PATH
   for the current shell, then `uv tool install token-oracle`. If uv bootstrap
   fails, fall back to `pip install --user token-oracle`.
4. **no Python at all** → print how to get Python ≥ 3.10 and exit 1.

Hard safety rules: POSIX `#!/bin/sh`, `set -eu`, **no `sudo`, no `rm`, no writes
outside user-local install dirs**, no piping of anything except the official uv
installer. Idempotent (re-running upgrades / says already-installed). End by
verifying `token-oracle` is runnable and printing next steps.

## File to create — `install.sh`

```sh
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
```

## How to verify (executor)

Do NOT actually execute the installer (it has real, persistent side effects —
installing uv and the package). Verify statically:

1. **POSIX syntax check:** `sh -n install.sh` exits 0.
2. **`shellcheck install.sh`** (if shellcheck is on PATH) reports no errors; if
   shellcheck is absent, say so in your report and rely on `sh -n`.
3. **Safety greps — all must return NOTHING:**
   - `grep -nE '\bsudo\b' install.sh`
   - `grep -nE '\brm\b' install.sh`
   - `grep -nE '\bcurl[^|]*\|[[:space:]]*sh' install.sh` should match ONLY the
     single official `astral.sh/uv/install.sh` line (no other pipe-to-shell).
4. **Shebang is `#!/bin/sh`** and the file is not marked executable is fine (it
   is run via `sh`); but DO `chmod +x install.sh` so a cloned copy runs directly.

## Done criteria (machine-checkable)

1. `sh -n install.sh` exits 0.
2. `grep -c 'sudo' install.sh` == 0 and `grep -c '\brm\b' install.sh` == 0.
3. The only pipe-to-shell in the file is the `astral.sh/uv/install.sh` line
   (`grep -c 'astral.sh/uv/install.sh' install.sh` == 1).
4. `git status --short` shows only `install.sh` (new).
5. Python suite unchanged (`python -m pytest -q` from repo root still passes).

## Escape hatches (STOP and report)

- If the plan's strategy would require `sudo` for any path, STOP — a curl|sh
  installer must never escalate. Report the case instead.
- Do NOT add a Homebrew/apt/dnf branch in this plan (out of scope; those are
  package-manager recipes, a separate concern). Keep it to uv/pipx/pip.

## Maintenance note

The install.sh URL (`raw.githubusercontent.com/muslewski/token-oracle/main/install.sh`)
is only live once this file is on `main`. Plan 049 adds the `curl | sh` line to
the README. Pin nothing — `uv tool install token-oracle` / `pipx install`
fetch the latest PyPI release. Re-audit this file's safety on any change; it runs
on strangers' machines.
