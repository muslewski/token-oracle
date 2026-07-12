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
