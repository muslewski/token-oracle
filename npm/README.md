# token-oracle (npx shim)

`npx token-oracle` / `bunx token-oracle` — run the
[token-oracle](https://github.com/muslewski/token-oracle) Python CLI without a
manual install.

```bash
npx token-oracle forecast     # time left before your next cap
npx token-oracle dash         # full-screen live dashboard
bunx token-oracle doctor      # check config, data sources, live status
```

This package is a thin launcher. It runs the real tool through `uvx` or
`pipx` (or an already-installed copy), so you need one of:

- **uv** (recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **pipx**: `pipx install token-oracle`
- or Python ≥ 3.10 with `pip install token-oracle`

It runs the **latest** published PyPI release. Full docs, screenshots, and the
offline/live details live in the
[main repository](https://github.com/muslewski/token-oracle).
