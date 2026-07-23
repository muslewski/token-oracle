---
title: "Server truth"
description: "5h and weekly live server-truth windows"
---

# Server truth

token-oracle reads Claude Code's authoritative rate-limit header. Wire
token-oracle as your Claude Code statusline with one command:

```bash
oracle statusline --install
# (then restart Claude Code)
```

(Or edit `~/.claude/settings.json` by hand:)

```json
{ "statusLine": { "type": "command", "command": "oracle statusline" } }
```

Claude Code then hands `oracle statusline` the `rate_limits` header on each
render; token-oracle captures it (stdlib only, never raises), and `oracle dash`,
`forecast`, etc. show the exact 5h (and weekly) numbers the website shows — no
browser needed. Verify with `oracle doctor` (look for "live 5h truth: ON").

If you already use a custom statusline, compose: e.g. call `oracle statusline`
from your wrapper or pipe its effect.

---
