# Plan 046 — npm shim: `npx token-oracle` / `bunx token-oracle`

**Status:** TODO
**Priority:** P1 (Phase 2 "make it spread" — keystone; ccusage's entire
distribution moat is `npx ccusage`)
**Effort:** M
**Risk:** medium (new distribution surface; must pass through stdio/args/exit
faithfully and degrade honestly when no Python runner exists)
**Written against commit:** (stamp `git rev-parse --short HEAD` at execution)
**Files in scope (all NEW):** `npm/package.json`, `npm/bin/cli.js`, `npm/README.md`, `npm/.gitignore`
**Do NOT touch:** any Python, the root `README.md` (plan 049 owns it), `pyproject.toml`, or anything outside `npm/`.

---

## Why this matters

`npx ccusage` is why ccusage (17k★) is the default — one command, zero install.
token-oracle is already on PyPI (`pipx install token-oracle`, `uvx token-oracle`
both work), but there is no `npx`/`bunx` entry, so it misses the exact muscle
memory its competitor owns. This plan adds a tiny **npm package** whose only job
is to run the real Python CLI via an ephemeral Python runner, passing everything
through. No npm dependencies. It reuses PyPI — no binary build pipeline.

## Design (read before coding)

The shim tries runners in order and stops at the first one that **exists**
(exit code, whatever it is, is then propagated — a present-but-failed runner is a
real error to surface, not a reason to fall through):

1. **`uvx token-oracle <args>`** — uv's ephemeral runner. Preferred: no
   persistent install, always the latest published PyPI version.
2. **`pipx run --spec token-oracle token-oracle <args>`** — pipx's ephemeral run.
3. **already-installed package** — if `python3`/`python` can `import token_oracle`
   (the user ran `pipx install`/`pip install` earlier), run
   `python -m token_oracle.cli.main <args>`.
4. **none available** → print honest guidance (install uv, or pipx/pip) to
   stderr and exit 1. **Never silently `pip install` from an `npx` invocation** —
   a persistent, unexpected environment mutation is the wrong default.

Unpinned by design: `npx token-oracle` runs the **latest** PyPI release, so users
get fixes without waiting for an npm republish. The npm `version` tracks the shim
itself, not the Python package (documented in the maintenance note).

Stdio is inherited so the full-screen `dash` TUI, colors, stdin, and Ctrl-C all
work. Exit codes propagate.

## Files to create

### `npm/package.json`

```json
{
  "name": "token-oracle",
  "version": "0.1.1",
  "description": "Forecast when you'll hit your Claude Code / Grok token limits — offline from local logs, optionally browser-verified. Python CLI, runnable with npx/bunx.",
  "bin": {
    "token-oracle": "bin/cli.js"
  },
  "keywords": [
    "claude", "claude-code", "grok", "tokens", "token-usage", "usage",
    "forecast", "cli", "ccusage", "anthropic", "xai"
  ],
  "homepage": "https://github.com/muslewski/token-oracle#readme",
  "repository": {
    "type": "git",
    "url": "git+https://github.com/muslewski/token-oracle.git"
  },
  "bugs": {
    "url": "https://github.com/muslewski/token-oracle/issues"
  },
  "license": "MIT",
  "author": "Mateusz Muślewski",
  "engines": {
    "node": ">=14"
  },
  "files": [
    "bin/",
    "README.md"
  ]
}
```

### `npm/bin/cli.js`

```js
#!/usr/bin/env node
"use strict";

// npm shim for token-oracle (a Python CLI). Runs the real tool via an ephemeral
// Python runner (uv/pipx) or an already-installed copy, passing through args,
// stdio (so the `dash` TUI + stdin + Ctrl-C work), and the exit code.
// Zero npm dependencies.

const { spawnSync } = require("child_process");

const args = process.argv.slice(2);

// Run `cmd cmdArgs...` inheriting stdio.
// Returns the numeric exit code if the command EXISTS (ran), or null if the
// command was not found (ENOENT) so the caller can try the next strategy.
function tryRun(cmd, cmdArgs) {
  const r = spawnSync(cmd, cmdArgs, { stdio: "inherit" });
  if (r.error && r.error.code === "ENOENT") return null;
  if (r.error) {
    // Existed but failed to spawn for another reason — surface it.
    process.stderr.write(`token-oracle: failed to run ${cmd}: ${r.error.message}\n`);
    return 1;
  }
  if (typeof r.status === "number") return r.status;
  if (r.signal) return 1;
  return 0;
}

// True if `py` can import the installed token_oracle package.
function pythonHasModule(py) {
  const r = spawnSync(py, ["-c", "import token_oracle"], { stdio: "ignore" });
  return !r.error && r.status === 0;
}

function guidanceAndExit() {
  process.stderr.write(
    [
      "token-oracle is a Python tool and needs a runner on your PATH.",
      "",
      "Fastest (recommended) — install uv, then this command just works:",
      "  curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux",
      "  powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"   # Windows",
      "  # then re-run your command, e.g.:  npx token-oracle forecast",
      "",
      "Or install token-oracle directly:",
      "  pipx install token-oracle      # isolated",
      "  pip install token-oracle       # into your current environment",
      "",
      "Requires Python >= 3.10.  Docs: https://github.com/muslewski/token-oracle",
      "",
    ].join("\n")
  );
  process.exit(1);
}

function main() {
  // 1) uv ephemeral runner (latest PyPI, no persistent install)
  let code = tryRun("uvx", ["token-oracle", ...args]);
  if (code !== null) process.exit(code);

  // 2) pipx ephemeral runner
  code = tryRun("pipx", ["run", "--spec", "token-oracle", "token-oracle", ...args]);
  if (code !== null) process.exit(code);

  // 3) already-installed Python package
  for (const py of ["python3", "python"]) {
    if (pythonHasModule(py)) {
      code = tryRun(py, ["-m", "token_oracle.cli.main", ...args]);
      if (code !== null) process.exit(code);
    }
  }

  // 4) nothing available — guide, do not silently install
  guidanceAndExit();
}

main();
```

