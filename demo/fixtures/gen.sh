#!/usr/bin/env bash
# Fabricate a dramatic near-limit token-oracle world under the demo sandbox.
# Invoked by demo_sandbox; relies on DEMO_ANCHOR_EPOCH + XDG_* + HOME exports.
# Fake-only: atlas / beacon / lumen fixture names; no keys, tokens, or real paths.
set -euo pipefail

: "${DEMO_ANCHOR_EPOCH:?DEMO_ANCHOR_EPOCH must be set by demo_sandbox}"
: "${XDG_DATA_HOME:?}"
: "${XDG_CONFIG_HOME:?}"
: "${HOME:?}"

DATA="$XDG_DATA_HOME/token-oracle"
CFG_DIR="$XDG_CONFIG_HOME/token-oracle"
mkdir -p "$DATA" "$CFG_DIR"

# ---------------------------------------------------------------------------
# Usage history + ratelimits + live snapshot (anchor-relative timestamps)
# ---------------------------------------------------------------------------
python3 - "$DEMO_ANCHOR_EPOCH" "$DATA" <<'PY'
import json
import os
import sys

now = float(sys.argv[1])
data_dir = sys.argv[2]
os.makedirs(data_dir, exist_ok=True)

# --- atlas (claude profile): heavy 5h burn ~85% of 220k, weekly ~90% of 8M ---
atlas = []
# 14-day past ledger (daytime only; keep ≥7h away so the rolling 5h window
# does not re-anchor onto an expired day-1 evening event).
for day in range(14, 0, -1):
    model = "lumen-code" if day % 3 == 0 else "atlas-opus"
    for h in (10, 12, 14, 16):
        ts = now - day * 86400 + h * 3600
        if ts > now - 7 * 3600:
            continue
        # denser weekly mass so the current 7d window sits near the cap (~7.2M/8M)
        tok = 230000 + (14 - day) * 2000 + h * 250
        atlas.append(
            [ts, tok, model, tok // 2, tok // 3, tok // 6, tok // 4, round(tok * 1.5e-5, 4)]
        )

# Continuous 5h session cluster (first event ≈4h ago so reset is still ahead)
t0 = now - 4.0 * 3600
used_5h = 0
i = 0
target_5h = 168000  # ~76% used; projection near but under the cap
while used_5h < target_5h and t0 + i * 80 < now - 20:
    tok = 2200 + (i % 6) * 240
    atlas.append(
        [
            t0 + i * 80,
            tok,
            "atlas-opus",
            tok // 2,
            tok // 3,
            tok // 6,
            tok // 5,
            round(tok * 1.5e-5, 4),
        ]
    )
    used_5h += tok
    i += 1
# final recent pulses (age near zero; stay under the 220k cap)
for j, tok in enumerate((2800, 2500, 3000, 2200)):
    if used_5h + tok > 185000:
        break
    atlas.append(
        [
            now - 90 + j * 20,
            tok,
            "atlas-opus",
            tok // 2,
            tok // 3,
            tok // 6,
            0,
            round(tok * 1.5e-5, 4),
        ]
    )
    used_5h += tok
atlas.sort(key=lambda e: e[0])

# --- beacon (grok profile): weekly near limit ~88% of 10M (under cap) ---
beacon = []
for day in range(6, 0, -1):
    for h in (9, 11, 13, 15, 17, 19):
        ts = now - day * 86400 + h * 3600
        if ts > now - 600:
            continue
        tok = 200000 + day * 2500
        beacon.append([ts, tok, "beacon-build", tok, 0, 0, 0, None])
for j, tok in enumerate((72000, 68000, 80000, 65000, 70000)):
    beacon.append([now - 800 + j * 140, tok, "beacon-build", tok, 0, 0, 0, None])
beacon.sort(key=lambda e: e[0])

with open(os.path.join(data_dir, "atlas-events.json"), "w", encoding="utf-8") as fh:
    json.dump(atlas, fh)
with open(os.path.join(data_dir, "beacon-events.json"), "w", encoding="utf-8") as fh:
    json.dump(beacon, fh)

# Rate-limit header self-ingest (statusline / 5h truth) — near limit, not exceeded.
# Installed oracle (main) re-bases 5h used from this via apply_live_fills.
rl = {
    "five_hour": {
        "used_percentage": 86.0,
        "resets_at": now + 48 * 60,
        "observed_at": now - 25,
    },
    "seven_day": {
        "used_percentage": 90.0,
        "resets_at": now + 2.4 * 86400,
        "observed_at": now - 25,
    },
}
with open(os.path.join(data_dir, "ratelimits.json"), "w", encoding="utf-8") as fh:
    json.dump(rl, fh)

# Live web overlay snapshot (dash Present tab) — staged, not probed
live = {
    "version": 1,
    "written_at": now - 18,
    "providers": {
        "claude": {
            "provider": "claude",
            "state": "ok",
            "fetched_at": now - 18,
            "error": None,
            "note": "demo fixture atlas",
            "readings": [
                {
                    "provider": "claude",
                    "metric": "five_hour_pct",
                    "value": 86.0,
                    "confidence": "high",
                    "extractor": "fixture.atlas",
                    "evidence": "atlas session near 5h cap",
                    "fetched_at": now - 18,
                    "model": None,
                },
                {
                    "provider": "claude",
                    "metric": "weekly_pct",
                    "value": 90.0,
                    "confidence": "high",
                    "extractor": "fixture.atlas",
                    "evidence": "atlas weekly near cap",
                    "fetched_at": now - 18,
                    "model": None,
                },
                {
                    "provider": "claude",
                    "metric": "reset_at",
                    "value": now + 48 * 60,
                    "confidence": "medium",
                    "extractor": "fixture.atlas",
                    "evidence": "Resets in 48 min",
                    "fetched_at": now - 18,
                    "model": None,
                },
            ],
        },
        "grok": {
            "provider": "grok",
            "state": "ok",
            "fetched_at": now - 22,
            "error": None,
            "note": "demo fixture beacon",
            "readings": [
                {
                    "provider": "grok",
                    "metric": "weekly_pct",
                    "value": 78.0,
                    "confidence": "high",
                    "extractor": "fixture.beacon",
                    "evidence": "beacon weekly usage",
                    "fetched_at": now - 22,
                    "model": None,
                }
            ],
        },
    },
}
with open(os.path.join(data_dir, "live.json"), "w", encoding="utf-8") as fh:
    json.dump(live, fh)

print(
    f"gen.sh: atlas={len(atlas)} events (~{used_5h} tok/5h), "
    f"beacon={len(beacon)} events",
    file=sys.stderr,
)
PY

# Config uses absolute sandbox paths (HOME ≠ XDG_DATA_HOME under demo_sandbox).
cat >"$CFG_DIR/config.json" <<EOF
{
  "profiles": {
    "claude": {
      "source": "generic",
      "source_opts": {
        "events_path": "$DATA/atlas-events.json"
      },
      "windows": [
        {"name": "5h", "cap": 220000, "period_secs": 18000},
        {"name": "weekly", "cap": 8000000, "period_secs": 604800}
      ]
    },
    "grok": {
      "source": "generic",
      "source_opts": {
        "events_path": "$DATA/beacon-events.json"
      },
      "windows": [
        {"name": "weekly", "cap": 10000000, "period_secs": 604800}
      ]
    }
  },
  "cost_mode": "auto"
}
EOF

# ---------------------------------------------------------------------------
# Stub the dash live-probe worker so it never launches a real browser.
# dash looks for ~/.local/share/token-oracle/venv/bin/oracle via expanduser(~)
# (HOME-relative, not XDG_DATA_HOME).
# ---------------------------------------------------------------------------
STUB_DIR="$HOME/.local/share/token-oracle/venv/bin"
mkdir -p "$STUB_DIR"
cat >"$STUB_DIR/oracle" <<'STUB'
#!/usr/bin/env bash
# Demo-only stub: live-probe returns the staged live.json instantly.
set -euo pipefail
if [ "${1:-}" = "live-probe" ]; then
  live="${XDG_DATA_HOME:-$HOME/.local/share}/token-oracle/live.json"
  if [ -f "$live" ]; then
    cat "$live"
    exit 0
  fi
  echo '{"version":1,"written_at":0,"providers":{}}'
  exit 0
fi
# Fall through to real oracle on PATH for any other subcommand.
exec command oracle "$@"
STUB
chmod +x "$STUB_DIR/oracle"

# Pre-warm the aggregation cache so the first dash frame is contentful.
export TOKEN_ORACLE_SKIP_BOOTSTRAP=1
# Prefer real oracle; ignore failures (recording still works off events scan).
if command -v oracle >/dev/null 2>&1; then
  oracle forecast >/dev/null 2>&1 || true
fi
