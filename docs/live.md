---
title: "Live data"
description: "Optional browser-verified live numbers"
---

# Live data

By default token-oracle forecasts entirely offline from local logs. It can also
read your **real** current usage directly from `grok.com` and `claude.ai` using a
headless/headed browser session you log into once. This is opt-in and honest: if
it cannot verify a number, it reports the state (`unavailable`, `needs_login`,
`rate_data_only`) rather than guessing.

### Enable it

```bash
oracle live on          # turn on real (headed) live probing; writes it to your config
oracle live-setup       # one-time browser login to grok.com / claude.ai
oracle dash             # the dashboard now shows live, browser-verified numbers
oracle live status      # check whether it's on and what was last probed
oracle live off         # back to offline-only
```

`oracle live-probe` runs a single probe now and prints what it found
(`--provider grok|claude|all`, `--json` for machine output).

### Xvfb (for machines without a graphical display)

Headed probing needs a display. On a normal desktop it uses your existing one.
On a server / container / SSH session with no `$DISPLAY`, install **Xvfb** (a
virtual display) and token-oracle will use it automatically:

```bash
# Arch / Manjaro
sudo pacman -S xorg-server-xvfb
# Debian / Ubuntu
sudo apt install xvfb
```

Without a display or Xvfb, live probing honestly reports `unavailable` — it
never fabricates a number.

### Notes

- **No fingerprint evasion.** token-oracle drives a real browser with your own
  logged-in session; it does not spoof fingerprints or solve CAPTCHAs. If a site
  serves a bot challenge it reports that state and suggests
  `TOKEN_ORACLE_LIVE_HEADED=1 oracle live-probe`.
- Grok weekly usage is on the `?_s=usage` modal (`https://grok.com/?_s=usage`),
  not `/settings/usage` (that route bounces to chat). When only the 2h rate
  window is available the state is `rate_data_only` — that is expected until a
  headed probe captures the modal.
- Live numbers are display-only on the dash overlay path; they never rewrite
  offline projection math in the pure engine. (Statusline/forecast may prefer
  self-ingested Claude rate-limit headers for the 5h window — see below.)

---
