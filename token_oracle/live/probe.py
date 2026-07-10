"""The ONLY place that actively probes providers. Everything else reads
live.json. Progress goes to the callback (stderr by default) so no consumer
surface can be polluted by browser chatter.
"""

import os
import time

from .contract import STATE_ERROR, ProviderLive, provider_live_to_dict
from .store import save_snapshot
from .web import fetch_claude_live_usage, fetch_grok_live_usage


def run_probe(
    providers=("grok", "claude"), headless: bool = True, progress=None, path: str | None = None
) -> dict:
    """Fetch each provider, build {name: ProviderLive}, save_snapshot, and
    return the snapshot dict. Per-provider exceptions become
    ProviderLive(state=STATE_ERROR, error=str(e)[:200]) — one provider
    failing must not lose the other's data.
    """
    if os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1":
        headless = False
    if isinstance(providers, str):
        if providers.lower() == "all":
            prov_list = ["grok", "claude"]
        else:
            prov_list = [providers.lower()]
    else:
        prov_list = [p.lower() for p in providers]

    snap_providers: dict[str, ProviderLive] = {}

    for name in prov_list:
        if name not in ("grok", "claude"):
            continue
        if progress:
            try:
                progress(f"   • probing {name} ...")
            except Exception:
                pass
        try:
            if name == "grok":
                pl = fetch_grok_live_usage(headless=headless, progress=progress)
            else:
                pl = fetch_claude_live_usage(headless=headless, progress=progress)

            if isinstance(pl, ProviderLive):
                snap_providers[name] = pl
            else:
                # None or unexpected (e.g. no playwright) → treat as needs_login honest state
                snap_providers[name] = ProviderLive(
                    provider=name,
                    state="needs_login",
                    readings=[],
                    fetched_at=time.time(),
                    error=None,
                    note="no playwright data",
                )
            if progress:
                try:
                    st = snap_providers[name].state if name in snap_providers else "?"
                    progress(f"   • {name} → {st}")
                except Exception:
                    pass
        except Exception as e:
            snap_providers[name] = ProviderLive(
                provider=name,
                state=STATE_ERROR,
                readings=[],
                fetched_at=time.time(),
                error=str(e)[:200],
            )

    # Always attempt the atomic write; return the dict regardless of I/O outcome.
    save_snapshot(snap_providers, path)

    snap_dict = {
        "version": 1,
        "written_at": time.time(),
        "providers": {
            k: provider_live_to_dict(v) for k, v in snap_providers.items() if v is not None
        },
    }
    return snap_dict
