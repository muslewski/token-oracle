# Plan 009: Close the release-automation gap (release-please tag must trigger publish)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- .github/workflows/release-please.yml .github/workflows/publish.yml`
> If either workflow changed since this plan was written, compare the
> "Current state" excerpts against the live files before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW-MED (release infrastructure; misconfiguration blocks releases until reverted)
- **Depends on**: none. **Requires one human action** (create a PAT) — see Step 1.
- **Category**: dx
- **Planned at**: commit `d2b4d32`, 2026-07-01

## Why this matters

The repo's own design spec (local doc `docs/superpowers/specs/2026-06-30-distribution-and-quality-design.md`, decisions D5/D6) promises "No manual version management required after setup." Reality, documented in `publish.yml`'s header comment: tags pushed by release-please's default `GITHUB_TOKEN` do **not** trigger the publish workflow (GitHub blocks same-actor workflow chaining), so every release needs a human to push the tag or click workflow_dispatch. A forgotten manual step means PyPI silently lags GitHub releases. The fix release-please itself documents: run the action with a personal access token so the tag push comes from a different actor. This plan wires the token with a safe fallback and updates the stale comments — closing the drift between the decision doc and reality.

## Current state

- `.github/workflows/release-please.yml` — full file at `d2b4d32`:

```yaml
name: Release Please

on:
  push:
    branches:
      - main

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

- `.github/workflows/publish.yml:1-11` — the header comment documenting the gap (trigger model: `push: tags: v*` + `workflow_dispatch`; "a tag pushed by release-please's default GITHUB_TOKEN will NOT trigger this workflow"; "For fully automated publishing without the manual push, configure release-please with a PAT or a GitHub App token").
- Release flow context: release-please opens a release PR on pushes to `main`; merging it bumps `pyproject.toml` + `token_oracle/__init__.py`, updates `CHANGELOG.md`, and pushes tag `vX.Y.Z`; `publish.yml` builds and publishes to PyPI via OIDC trusted publishing (no stored PyPI token — keep it that way).
- The repo is `muslewski/token-oracle` on GitHub.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| YAML sanity | `python -c "import tomllib"` is irrelevant — use: `gh workflow list` (after push) or a YAML parse via `python - <<'EOF'` with `json`? — **use actionlint if installed**: `actionlint .github/workflows/release-please.yml` | no errors |
| Secret check | `gh secret list --repo muslewski/token-oracle` | shows `RELEASE_PLEASE_TOKEN` after Step 1 |
| Fallback YAML check (no actionlint) | `python -c "import yaml"` — PyYAML may be absent; if so, rely on careful diff + actionlint in CI marketplace | — |

Note: you cannot fully test a release pipeline locally. Verification here is configuration-level; the first real release is the end-to-end test (see Maintenance notes).

## Scope

**In scope** (the only files you should modify):
- `.github/workflows/release-please.yml`
- `.github/workflows/publish.yml` (comment block only)

**Out of scope** (do NOT touch):
- `release-please-config.json`, `.release-please-manifest.json` — working correctly.
- The OIDC publish job itself (`environment: pypi`, `id-token: write`) — do not introduce a stored PyPI token under any circumstances.
- `docs/superpowers/…` — local-only untracked docs; note for the maintainer instead (Maintenance notes).

## Git workflow

- Branch: `advisor/009-release-automation`.
- Conventional commit, e.g.: `ci: run release-please with PAT so release tags trigger publish`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: HUMAN ACTION — create and store the token

This step must be performed by the repo owner (an agent must not create PATs). Report it as a required manual step and wait for confirmation, or verify it is already done via `gh secret list`:

1. GitHub → Settings → Developer settings → Fine-grained personal access tokens → Generate new token.
2. Repository access: only `muslewski/token-oracle`. Permissions: **Contents: Read and write**, **Pull requests: Read and write**. Expiration: owner's choice (note the renewal burden).
3. Repo → Settings → Secrets and variables → Actions → New repository secret: name `RELEASE_PLEASE_TOKEN`, value = the token.

Security note (normal prose, no shortcuts): never write the token value into any file, log, or plan. Only the secret *name* appears in the workflow.

**Verify**: `gh secret list --repo muslewski/token-oracle` → row `RELEASE_PLEASE_TOKEN`. If you lack permission to list secrets, record "unverified — owner must confirm" in your report and continue (the fallback in Step 2 keeps the pipeline working either way).

### Step 2: Wire the token with a graceful fallback

Edit `release-please.yml`, adding one line to the action's `with:` block:

```yaml
      - uses: googleapis/release-please-action@v4
        with:
          token: ${{ secrets.RELEASE_PLEASE_TOKEN || github.token }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

The `|| github.token` expression falls back to the default token when the secret is unset — behavior then remains exactly today's (manual tag push), instead of a hard failure.

**Verify**: `actionlint .github/workflows/release-please.yml` → no errors (skip with a note if actionlint is unavailable; then verify by eye that indentation matches the existing `with:` entries — 10 spaces).

### Step 3: Update the stale trigger-model comment

In `publish.yml`'s header comment (lines 1-11), replace the third bullet ("For fully automated publishing…") with the new reality, e.g.:

```
#   - release-please runs with RELEASE_PLEASE_TOKEN (repo secret, fine-grained PAT); tags it
#     pushes therefore trigger this workflow automatically. If the secret is absent or expired,
#     the fallback GITHUB_TOKEN applies and a human must push the tag manually
#     (`git pull --tags && git push origin vX.Y.Z`) or run this workflow via workflow_dispatch.
```

Keep the first two bullets (they correctly describe the trigger mechanics and the manual fallback).

**Verify**: `grep -n "RELEASE_PLEASE_TOKEN" .github/workflows/*.yml` → 2 matches (one in each file: the expression and the comment).

### Step 4: Config-level gate

**Verify**:
- `git diff` shows exactly: one added `token:` line in `release-please.yml`, comment-only changes in `publish.yml`.
- `python -m pytest -q` → all pass (untouched, but run it — cheap insurance).

## Test plan

No unit tests possible for workflow config. The gates are: actionlint (or careful YAML review), the grep in Step 3, and the diff shape in Step 4. End-to-end proof happens at the next real release (Maintenance notes tell the maintainer what to watch).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "secrets.RELEASE_PLEASE_TOKEN || github.token" .github/workflows/release-please.yml` → 1 match.
- [ ] `publish.yml` comment no longer claims automation requires unimplemented configuration (grep from Step 3 → 2 matches total).
- [ ] `git status --short` → only the two workflow files (plus `plans/README.md`).
- [ ] Step 1 either verified via `gh secret list` or explicitly reported as "owner must confirm".
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- Either workflow file differs from the excerpts (drifted).
- You are asked or tempted to store a PyPI API token — the OIDC trusted-publishing setup must not be replaced.
- The operator wants a GitHub App instead of a PAT — that's a valid alternative with different setup; it changes Step 1-2 materially, so report and get direction rather than improvising App wiring.

## Maintenance notes

- **First release after this lands is the real test**: merge the next release PR and confirm, without any manual step, that (a) the `v*` tag exists, (b) the "Publish to PyPI" run triggered from it, (c) the new version is on PyPI. If (b) didn't fire, the secret is missing/expired — the fallback comment in publish.yml documents the manual escape.
- Fine-grained PATs expire; a silent expiry degrades to manual-tag mode (not a hard failure) thanks to the `||` fallback. Calendar-note the renewal.
- The local design doc (`docs/superpowers/specs/2026-06-30-…`, decision D5) should be annotated by the maintainer to note the PAT requirement — it's untracked, so no executor can do it as part of a reviewable change.
