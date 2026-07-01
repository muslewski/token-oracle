# AGENTS

Deterministic runbook for a coding agent setting up and verifying token-oracle.
Follow the steps in order; each includes the exact command and expected output.

---

## Step 1 — Install in development mode

```bash
pip install -e ".[dev]"
```

Expected: pip resolves and installs (no dependencies beyond stdlib; only
`pytest>=7` is pulled in for the `dev` extra). The `oracle` entry point is
registered.

---

## Step 2 — Verify the test suite

```bash
python -m pytest -q
```

Expected output (last line):

```
71 passed in 0.XXs
```

The exact count grows as tests are added; any failure or error means stop.
If any tests fail, stop and report the failure. Do not proceed with further
steps or doc changes until the suite is green.

---

## Step 3 — Verify the CLI entry point

```bash
oracle doctor
```

Expected output (paths will differ per machine; run with `NO_COLOR=1` for
plain output, otherwise ANSI color codes will be present). This example is
from a fresh machine with no config file yet, but with prior Claude Code
usage on disk:

```
🔮 oracle doctor
  ✓ config   — /home/<user>/.config/token-oracle/config.json (missing — using built-in max20 preset)
  ✓ source   — claude_code (available: claude_code, generic)
  ✓ data     — 182 files, 32258 events, last 57s ago
  ✓ cache    — /home/<user>/.local/share/token-oracle/cache.json (updated 12m ago)
  ✓ windows  — 2 → ['5h', 'weekly']
  5 ok · 0 need attention
```

The `source` row must show `claude_code` as the active source and list at
least `claude_code, generic` as available. The `data` row must show a
non-zero event count if Claude Code has been used recently; `no events found`
with ✗ is expected on a fresh machine with no usage history yet — that is not
a failure, just an empty history. The `windows` row must show two windows
named `5h` and `weekly` (the built-in `max20` preset). Each row is badged `✓`
(good) or `✗` (needs attention); the footer line tallies the count, and the
process exit code is `0` only when every row is `✓`.

---

## Step 4 — Configure windows (or accept the default)

The default `max20` preset works for Claude Pro / max20 subscriptions with no
config file needed. To customise, write `~/.config/token-oracle/config.json`:

```bash
mkdir -p ~/.config/token-oracle
cat > ~/.config/token-oracle/config.json << 'EOF'
{
  "source": "claude_code",
  "windows": [
    {"name": "5h",     "cap": 220000,  "period_secs": 18000},
    {"name": "weekly", "cap": 8000000, "period_secs": 604800}
  ]
}
EOF
```

Re-run `oracle doctor` to confirm the config file is now loaded:

```
🔮 oracle doctor
  ✓ config   — /home/<user>/.config/token-oracle/config.json
  ✓ source   — claude_code (available: claude_code, generic)
  ✓ data     — 182 files, 32263 events, last 6s ago
  ✓ cache    — /home/<user>/.local/share/token-oracle/cache.json (updated 13m ago)
  ✓ windows  — 2 → ['5h', 'weekly']
  5 ok · 0 need attention
```

---

## Step 5 — Run a forecast

```bash
oracle forecast
```

Expected: a human-readable status line, or `idle` if no Claude Code usage has
been recorded recently. Example non-idle output:

```
🕐 3:42 45k/220k →21%
```

ANSI color codes are present in the actual output unless `NO_COLOR=1` is set.

To get machine-readable output:

```bash
oracle forecast --json
```

Expected: a JSON object with `schema`, `generated_at`, and `windows` array. Example:

```json
{
  "schema": 1,
  "generated_at": 1751234567.89,
  "windows": [
    {
      "window": "5h",
      "used": 45200,
      "cap": 220000,
      "projected_pct": 21.0,
      "eta_to_cap_secs": null,
      "reset_in_secs": 13320.0,
      "idle": false,
      "confidence": 1.0
    }
  ]
}
```

---

## Step 6 — Write a snapshot

```bash
oracle snapshot
```

Expected: prints the absolute path where `forecast.json` was written, e.g.:

```
/home/<user>/.local/share/token-oracle/forecast.json
```

Verify the file exists:

```bash
python -c "import json; print(json.load(open('/home/<user>/.local/share/token-oracle/forecast.json'))['schema'])"
```

Expected: `1`

---

## Step 7 — (Optional) Wire agentic-sage

If [agentic-sage](https://github.com/muslewski/agentic-sage) is installed, add
`tokenForecastPath` to its config:

```json
{
  "tokenForecastPath": "~/.local/share/token-oracle/forecast.json"
}
```

Then run `oracle snapshot` before each sage session (or on a cron) to keep the
forecast file fresh.

---

## Verification checklist

- [ ] `pip install -e ".[dev]"` exits 0
- [ ] `python -m pytest -q` reports all tests passing (count grows over time)
- [ ] `oracle doctor` shows a `source` row for `claude_code`, a `data` row (non-zero
      events if Claude Code has been used recently), and a `windows` row for `2`
- [ ] `oracle forecast` returns a line or `idle` (no stack trace)
- [ ] `oracle forecast --json` returns valid JSON with `"schema": 1`
- [ ] `oracle snapshot` prints a path and the file exists
