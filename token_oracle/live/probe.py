"""The ONLY place that actively probes providers. Everything else reads
live.json. Progress goes to the callback (stderr by default) so no consumer
surface can be polluted by browser chatter.
"""

import contextlib
import os
import time

from .contract import STATE_ERROR, STATE_UNAVAILABLE, ProviderLive, provider_live_to_dict
from .store import load_snapshot, merge_with_previous, save_snapshot
from .web import fetch_claude_live_usage, fetch_grok_live_usage, virtual_display


def run_probe(
    providers=("grok", "claude"), headless: bool = True, progress=None, path: str | None = None
) -> dict:
    """Fetch each provider, build {name: ProviderLive}, save_snapshot, and
    return the snapshot dict. Per-provider exceptions become
    ProviderLive(state=STATE_ERROR, error=str(e)[:200]) — one provider
    failing must not lose the other's data.

    Before write: merge_with_previous so (1) partial probes keep unprobed
    providers and (2) empty bot-challenge results retain last-good readings.
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
    probed: set[str] = set()

    display_ok = True
    cm = virtual_display(progress) if not headless else contextlib.nullcontext(True)
    with cm as _disp:
        if not headless:
            display_ok = bool(_disp)
        for name in prov_list:
            if name not in ("grok", "claude"):
                continue
            probed.add(name)
            if progress:
                try:
                    progress(f"   • probing {name} ...")
                except Exception:
                    pass
            try:
                if not headless and not display_ok:
                    # RC-D: honest — headed requested but no display/Xvfb available.
                    # Never lie with needs_login; user must install xorg-server-xvfb.
                    snap_providers[name] = ProviderLive(
                        provider=name,
                        state=STATE_UNAVAILABLE,
                        readings=[],
                        fetched_at=time.time(),
                        error=None,
                        note="headed mode needs a display or Xvfb (install xorg-server-xvfb)",
                    )
                    if progress:
                        try:
                            progress(f"   • {name} → {STATE_UNAVAILABLE}")
                        except Exception:
                            pass
                    continue
                if name == "grok":
                    pl = fetch_grok_live_usage(headless=headless, progress=progress)
                else:
                    pl = fetch_claude_live_usage(headless=headless, progress=progress)

                if isinstance(pl, ProviderLive):
                    snap_providers[name] = pl
                else:
                    # RC-D: None no longer means "needs_login". If we got here
                    # (headed with a display or in headless), it's an honest unavailable,
                    # not a login problem. (The fetch preflight or None return.)
                    snap_providers[name] = ProviderLive(
                        provider=name,
                        state=STATE_UNAVAILABLE,
                        readings=[],
                        fetched_at=time.time(),
                        error=None,
                        note="no data returned",
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

    # Merge last-good / unprobed providers, then atomic write.
    prev = load_snapshot(path)
    snap_providers = merge_with_previous(snap_providers, prev, probed=probed)
    save_snapshot(snap_providers, path)

    snap_dict = {
        "version": 1,
        "written_at": time.time(),
        "providers": {
            k: provider_live_to_dict(v) for k, v in snap_providers.items() if v is not None
        },
    }
    return snap_dict