### `npm/README.md`

```markdown
# token-oracle (npx shim)

`npx token-oracle` / `bunx token-oracle` — run the
[token-oracle](https://github.com/muslewski/token-oracle) Python CLI without a
manual install.

```bash
npx token-oracle forecast     # time left before your next cap
npx token-oracle dash         # full-screen live dashboard
bunx token-oracle doctor      # check config, data sources, live status
```

This package is a thin launcher. It runs the real tool through `uvx` or
`pipx` (or an already-installed copy), so you need one of:

- **uv** (recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **pipx**: `pipx install token-oracle`
- or Python ≥ 3.10 with `pip install token-oracle`

It runs the **latest** published PyPI release. Full docs, screenshots, and the
offline/live details live in the
[main repository](https://github.com/muslewski/token-oracle).
```

### `npm/.gitignore`

```
node_modules/
*.tgz
```

## How to verify (executor — run from repo root, then from `npm/`)

The executor's environment may or may not have uv/pipx/token-oracle, so verify
what is env-independent:

1. **Syntax check** (must pass regardless of runners):
   `node --check npm/bin/cli.js`
2. **package.json is valid JSON**:
   `node -e "JSON.parse(require('fs').readFileSync('npm/package.json','utf8')); console.log('ok')"`
3. **`npm pack` produces a tarball with exactly bin/ + README.md + package.json**:
   `cd npm && npm pack --dry-run 2>&1` — the file list must include
   `package/bin/cli.js`, `package/package.json`, `package/README.md` and NOT
   `node_modules` or a `.tgz`.
4. **Runtime smoke (env-tolerant)**: `node npm/bin/cli.js --help`
   - If a runner (uvx/pipx) or an installed `token_oracle` IS present: it prints
     token-oracle's own help.
   - If NONE is present: it prints the guidance block and exits 1.
   - In BOTH cases there must be **no Node stack trace** and no
     `Error:`/`throw` from the shim itself. Capture and check:
     `node npm/bin/cli.js --help; echo "exit=$?"` — exit is either token-oracle's
     (0 for --help) or 1 (guidance). Any other Node-level crash is a failure.

Do NOT run `npm publish` (that is the operator's outward action) and do NOT run
`npm install` (there are no dependencies). Do NOT add any dependency.

## Done criteria (machine-checkable)

1. `node --check npm/bin/cli.js` exits 0.
2. `npm/package.json` parses as JSON and has `bin["token-oracle"] == "bin/cli.js"`.
3. `cd npm && npm pack --dry-run` lists `package/bin/cli.js` and does NOT list
   `node_modules`.
4. `node npm/bin/cli.js --help` prints either token-oracle help OR the guidance
   block, with no Node stack trace, and a defined exit code (0 or 1).
5. `git status --short` shows only new files under `npm/`.
6. The existing Python test suite still passes unchanged (`python -m pytest -q`
   from repo root) — this plan touches no Python, so it must be untouched.

## Escape hatches (STOP and report)

- If `spawnSync` with `stdio: "inherit"` does not exist in the target Node
  version, STOP — do not rewrite with manual pipe plumbing; report the Node
  version.
- If the npm name `token-oracle` turns out to be taken at publish time (it is
  free as of writing), that is an operator/publish concern, not this plan's —
  build the package as named; note it.
- Do NOT invent an auto-install path that mutates the user's Python environment
  from `npx`. If you feel the guidance-only fallback is "not seamless enough",
  STOP and report rather than adding a silent `pip install`.

## Maintenance note

- **Unpinned on purpose:** the shim runs the latest PyPI release. The npm
  `version` is the shim's own version — bump it only when `bin/cli.js` or
  metadata changes, not on every PyPI release.
- **Publishing (operator, outward action):** `cd npm && npm publish` (name
  `token-oracle`, currently unregistered). Requires an npm login. The advisor
  will smoke-test `npx`/`bunx` locally before recommending publish.
- Windows `.cmd` shim quirks (uv/pipx installed as `.exe`) are handled by
  `spawnSync` finding them on PATH; if a future Windows bug appears, prefer
  `where`-based detection over `shell: true`.
