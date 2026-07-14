# Plan 013: Third-party source adapters discoverable via entry points (make the CLI extension story real)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/sources/base.py tests/ ADAPTERS.md`
> Plans 001–007 landed; ADAPTERS.md and tests/ changes through `ada32e9` are
> expected and reflected below (`base.py` itself is unchanged — excerpt
> verified byte-identical at `ada32e9`, 2026-07-02). On changes after
> `ada32e9`, compare the `base.py` excerpt against live code; on a mismatch,
> treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: plans/002-docs-drift-sweep.md — DONE (merged at `429d53a`); dependency satisfied
- **Category**: direction
- **Planned at**: commit `d2b4d32`, 2026-07-01; excerpts verified current at `ada32e9`, 2026-07-02
- **Executed**: 2026-07-14 — DONE. Lazy entry-point load; available() lists without import; 4 tests; ADAPTERS.md.

## Why this matters

token-oracle's pitch is "provider-agnostic", and ADAPTERS.md documents how to write a third-party source adapter. But the registration mechanism is an import side effect (`@register("name")` runs when the module is imported), and ADAPTERS.md's own instruction — "import it in your project's entry point … before calling `oracle forecast`" — only works when token-oracle is used **as a library**. The primary interface is the CLI, and a CLI user cannot inject an import into `token_oracle.cli.main`. So the documented extension story is unusable for the main use case: today you cannot `pip install token-oracle-codex` and set `"source": "codex"`. Python packaging solved this decades ago: entry points. One `importlib.metadata` lookup in the registry makes third-party adapters installable, discoverable, and listable by `doctor` — the architecture is already one interface away from a real plugin system.

## Current state

- `token_oracle/sources/base.py` — the whole registry, 22 lines (unchanged since `d2b4d32`, verified at `ada32e9`):

```python
"""Source adapter registry. A source turns provider data into neutral
(timestamp, tokens) events, owning its own incremental file/cache state."""

_REGISTRY: dict[str, type] = {}


def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls

    return deco


def available():
    return sorted(_REGISTRY)


def get_source(name, opts=None):
    if name not in _REGISTRY:
        raise KeyError(f"unknown source: {name!r}; available: {available()}")
    return _REGISTRY[name](opts or {})
```

