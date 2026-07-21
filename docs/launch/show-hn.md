# Show HN — token-oracle

**You post this** (your account). Don’t use a bot. Don’t cross-post the same day to five subs.

## When

- **Tue–Thu**, roughly **09:00–11:00 US Eastern** (or EU morning if you prefer EU crowd).
- Avoid Friday / weekend.
- One product only. Don’t link the whole fleet in the title.

## Title (exact)

```
Show HN: token-oracle – time left before your coding-agent usage caps (local logs)
```

Shorter alt if needed:

```
Show HN: token-oracle – offline forecast for coding-agent rate limits
```

## Post body (paste)

```
I kept guessing whether I still had headroom on my coding-agent usage windows.
The hosted dashboards are fine when they work; I wanted something that reads
the logs already on disk and never needs a provider API key.

token-oracle is a small local CLI:

- forecast: rough time left before 5h / weekly-style caps
- dash: terminal UI (past / present / future)
- report: day-by-day spend
- optional statusline snippet for the terminal

Try without installing:

  npx token-oracle forecast
  # or: uvx token-oracle dash

Repo: https://github.com/muslewski/token-oracle
Site: https://oracle.muslewski.com

Honest limits: it's math on local trails, not a bill from the vendor.
If logs are missing or stale, it says so instead of inventing confidence.
Happy to take questions or roast the UX.
```

## Reply kit (first hour)

Stay polite. Short answers.

| Comment type | Reply sketch |
|---|---|
| “How is this different from ccusage / X?” | “Same general problem. I wanted offline-first + multi-window forecast + a statusline path. Overlap is fine; use whatever fits.” |
| “Is it accurate?” | “It’s a forecast from local logs, not the provider’s official meter. When data is thin it degrades honestly.” |
| “Does it phone home?” | “No. Reads local files. Optional live check is opt-in if you wire it.” |
| “Windows?” | “Primary target is macOS/Linux. Happy to note gaps if someone hits them.” |
| “Self-promo / spam” | Don’t argue. One calm sentence: built for my own setup, shared in case it’s useful. Link and leave. |

## Don’t

- Don’t ask for stars.
- Don’t paste five other repos in the first comment.
- Don’t paste AI-sounding essays.
- Don’t correct every pedant on word choice.
- Don’t edit the title after votes start (HN hates that).

## After you post

1. Leave the tab open and answer for ~2–4 hours.
2. If it dies quietly: fine. Don’t repost for **weeks**.
3. If it gains traction: still **one** follow-up post max (e.g. a day later on your blog), not a blast.
