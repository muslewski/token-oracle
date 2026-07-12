# Plan 050 — Launch runbook (Phase 2 "make it spread")

**Status:** DRAFT (advisor-authored; the operator executes the launch — the
advisor does NOT post to any external platform)
**Priority:** P2 — do this only AFTER the credibility + distribution gates below
are green.
**Written against commit:** `e0d8384`

This is a go-to-market playbook, not a code plan. It exists so the launch is
deliberate, honest, and sequenced correctly. The single biggest risk the audit
flagged: **a launch before the numbers are true or the channels are live turns
the first viral screenshot into a liability.** Phase 0 (truth) and Phase 1
(visible) cleared most of that; this gates the rest.

## Positioning (the one thing to own)

> **The truthful token tracker for Claude Code AND Grok** — forecasts when you'll
> hit your limit from local logs, and (uniquely) can verify the number against
> the real site in a browser instead of guessing.

Two wedges no competitor holds together:
1. **Grok usage tracking** — uncontested (ccusage, claude-monitor et al. are
   Claude-only).
2. **Browser-verified real numbers** — directly targets rivals' #1 complaint
   ("the numbers are wrong"). This is the moat *and* the biggest operational
   risk (ToS/DOM breakage) — present it as opt-in and honest, never the headline
   claim that invites a "you're scraping" pile-on.

Do NOT lead with star-chasing language or inflated comparisons. Lead with the
demo GIF and one true sentence.

## Pre-launch gate — ALL must be green before any post

- [ ] **Truth:** Phase 0 merged + pushed (DONE — `7264a71`). No known
      wrong-number bug open.
- [ ] **Visible:** README demo GIF renders on GitHub; `--help` is real;
      first-run guidance lands (Phase 1 DONE + pushed — `e0d8384`).
- [ ] **Distribution live — each verified by the advisor before launch:**
  - [ ] `pipx install token-oracle` / `uvx token-oracle` work (already true on PyPI 0.1.1).
  - [ ] npm package published (`npm publish` — operator) AND `npx token-oracle --help`
        verified working from a clean shell (advisor smoke test).
  - [ ] `curl -fsSL .../install.sh | sh` verified on a clean machine/VM.
  - [ ] README Install section (plan 049) advertises only channels that are live.
- [ ] **First-run sanity on a clean box:** a brand-new user with no config runs
      `token-oracle dash` / `forecast` and sees something honest and helpful (not
      a blank, not a wrong %, not a traceback).
- [ ] **Repo hygiene:** LICENSE present, README badges resolve, CI green, Issues
      enabled, a couple of "good first issue" items filed (invites contribution).
- [ ] **Bus check:** decide the ban/ToS story in advance — one honest paragraph
      ready for "isn't scraping against ToS?" (answer: opt-in, your own logged-in
      session, no fingerprint evasion, log-only by default).

If any box is unchecked, the launch waits. A delayed launch costs nothing; a
launch onto a broken `npx` or a wrong number costs the one first impression.

## Channels — ranked by fit, with messaging

Launch in **waves**, not all at once — fix issues surfaced by wave 1 before
wave 2.

**Wave 1 — the home crowd (highest intent, most forgiving):**
1. **r/ClaudeAI** and the **Anthropic/Claude Code community** (Discord/forum):
   these people literally hit the caps. Lead with the demo GIF + "tracks Grok
   too." Title angle: *"I built a token tracker that also does Grok — and
   verifies the number against the real site."*
2. **X/Twitter** — post the demo GIF (autoplay), one true sentence, the `npx`
   one-liner, repo link. Tag no one; let the GIF do the work. Thread a second
   post with the "how it stays honest" angle (the truthfulness state machine).

**Wave 2 — the broad dev audience (after wave 1 feedback):**
3. **Show HN** (`Show HN: token-oracle – honest Claude Code + Grok token
   forecasts`). HN rewards: works offline, zero-dep, one-liner install, honest
   about limitations. Be present in the thread to answer; do NOT argue. Post
   Tue–Thu morning US time.
4. **r/LocalLLaMA / r/ChatGPTCoding** if the Grok/multi-provider angle resonates
   in wave 1.

**Wave 3 — durable discovery (no timing pressure):**
5. **AUR** package for Arch/Manjaro users (deferred — a `PKGBUILD` sourcing the
   PyPI sdist; low reach, no timing pressure).
6. **awesome-claude / awesome-cli** list PRs.
7. A short **dev.to / blog** post: "How I make a usage tracker that refuses to
   lie" — the truthfulness-first design as the story.

## Assets checklist (have these ready before wave 1)

- [x] Animated demo GIF (`assets/dash-demo.gif`).
- [ ] One static screenshot fallback (some platforms don't autoplay GIFs) —
      optional; extract a frame from the tape if needed.
- [ ] A 2–3 sentence description reused verbatim across channels (consistency).
- [ ] The `npx token-oracle dash` one-liner front and center.

## What NOT to do (hard rules)

- Do not fabricate or round-up usage numbers in any screenshot. Show real or
  clearly-synthetic-labeled data.
- Do not claim "works with every provider" — claim Claude Code + Grok, the two
  that are real.
- Do not oversell the browser verification. "Optional, opt-in, honest when it
  can't verify" — never "always accurate."
- Do not buy stars / ask for stars in a way that violates platform rules.
- Do not launch on a Friday or over a weekend (lower reach, slower issue
  response).

## Honest odds (set expectations)

Per the audit: base realistic outcome with fix + visual + npx + one good launch
is **~1k–3k stars over 6–12 months**; **10k is a genuine stretch** that needs the
Grok wedge to grow, a viral moment, and no ban story. Treat wave 1 as
validation, not the moon shot. The winning bet is durable: *own "the truthful
tracker, for Claude AND Grok."* Everything above only works because Phase 0 made
the numbers true.

## Metrics to watch (first 2 weeks)

- Stars/day slope (not absolute), referral sources (GitHub Insights → Traffic).
- Issue quality: "wrong number" reports are P0 regressions — triage same day.
- npx/pip download counts (npm stats + PyPI `pypistats`) — which channel converts.
- Any ToS/ban report → pause the live-web promotion, keep the offline tool.

## Advisor boundary

The advisor prepares assets, verifies the gates, and drafts copy on request. The
advisor does **not** post to X/HN/Reddit or publish packages — those are the
operator's outward actions. Ask the advisor to smoke-test any channel before you
announce it.
