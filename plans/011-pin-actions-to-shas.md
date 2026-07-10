# Plan 011: Pin GitHub Actions to commit SHAs (optional supply-chain hardening)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- .github/workflows/`
> Plan 009 legitimately adds a `token:` line to `release-please.yml` and edits
> `publish.yml` comments. On other workflow mismatches vs. the excerpts below,
> treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW (a wrong SHA fails CI loudly; nothing silent)
- **Depends on**: none (execute after Plan 009 to avoid a trivial merge conflict in the same files)
- **Category**: security
- **Planned at**: commit `d2b4d32`, 2026-07-01
- **Advisor note**: the audit's verdict was "not worth doing *now*" — dependabot already watches these actions weekly and the repo has no secrets an action could exfiltrate beyond the OIDC publish credential. The operator opted to plan it anyway. Treat as low-urgency hardening.

## Why this matters

Workflow steps reference actions by mutable tags (`@v4`, `@v5`, `@release/v1`). A compromised or force-pushed tag in an upstream action repo executes attacker-controlled code in this repo's CI — and in `publish.yml` that code runs inside the `pypi` environment with an OIDC `id-token: write` grant, i.e. the ability to publish to PyPI as this project. Pinning to full commit SHAs makes the referenced code immutable; dependabot understands SHA pins (with the trailing version comment) and keeps proposing updates, so freshness is not lost.

## Current state

All `uses:` references at `d2b4d32`:

- `.github/workflows/ci.yml` — `actions/checkout@v4` (3×, lines 17, 30, 44-ish), `actions/setup-python@v5` (3×).
- `.github/workflows/publish.yml` — `actions/checkout@v4`, `actions/setup-python@v5`, `pypa/gh-action-pypi-publish@release/v1` (a **branch** ref, not a tag).
- `.github/workflows/release-please.yml` — `googleapis/release-please-action@v4`.

Example of the current shape (`publish.yml:32-38`):

```yaml
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- `.github/dependabot.yml` already has a weekly `github-actions` ecosystem entry — it updates SHA-pinned actions and their version comments automatically.

Target shape: `uses: actions/checkout@<40-char-sha> # v4`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Resolve a tag to a commit | `git ls-remote https://github.com/actions/checkout refs/tags/v4 "refs/tags/v4^{}"` | 1–2 lines; the `^{}` (peeled) line's SHA is the **commit**; if no `^{}` line appears, the plain line already is the commit |
| Resolve the publish branch | `git ls-remote https://github.com/pypa/gh-action-pypi-publish refs/heads/release/v1` | one line; that SHA is the commit |
| Lint workflows | `actionlint` (if installed) | no errors |
| Repo tests | `python -m pytest -q` | all pass (untouched — insurance) |

## Scope

**In scope** (the only files you should modify):
- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/release-please.yml`

**Out of scope** (do NOT touch):
- `.github/dependabot.yml` — already correct.
- Any workflow logic, triggers, permissions — this plan changes only `uses:` refs.

## Git workflow

- Branch: `advisor/011-pin-action-shas`.
- Conventional commit, e.g.: `ci: pin actions to commit SHAs (supply-chain hardening)`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Resolve every ref to a commit SHA

For each of: `actions/checkout` tag `v4`, `actions/setup-python` tag `v5`, `googleapis/release-please-action` tag `v4`, `pypa/gh-action-pypi-publish` branch `release/v1` — run the `git ls-remote` commands from the table and record the peeled commit SHA. Tags like `v4` in these repos are annotated: the `refs/tags/v4^{}` line is the commit; use THAT, never the tag-object SHA.

**Verify**: four 40-hex-char SHAs recorded; each command returned at least one line (network reachable).

### Step 2: Rewrite the `uses:` lines

Replace every occurrence, appending the human-readable comment dependabot maintains:

```yaml
      - uses: actions/checkout@<sha-from-step-1> # v4
```

…and for the publish action: `pypa/gh-action-pypi-publish@<sha> # release/v1`. Apply in all three workflow files (8 `uses:` lines total: 3+3 in ci.yml, 3 in publish.yml, 1 in release-please.yml — recount with the grep below first; Plan 009 didn't add any).

**Verify**: `grep -rn "uses:" .github/workflows/ | grep -vE "@[0-9a-f]{40} #"` → 0 matches.

### Step 3: Gates

**Verify**:
- `actionlint` → no errors (skip with a note if unavailable).
- `git diff` → only `uses:` lines changed, nothing else.
- After the change is pushed to a branch/PR by the operator, CI must run green — a red "unable to resolve action" means a wrong SHA (tag-object instead of commit); fix from Step 1's peeled values.

## Test plan

No unit tests — CI itself is the test. The Step 2 grep is the machine gate; the first CI run on the branch is the behavioral gate (operator-triggered).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn "uses:" .github/workflows/ | grep -vE "@[0-9a-f]{40} #"` → 0 matches.
- [ ] Every pinned line carries a `# <original-ref>` comment.
- [ ] `git status --short` → only the three workflow files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated (note: full verification pends the next CI run).

## STOP conditions

Stop and report back (do not improvise) if:

- No network access to resolve SHAs (`git ls-remote` fails) — do not copy SHAs from memory or training data; they must come from the live remote.
- A `uses:` line exists that this plan doesn't list (workflow drift) — pin it too only if its repo/ref resolves cleanly; otherwise report.

## Maintenance notes

- Dependabot PRs will now bump SHAs and comments together; review them as usual.
- If a future contributor adds an action by tag, CI won't catch it — consider adding `actionlint` or a simple grep check to CI later (deferred; not planned).
- Reviewer: verify each SHA against the upstream repo's tag (one `git ls-remote` per action) rather than trusting the PR text.
