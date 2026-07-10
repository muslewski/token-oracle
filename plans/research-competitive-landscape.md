# Research: Competitive landscape for token-usage monitors (2026-07-02)

Source: scraped GitHub pages of six open-source tools (star counts as of
2026-07-02). This document backs plans 016–023; each plan inlines what it
needs, this file preserves the full picture so nobody re-scrapes.

## The six tools

| Tool | Stars | Kind | One-liner |
|------|-------|------|-----------|
| ccusage/ccusage | 16.7k | CLI report tool (npx) | daily/weekly/monthly/session/blocks token+cost reports from local Claude logs; multi-agent (Codex, OpenCode, Amp) |
| Maciek-roboblog/Claude-Code-Usage-Monitor ("ccmonitor") | 8.3k | Python Rich TUI | real-time monitor with ML-ish predictions, P90 personal-limit auto-detect, plan presets |
| phuryn/claude-usage | 1.9k | local web dashboard + VS Code ext | "subscribers finally get a progress bar"; SQLite at `~/.claude/usage.db` |
| mm7894215/TokenTracker | 805 | desktop/web | 25 coding tools tracked; LiteLLM pricing for 2 200+ models refreshed daily; per-provider rate-limit reset countdowns |
| VasiHemanth/tokentelemetry | 190 | Next.js+FastAPI dashboard | session traces, tool-call analytics, budgets with 80 %/100 % observational alerts |
| victorGPT/vibeusage | 128 | Node CLI + hosted dashboard | reasoning/cached token lanes, per-repo attribution, heatmaps |

## Concepts adopted into plans (ranked by stars x relevance)

1. **P90 auto-detected personal limit** (ccmonitor: `custom` plan = 90th
   percentile of your own history; "95 % confidence" limit discovery) → plan 023.
2. **Cost-mode tri-state `auto` / `calculate` / `display`** with an offline
   bundled price snapshot plus a user override file (ccusage; TokenTracker
   confirms offline snapshot + daily refresh pattern) → plan 017. We reuse
   ccusage's exact mode names for familiarity.
3. **Plan presets with concrete 5h-window numbers** (ccmonitor):
   `pro ≈ 19 000`, `max5 ≈ 88 000`, `max20 ≈ 220 000` tokens → plan 017.
4. **5-hour billing blocks as a first-class time slice with live projection**
   (ccusage `blocks --live`) — already token-oracle's core model; the tabbed
   TUI surfaces it better → plans 018/020.
5. **Decoupled data-refresh vs render cadence** (ccmonitor `--refresh-rate`
   vs `--refresh-per-second`) → plan 018 (engine re-aggregates each 30 s;
   frame renders ~4×/s for smooth countdowns).
6. **Width-responsive tables that auto-collapse below ~100 columns**, plus an
   explicit compact mode "perfect for screenshots" (ccusage) → plans 018/019.
7. **Observational (never blocking) threshold warnings at 80 %/100 %**
   (tokentelemetry budgets; ccmonitor warnings) → plan 020.
8. **Machine-readable export carrying provenance/confidence** (ccmonitor
   `--once --output json`, `--write-state`) — token-oracle already has
   `forecast --json` + snapshot; plan 019 adds `report --json`.
9. **Past-tab depth: per-model daily tables with cache lanes, activity
   heat strip, per-project attribution** (ccusage daily view; TokenTracker
   heatmap; vibeusage token lanes) → plans 016 (data), 019 (view).
10. **Sticky config that restores last-used preferences** (ccmonitor
    `~/.claude-monitor/last_used.json`) → plan 021 takes the lighter form:
    an interactive wizard writing a durable config once.

## Whitespace we exploit

None of the six ships an interactive arrow-key TUI with distinct
past/present/future views: ccmonitor is one live view behind mode flags,
ccusage is a static report CLI, the rest are web/desktop apps. A tabbed,
prediction-first terminal Oracle (past = ledger, present = live burn,
future = forecast) is an open niche. token-oracle's existing 168-bucket
burn profile and blend projection already out-model most of them; the gap
is presentation, cost, and onboarding — which is what plans 016–023 close.

## Ideas considered and NOT adopted (with reasons)

- **Rich/Textual dependency** (ccmonitor uses Rich): rejected — the repo's
  documented stdlib-only stance (AGENTS.md:14, `dependencies = []`,
  colors.py docstring). Hand-rolled ANSI already exists and suffices.
- **Auto light/dark theme detection** (ccmonitor): deferred — `COLORFGBG`
  heuristics are unreliable across terminals; NO_COLOR/FORCE_COLOR gating
  already exists.
- **Runtime LiteLLM price fetch** (ccusage `calculate` mode, TokenTracker):
  deferred — would be the first network call in the codebase; offline
  snapshot + user overrides covers the need. Revisit if model churn makes
  the snapshot rot faster than releases.
- **MCP server / statusline beta parity** (ccusage): deferred — snapshot
  JSON + existing statusline adapter serve the same consumers; an MCP
  server is a separate product decision.
- **Cloud sync, leaderboards, badges** (vibeusage, TokenTracker): rejected —
  token-oracle is local-first/privacy-first; nothing leaves the machine.
- **Web dashboard / VS Code extension** (claude-usage, tokentelemetry):
  rejected for this repo — terminal is the product; ADAPTERS.md invites
  external consumers to build those on `forecast.json`.
- **Session traces / tool-call analytics** (tokentelemetry): out of scope —
  that is agentic-sage's territory (session awareness); see plan 022's
  division-of-labor note.