- Built-ins register via `token_oracle/sources/__init__.py` importing `claude_code` and `generic` (comment: "register on import").
- Callers of `get_source`/`available`: `token_oracle/core/engine.py:15` (inside a never-raises try), `token_oracle/cli/main.py` (doctor's availability row; after Plan 003, also the data probe).
- `pyproject.toml` — `requires-python = ">=3.10"`; `importlib.metadata.entry_points(group=...)` keyword selection is available from 3.10. No pyproject change is needed in THIS repo (entry points are declared by the *third-party* package).
- ADAPTERS.md "Registration" section (lines ~55-62 post-Plan-002) currently teaches the import-before-use workaround — to be replaced.
- Test conventions: flat pytest functions; `monkeypatch` is available (used in `tests/test_config.py:16`, `test_paths_honor_xdg`); no mocking libraries.

Third-party packaging shape this plan enables (goes into ADAPTERS.md):

```toml
# pyproject.toml of e.g. token-oracle-myprovider
[project.entry-points."token_oracle.sources"]
my_provider = "my_pkg.my_source"
```

where importing `my_pkg.my_source` executes `@register("my_provider")`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Focused | `python -m pytest tests/test_sources_claude.py tests/test_sources_generic.py -q` | all pass |
| Lint/type | `ruff check token_oracle/ && ruff format --check token_oracle/ && mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/sources/base.py`
- `tests/test_sources_generic.py` (add the discovery tests here — registry-level tests live beside the generic-source ones) — if the file's existing content makes that awkward, creating `tests/test_sources_base.py` instead is acceptable; say which you chose.
- `ADAPTERS.md` (Registration section)

**Out of scope** (do NOT touch):
- `token_oracle/sources/claude_code.py`, `generic.py` — built-ins keep registering via package import; entry points are additive.
- `pyproject.toml` of this repo — this package declares no entry points for its own built-ins (import registration is simpler and avoids a needless metadata lookup).
- `engine.py`, `cli/main.py` — they consume the registry unchanged.

## Git workflow

- Branch: `advisor/013-entry-point-sources`.
- Conventional commit, e.g.: `feat(sources): discover third-party adapters via token_oracle.sources entry points`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add lazy entry-point loading to the registry

Extend `base.py` (keep the docstring's design-note style — add one sentence about entry points):

```python
_EP_GROUP = "token_oracle.sources"


def _entry_points():
    try:
        from importlib.metadata import entry_points

        return list(entry_points(group=_EP_GROUP))
    except Exception:
        return []


def _load_entry_point(name):
    """Import the entry point matching name, if any; it registers on import."""
    for ep in _entry_points():
        if ep.name == name and name not in _REGISTRY:
            try:
                ep.load()
            except Exception:
                pass
            return


def available():
    names = set(_REGISTRY)
    names.update(ep.name for ep in _entry_points())
    return sorted(names)


def get_source(name, opts=None):
    if name not in _REGISTRY:
        _load_entry_point(name)
    if name not in _REGISTRY:
        raise KeyError(f"unknown source: {name!r}; available: {available()}")
    return _REGISTRY[name](opts or {})
```

Design decisions embedded here (keep them): lazy load — only the *requested* entry point is imported, never all of them (a broken third-party package must not break unrelated invocations); `available()` lists entry-point names *without* importing them (doctor stays cheap and safe); a failing `ep.load()` degrades to the normal unknown-source `KeyError` whose message lists what IS available.

**Verify**: `python -m pytest -q` → all existing tests pass (built-in behavior unchanged).

### Step 2: Tests

Fake entry points via `monkeypatch` — patch `importlib.metadata.entry_points` (the function is imported *inside* `_entry_points`, so patching the module attribute works):

```python
class _FakeEp:
    name = "fake_src"

    @staticmethod
    def load():
        from token_oracle.sources.base import register

        @register("fake_src")
        class FakeSrc:
            def __init__(self, opts):
                self.opts = opts

            def scan(self, files_state, now, window):
                return files_state, []

        return FakeSrc
```

1. `test_entry_point_source_loads_on_demand(monkeypatch)` — patch `entry_points` to return `[_FakeEp]` for the group; `get_source("fake_src", {})` returns an instance; `"fake_src" in available()`. Clean up `_REGISTRY.pop("fake_src", None)` at the end (module-global state).
2. `test_available_lists_entry_points_without_loading(monkeypatch)` — a fake ep whose `load` raises `AssertionError("must not load")`; `available()` includes its name and does not raise.
3. `test_broken_entry_point_falls_through_to_keyerror(monkeypatch)` — fake ep whose `load()` raises `ImportError`; `get_source("broken")` raises `KeyError` mentioning `broken`.
4. `test_unknown_source_still_keyerror` — no patching; `get_source("nope-not-real")` raises `KeyError` (pins that the metadata lookup didn't change the error contract — `tests/test_engine.py::test_forecast_empty_on_bad_source` also guards this end to end).

Mind the patch target: `monkeypatch.setattr("importlib.metadata.entry_points", lambda **kw: [_FakeEp])` and assert the `group` kwarg if you want extra rigor.

**Verify**: `python -m pytest tests/ -q -k "entry_point or unknown_source"` → 4 pass; full suite green.

### Step 3: Rewrite the ADAPTERS.md Registration section

Replace the "import it in your project's entry point (or in a `conftest.py` …)" paragraph with the entry-points recipe: the `[project.entry-points."token_oracle.sources"]` pyproject snippet above, one sentence on semantics (the value is a module path; importing it must execute `@register("<name>")` with the same name as the entry point), and one sentence noting the old library-mode option (import before use) still works. Keep the surrounding Source-interface docs untouched.

**Verify**: `grep -n "entry-points" ADAPTERS.md` → ≥ 1 match; `grep -n "conftest" ADAPTERS.md` → 0 matches.

### Step 4: Full gates

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

The four tests in Step 2, placed in `tests/test_sources_generic.py` (or `tests/test_sources_base.py` — state your choice). Pattern: `tests/test_config.py::test_paths_honor_xdg` for monkeypatch style. End-to-end (real installed third-party package) is Plan 014's spike territory — not required here.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 with 4 new registry tests.
- [ ] `grep -n "entry_points" token_oracle/sources/base.py` → ≥ 2 matches (lookup + group constant usage).
- [ ] `python -c "from token_oracle.sources.base import available; print(available())"` → prints at least `['claude_code', 'generic']` and exits 0 (no metadata crash in a clean env).
- [ ] ADAPTERS.md documents the entry-point group `token_oracle.sources`.
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] `git status --short` → only in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `base.py` differs from the 22-line excerpt (drifted).
- You find yourself declaring entry points for the built-in sources in this repo's pyproject — decided against (out of scope); report if you believe it's required.
- The monkeypatch approach fails because `entry_points` resolution behaves differently on the local Python version — report the version and error; do not switch to installing real fixture packages.

## Maintenance notes

- Name collisions: a third-party entry point named `claude_code` never wins — `get_source` checks `_REGISTRY` first and `_load_entry_point` skips names already registered. Document-by-test if it ever matters.
- Doctor (Plan 003) now lists entry-point sources in its availability row automatically; a *listed-but-unloadable* source only surfaces as an error when selected — acceptable, revisit if support burden appears.
- Plan 014 (second-provider spike) builds directly on this: its prototype package is the first real consumer of the group.
- Reviewer: check the lazy-load property (no `ep.load()` outside a name match) — eager loading would make any broken plugin break every invocation.
