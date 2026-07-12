# Plan 049 — README Install section: npx / bunx / curl + uv / pipx / pip

**Status:** TODO
**Priority:** P1 (Phase 2 — the Install section is the most-read block after the
hero; it must show the frictionless channels first)
**Effort:** S
**Risk:** low (README markdown), but see the **sequencing caveat** below —
`npx token-oracle` only works after the npm package is published.
**Written against commit:** (stamp `git rev-parse --short HEAD` at execution)
**Files in scope:** `README.md` (Install section only)
**Do NOT touch:** the hero/banner/badges/demo block (top of README), the
`npm/` package (plan 046), `install.sh` (plan 047), or any Python.

---

## Why this matters

Today the Install section lists only `pipx`/`pip`/`uvx`. The two highest-reach
channels — `npx`/`bunx` (matching `npx ccusage`) and the `curl | sh` one-liner —
are missing. A visitor decides whether to try the tool in the first ten seconds;
the fastest path must be first.

## Sequencing caveat (the executor must reproduce this note in its report)

The `npx token-oracle` / `bunx token-oracle` lines only resolve once the npm
package (plan 046) is **published** (`npm publish`), and the `curl | sh` line
only resolves once `install.sh` (plan 047) is on the pushed `main`. This plan
edits the README to include them; the advisor gates the public push on those
channels being live. Do NOT remove or comment out the lines — just include them
as written.

## Current state (exact excerpt — `README.md`, lines 18–27)

```markdown
## Install

```bash
pipx install token-oracle   # recommended — isolated environment
pip install token-oracle    # fallback
uvx token-oracle            # uv users
```

## Quickstart
```

## The fix — replace the Install section

Replace everything from the `## Install` heading through the end of its code
block (up to, but NOT including, `## Quickstart`) with:

```markdown
## Install

**Run it instantly** — no install, using a runner you probably already have:

```bash
npx token-oracle dash         # Node
bunx token-oracle dash        # Bun
uvx token-oracle dash         # uv
```

**Or install** the `token-oracle` command onto your PATH:

```bash
curl -fsSL https://raw.githubusercontent.com/muslewski/token-oracle/main/install.sh | sh
uv tool install token-oracle   # uv (isolated, fast)
pipx install token-oracle      # pipx (isolated)
pip install token-oracle       # pip
```

> `npx`/`bunx`/`uvx` fetch and run the latest release on demand; the installers
> put it on your PATH. All routes are the same offline-first tool — see
> [SETUP.md](./SETUP.md) for live web data and configuration.
```

Keep the `## Quickstart` section that follows exactly as it is.

## Done criteria (machine-checkable)

1. `grep -c "npx token-oracle" README.md` ≥ 1 and `grep -c "bunx token-oracle" README.md` ≥ 1.
2. `grep -c "install.sh | sh" README.md` == 1.
3. `grep -c "uv tool install token-oracle" README.md` == 1.
4. The `## Quickstart` heading still exists (`grep -c "## Quickstart" README.md` == 1)
   and the hero/banner/demo block above `## Install` is unchanged
   (`grep -c "dash-demo.gif" README.md` == 1).
5. `git diff --stat` shows only `README.md`.

## Escape hatches

- If the Install section's current content differs from the excerpt (README may
  have changed), replace the block bounded by `## Install` and the next `##`
  heading with the new content, preserving that next heading. If you cannot
  cleanly identify the boundary, STOP and report.
- Do NOT touch the demo GIF block or badges.

## Maintenance note

The four install commands and three run commands must stay in sync with what
plans 046 (npm shim) and 047 (install.sh) actually provide. If the npm package
name or the install.sh path changes, update this section.
