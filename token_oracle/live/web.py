"""Optional live web scraper for authoritative usage % and reset times.

Uses Playwright (if installed) to open an authenticated browser context and
extract the exact numbers from the official settings/usage pages.

This is the "real time from the real websites" approach the user requested,
bypassing local log lag and calculation drift.

Usage:
  pip install playwright
  playwright install chromium   # once

Then in config or when running dash, it can be enabled.
The scraper reuses a persistent profile dir so one login lasts.

For first-time login, you can temporarily run with headless=False.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from .contract import (
    STATE_NEEDS_LOGIN,
    ProviderLive,
    provider_live_from_dict,
)
from .grok_extract import (
    build_provider_live,
    merge_readings,
    monotonic_guard,
    readings_from_labeled_text,
    readings_from_network_json,
    readings_from_progressbars,
    readings_from_reset_text,
)

PLAYWRIGHT_AVAILABLE = False
sync_playwright = None  # type: ignore
PlaywrightTimeout = Exception  # type: ignore

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright  # type: ignore

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

# Blessed venv for live features (created by live-setup bootstrap)
# Detection is now lazy: importing this module must not spawn any subprocess.
_BLESSED_VENV_PY = os.path.expanduser("~/.local/share/token-oracle/venv/bin/python")
_BLESSED_PYTHON = None
_BLESSED_CHECKED = False


def _blessed_python():
    """Return path to blessed python (if usable) or None. Performs the
    one-time subprocess check only on first call; result cached in module
    globals. This eliminates the import-time side effect.
    """
    global _BLESSED_PYTHON, _BLESSED_CHECKED
    if _BLESSED_CHECKED:
        return _BLESSED_PYTHON
    _BLESSED_CHECKED = True
    if not PLAYWRIGHT_AVAILABLE and os.path.isfile(_BLESSED_VENV_PY):
        try:
            out = subprocess.check_output(
                [_BLESSED_VENV_PY, "-c", "import playwright; print('ok')"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            if "ok" in out:
                _BLESSED_PYTHON = _BLESSED_VENV_PY
        except Exception:
            pass
    return _BLESSED_PYTHON


def _delegate_to_blessed(func_name: str, **kwargs):
    """Run a fetch/lookup function in the blessed venv python and return the result."""
    bp = _blessed_python()
    if not bp:
        return None
    try:
        arg_json = json.dumps(kwargs)
        code = f"""
import json
from token_oracle.live.web import {func_name}
from token_oracle.live.contract import provider_live_to_dict, ProviderLive
kwargs = json.loads({arg_json!r})
data = {func_name}(**kwargs)
if isinstance(data, ProviderLive):
    data = provider_live_to_dict(data)
print(json.dumps(data, default=str))
"""
        out = subprocess.check_output(
            [bp, "-c", code], text=True, stderr=subprocess.DEVNULL, timeout=60
        )
        raw = json.loads(out)
        if (
            func_name.startswith("fetch_grok")
            and isinstance(raw, dict)
            and raw.get("provider") == "grok"
        ):
            try:
                return provider_live_from_dict(raw)
            except Exception:
                return None
        return raw
    except Exception:
        return None


# Re-export for doctor / other modules
__all__ = [
    "fetch_grok_live_usage",
    "fetch_claude_live_usage",
    "PLAYWRIGHT_AVAILABLE",
    "get_live_status",
    "launch_login_session",
]

# Very small in-memory TTL cache so the live dash doesn't launch a full browser on every 1s tick.
_LIVE_CACHE: dict[str, Any] = {}
_LIVE_TTL = 25  # seconds; refresh ~2x per minute is plenty for usage numbers


def _cached_fetch(key: str, fetcher, *a, **k):
    now = time.time()
    ent = _LIVE_CACHE.get(key)
    if ent and now - ent["ts"] < _LIVE_TTL:
        return ent["val"]
    val = fetcher(*a, **k)
    _LIVE_CACHE[key] = {"ts": now, "val": val}
    return val


def get_browser_profile_dir(provider: str) -> str:
    """Public helper: returns the persistent browser profile directory for a provider ('grok' or 'claude')."""
    name = "grok" if provider.lower().startswith("grok") else "claude"
    base = os.path.expanduser("~/.config/token-oracle/browser-profiles")
    d = os.path.join(base, name)
    os.makedirs(d, exist_ok=True)
    return d


def _has_graphical_display() -> bool:
    """Best effort detection of whether we can show a real browser window."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    # On macOS/Windows the assumption is usually GUI is available when running locally
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return False


def _maybe_start_virtual_display():
    """If no real display, try to start Xvfb so headed Playwright can run.
    Returns the Popen object (or None) so caller can clean it up.
    """
    if _has_graphical_display():
        return None
    if not shutil.which("Xvfb"):
        return None
    # Try to find a free display number
    for disp_num in range(99, 150):
        disp = f":{disp_num}"
        try:
            proc = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", "1280x1024x24", "-ac", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.3)
            if proc.poll() is None:  # still running
                os.environ["DISPLAY"] = disp
                print("  Started virtual display (Xvfb) for browser.")
                return proc
            proc.terminate()
        except Exception:
            pass
    return None


def _get_profile_dir(name: str) -> str:
    # legacy internal
    return get_browser_profile_dir(name)


def fetch_grok_live_usage(headless: bool = True, timeout_ms: int = 15000) -> ProviderLive | None:
    """Fetch current Grok usage from grok.com Settings → Usage.

    Returns ProviderLive (state + evidence-bound LiveReadings) or None only
    when playwright unavailable and delegation failed.
    Uses short TTL cache keyed grok:{headless}.
    """
    if not PLAYWRIGHT_AVAILABLE:
        delegated = _delegate_to_blessed(
            "fetch_grok_live_usage", headless=headless, timeout_ms=timeout_ms
        )
        if isinstance(delegated, ProviderLive):
            return delegated
        if delegated is None:
            return None
        if isinstance(delegated, dict):
            try:
                return provider_live_from_dict(delegated)
            except Exception:
                return None
        return None

    ck = f"grok:{headless}"
    now = time.time()
    ent = _LIVE_CACHE.get(ck)
    if ent and now - ent["ts"] < _LIVE_TTL:
        cached = ent["val"]
        if isinstance(cached, ProviderLive):
            return cached
        if isinstance(cached, dict):
            try:
                return provider_live_from_dict(cached)
            except Exception:
                pass
        return None

    url = "https://grok.com/settings/usage"
    profile_dir = _get_profile_dir("grok")

    try:
        if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
            print("   • launching browser (Chromium) for grok.com ...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
                viewport={"width": 1200, "height": 800},
            )
            page = context.new_page()

            # Capture raw JSON payloads BEFORE any navigation (initial XHR burst
            # often contains the authoritative remainingQueries payload).
            captured: list[tuple[str, dict]] = []

            def _on_response(resp):
                try:
                    ct = resp.headers.get("content-type", "") or ""
                    if "json" in ct.lower():
                        j = resp.json()
                        if isinstance(j, dict):
                            captured.append((resp.url or "", j))
                except Exception:
                    pass

            try:
                page.on("response", _on_response)
            except Exception:
                pass

            # Warm + deep link. NO blind click navigation loops.
            if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
                print("   • warming main grok.com page...")
            try:
                page.goto("https://grok.com", wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_load_state("networkidle", timeout=6000)
                page.wait_for_timeout(400)
            except Exception:
                pass

            if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
                print("   • loading grok usage page and waiting for data...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Single targeted wait for progress UI (no click cascades).
            try:
                page.wait_for_selector('[role="progressbar"], progress', timeout=8000)
            except Exception:
                pass

            try:
                final_url = getattr(page, "url", url) or url
                page_title = page.title() or ""
            except Exception:
                final_url = url
                page_title = ""

            # Login wall check (after navigation attempts).
            try:
                content = (page.content() or "").lower()
            except Exception:
                content = ""
            looks_like_login_wall = ("sign in" in content or "log in" in content) and (
                "usage" not in content
                and "limit" not in content[:3000]
                and "settings" not in content[:1500]
            )
            if looks_like_login_wall:
                context.close()
                pl = ProviderLive(
                    provider="grok",
                    state=STATE_NEEDS_LOGIN,
                    readings=[],
                    fetched_at=now,
                    error=None,
                    note="login wall",
                )
                _LIVE_CACHE[ck] = {"ts": time.time(), "val": pl}
                return pl

            # Authenticated at this point (passed obvious wall).
            if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
                print("   • collecting usage facts via DOM evaluate...")

            # One evaluate for bars + sections (no full body walk, no __NEXT concat here).
            facts: dict[str, Any] = {"bars": [], "sections": []}
            try:
                facts = page.evaluate(
                    """
() => {
  const bars = [];
  const seenLabels = new Set();
  const sections = [];
  const barSel = '[role=progressbar], progress, [aria-valuenow]';
  document.querySelectorAll(barSel).forEach(el => {
    const vn = el.getAttribute('aria-valuenow') || (el.value != null ? String(el.value) : null);
    const vm = el.getAttribute('aria-valuemax') || null;
    let lb = '';
    const csel = 'section, li, [class*="card" i], [class*="usage" i], [class*="quota" i]';
    const anc = el.closest(csel) || el.parentElement || el;
    if (anc) { lb = (anc.innerText || anc.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120); }
    bars.push({valuenow: vn, valuemax: vm, label: lb});
  });
  const labelAnc = new Set();
  document.querySelectorAll(barSel).forEach(el => {
    const a = el.closest('section, li, [class*="card" i], [class*="usage" i], [class*="quota" i]');
    if (a) labelAnc.add(a);
  });
  labelAnc.forEach(anc => {
    const t = (anc.innerText || anc.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 300);
    if (t && !seenLabels.has(t)) { seenLabels.add(t); sections.push(t); }
  });
  const headSel = 'h1,h2,h3,h4,[class*="usage" i],[class*="limit" i],[class*="quota" i]';
  document.querySelectorAll(headSel).forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 300);
    if (t && !seenLabels.has(t)) { seenLabels.add(t); sections.push(t); }
  });
  return {bars: bars.slice(0, 30), sections: sections.slice(0, 40)};
}
"""
                )
            except Exception:
                facts = {"bars": [], "sections": []}

            # Feed the pure extractors.
            readings: list = []
            for u, obj in captured:
                try:
                    rs = readings_from_network_json(u, obj, now)
                    readings.extend(rs)
                except Exception:
                    pass

            try:
                bars = facts.get("bars") or []
                readings.extend(readings_from_progressbars(bars, now))
            except Exception:
                pass

            try:
                sections = facts.get("sections") or []
                readings.extend(readings_from_labeled_text(sections, now))
                readings.extend(readings_from_reset_text(sections, now))
            except Exception:
                pass

            readings = merge_readings(readings)

            # monotonic guard (load persisted snapshot)
            prev_snap = None
            try:
                from . import store as _store

                prev_snap = _store.load_snapshot()
            except Exception:
                prev_snap = None
            readings = monotonic_guard(readings, prev_snap, now)

            note = f"landed on {final_url}"
            pl = build_provider_live(readings, authenticated=True, note=note, now=now)

            # Debug dump retargeted to user-writable share dir (avoid /tmp hijack risk).
            if os.environ.get("TOKEN_ORACLE_LIVE_DEBUG"):
                has_high_weekly = any(
                    (r.metric == "weekly_pct" and r.confidence == "high")
                    for r in (pl.readings or [])
                )
                if not has_high_weekly:
                    try:
                        debug_dir = os.path.expanduser("~/.local/share/token-oracle/debug")
                        os.makedirs(debug_dir, exist_ok=True)
                        dump_path = os.path.join(debug_dir, "grok-usage.txt")
                        sample = ""
                        try:
                            sample = (page.inner_text("body") or "")[:2200]
                        except Exception:
                            pass
                        with open(dump_path, "w", encoding="utf-8") as df:
                            df.write("URL: https://grok.com/settings/usage (attempted)\n")
                            df.write("final_url: " + str(final_url) + "\n")
                            df.write("page_title: " + str(page_title) + "\n")
                            df.write("fetched_at: " + str(now) + "\n")
                            df.write("state: " + str(pl.state) + "\n")
                            df.write("readings: " + str(len(pl.readings)) + "\n\n")
                            df.write("=== BARS ===\n" + str(facts.get("bars")) + "\n\n")
                            df.write("=== SECTIONS (first few) ===\n")
                            for s in (facts.get("sections") or [])[:5]:
                                df.write(str(s)[:200] + "\n---\n")
                            df.write("\n=== SAMPLE BODY TEXT ===\n" + sample + "\n")
                            df.write("\n=== CAPTURED JSON URLS ===\n")
                            for uu, _ in captured[:5]:
                                df.write(str(uu)[:120] + "\n")
                    except Exception:
                        pass

            context.close()
            _LIVE_CACHE[ck] = {"ts": time.time(), "val": pl}
            return pl

    except Exception:
        _LIVE_CACHE[ck] = {"ts": time.time(), "val": None}
        return None


def fetch_claude_live_usage(
    headless: bool = True, timeout_ms: int = 15000
) -> dict[str, Any] | None:
    """Fetch current Claude usage from claude.ai/settings/usage .

    Returns similar dict with 5h and weekly info.
    Uses TTL cache.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _delegate_to_blessed(
            "fetch_claude_live_usage", headless=headless, timeout_ms=timeout_ms
        )

    ck = f"claude:{headless}"
    nowt = time.time()
    ent = _LIVE_CACHE.get(ck)
    if ent and nowt - ent["ts"] < _LIVE_TTL:
        return ent["val"]

    url = "https://claude.ai/settings/usage"
    profile_dir = _get_profile_dir("claude")

    val = None
    try:
        if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
            print("   • launching browser (Chromium) for claude.ai ...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1100, "height": 800},
            )
            page = context.new_page()
            if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
                print("   • loading claude.ai/settings/usage ...")
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Aggressive SPA handling for claude.ai too
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass
            for _ in range(2):
                try:
                    for label in ("Usage", "usage", "Limits"):
                        loc = page.get_by_text(label, exact=False).first
                        if loc and loc.is_visible():
                            loc.click()
                            break
                    page.wait_for_timeout(400)
                except Exception:
                    pass
                time.sleep(0.3)

            text = page.inner_text("body") or ""

            if not os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE"):
                print("   • parsing claude usage numbers...")

            if "sign in" in text.lower():
                context.close()
                return None

            # Extra DOM attribute scraping (broadened)
            try:
                extra = page.evaluate("""
() => {
  const out = [];
  document.querySelectorAll('[aria-valuenow],[role=progressbar],progress,[data-*]').forEach(el => {
    const v = el.getAttribute('aria-valuenow') || el.value || el.getAttribute('data-percent') || el.getAttribute('data-value') || (el.style && el.style.width) || '';
    if (v) out.push('progress:' + String(v));
  });
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = (n.nodeValue || '').trim();
    if (t.length > 0 && t.length < 200 && (/[0-9]/.test(t) || /%/.test(t))) out.push('txt:' + t);
  }
  document.querySelectorAll('h1,h2,h3,[class*="usage" i],[class*="limit" i],[class*="quota" i]').forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
    if (t && (/[0-9]/.test(t) || /usage|limit|reset|fable|all models/i.test(t))) out.push('label:' + t);
  });
  return out.slice(0, 20);
}
""")
                if extra:
                    text += "\n" + "\n".join(extra)
            except Exception:
                pass

            result: dict[str, Any] = {
                "source": "claude-web",
                "fetched_at": time.time(),
                "authenticated": True,
            }

            # Better structured scrape for Claude /settings/usage
            # Separate All models (weekly) vs Fable, and 5h state.
            # The site shows distinct % for "All models" and "Fable", plus reset times.

            low = text.lower()

            # All models (the main weekly cloud pool) — use .*? to cross newlines/labels like "Resets Thu..."
            m_all = re.search(r"(?i)all\s*models.*?(?P<pct>\d+(?:\.\d+)?)\s*%", text, re.S)
            if m_all:
                result["all_pct"] = float(m_all.group("pct"))
            elif "all models" in low:
                after = text[low.find("all models") :]
                mp = re.search(r"(\d+(?:\.\d+)?)\s*%", after)
                if mp:
                    result["all_pct"] = float(mp.group(1))

            # Fable specific weekly
            m_fab = re.search(r"(?i)\bfable\b.*?(?P<pct>\d+(?:\.\d+)?)\s*%", text, re.S)
            if m_fab:
                result["fable_pct"] = float(m_fab.group("pct"))
            elif "fable" in low:
                after = text[low.find("fable") :]
                mp = re.search(r"(\d+(?:\.\d+)?)\s*%", after)
                if mp:
                    result["fable_pct"] = float(mp.group(1))

            # Capture reset hints (e.g. "Resets Thu 9:00 PM")
            reset_hit = re.search(
                r"(?i)resets\s+([A-Za-z]{3,9}\s+\d{1,2}:\d{2}\s*(?:[AP]M)?)", text
            )
            if reset_hit:
                result["reset_text"] = "Resets " + reset_hit.group(1).strip()

            # 5h / current window state — the label and the "starts when..." may be on separate lines
            m5 = re.search(
                r"(?i)(5\s*h|5-hour|five.?hour|current[^.]*limit|5h)[^\n]{0,160}", text, re.S
            )
            if m5:
                t5 = m5.group(0).strip()
                result["five_hour_text"] = t5
            # independent state probe (covers "Starts when a message is sent" on its own line)
            if re.search(
                r"start.*(message|sent)|starts when|when you send|idle until|begins (on|when)|not (yet )?active",
                low,
            ):
                result["five_hour_state"] = "starts_on_first_message"
                result["five_hour_pct"] = 0.0
            elif m5:
                t5 = result.get("five_hour_text", "")
                mins = re.search(r"(\d+)\s*(minute|min)", t5, re.I)
                if mins:
                    result["five_hour_reset_in_secs"] = int(mins.group(1)) * 60
                mp = re.search(r"(\d+(?:\.\d+)?)\s*%", t5)
                if mp:
                    result["five_hour_pct"] = float(mp.group(1))

            # General fallback pcts (in case structure changes)
            pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
            if pcts:
                result["pcts_found"] = [float(x) for x in pcts[:6]]

            context.close()
            # Return even without specific data keys, so we can tell "authenticated but scrape didn't find numbers"

            # Debug aid for Claude too
            if (
                "all_pct" not in result
                and "fable_pct" not in result
                and "five_hour_pct" not in result
                and not result.get("five_hour_state")
                and os.environ.get("TOKEN_ORACLE_LIVE_DEBUG")
            ):
                try:
                    print(
                        "[live-debug claude] authenticated but no mapped usage numbers.",
                        file=sys.stderr,
                    )
                    with open("/tmp/token-oracle-claude-usage.txt", "w", encoding="utf-8") as df:
                        df.write("URL: https://claude.ai/settings/usage\n")
                        df.write("keys: " + str(list(result.keys())) + "\n\n")
                        df.write(text or "")
                except Exception:
                    pass

            val = result

    except Exception:
        val = None

    _LIVE_CACHE[ck] = {"ts": time.time(), "val": val}
    return val


def launch_login_session(provider: str = "grok", headless: bool = False) -> bool:
    """Launch a (headed by default) browser using the token-oracle persistent profile.

    - If a graphical display is available we prefer a real window (system Chrome if present).
    - If no GUI (remote / server / pure terminal) we try to start Xvfb so the
      automation can still run. For interactive login on remote machines the
      practical options are usually:
        * ssh -X
        * Run the setup once on a machine with GUI and rsync the profile dir
        * Use the direct URLs printed below and somehow get cookies into the profile
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright is not installed in the current Python environment.")
        print("Run `oracle live-setup` (it can set things up automatically).")
        return False

    if provider.lower().startswith("grok"):
        url = "https://grok.com"
        prof_name = "grok"
        display = "Grok"
    else:
        url = "https://claude.ai"
        prof_name = "claude"
        display = "Claude"

    profile_dir = get_browser_profile_dir(prof_name)
    prof_display = profile_dir.replace(os.path.expanduser("~"), "~")

    # Fast path — check BEFORE any "opening" message or browser launch.
    # This makes re-running `oracle live-setup` completely silent for already-authenticated providers.
    if _looks_logged_in(provider):
        print(f"✓ Already logged in for {display} (from previous session, no browser needed).")
        return True

    print(f"   Using profile: {prof_display}")
    print("   (This login step is one-time only. Future runs of `oracle live-setup` will skip it.)")

    xvfb_proc = _maybe_start_virtual_display()

    # Default to Playwright's own bundled Chromium. It is the most reliable.
    # System Chrome often crashes on Linux (VAAPI, GTK modules, library mismatches).
    # Set TOKEN_ORACLE_USE_SYSTEM_BROWSER=1 if you want to experiment with your installed Chrome.
    channel = None
    if os.environ.get("TOKEN_ORACLE_USE_SYSTEM_BROWSER"):
        for cand in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            if shutil.which(cand):
                channel = "chrome"
                break

    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
                "viewport": {"width": 1280, "height": 800},
            }
            if channel:
                launch_kwargs["channel"] = channel

            context = p.chromium.launch_persistent_context(profile_dir, **launch_kwargs)
            page = context.new_page()

            # Go straight to the usage page so the user can verify the numbers immediately
            usage_url = (
                "https://grok.com/settings/usage"
                if provider.lower().startswith("grok")
                else "https://claude.ai/settings/usage"
            )
            page.goto(usage_url, wait_until="domcontentloaded", timeout=30000)

            # We intentionally do NOT call webbrowser.open() here.
            # The Playwright persistent context (with headless=False) is the one
            # that uses the correct profile directory. Opening the system's default
            # browser would log in to the wrong cookie jar and open a second window.

            if not headless:
                print(
                    "  1. A browser window should open (this is the one using the token-oracle profile)."
                )
                print("  2. Log in with your normal account if needed.")
                print("  3. You should now see your usage numbers on the page.")
                print("  4. Close the window when done, then press Enter here.")
                print(
                    "     This is a ONE-TIME step. Future `oracle live-setup` runs will detect the session and skip opening the browser."
                )
                try:
                    input("\n[Press Enter after you have logged in (or if already logged in)] ")
                except EOFError:
                    pass
            else:
                print("  Running under virtual display (no visible window on this machine).")
                print(f"  Please make sure you are logged in at {usage_url}.")
                try:
                    input("\n[Press Enter when login is complete] ")
                except EOFError:
                    pass

            context.close()
        print("✓ Login saved for " + display + ".")
        return True
    except Exception as e:
        err = str(e)
        if "closed" in err.lower() or "crashed" in err.lower() or "target page" in err.lower():
            print("   The browser was closed or crashed during launch.")
            print(
                "   This can happen if you closed the window too early, or due to system Chrome issues."
            )
            print(
                "   Run `oracle live-setup` again — it will skip providers that are already logged in."
            )
            return False
        if "X server" in err or "DISPLAY" in err or not os.environ.get("DISPLAY"):
            print("   No graphical display available for the browser.")
            print("")
            print("   Practical options for remote/no-GUI machines:")
            print("   • ssh -X user@host   then run `oracle live-setup` (X11 forwarding)")
            print("   • On a machine with a GUI run `oracle live-setup`, then copy the profiles:")
            print(
                "       rsync -av ~/.config/token-oracle/browser-profiles/ user@remote:~/.config/token-oracle/"
            )
            print("   • We tried to start a virtual Xvfb display (if Xvfb is installed).")
        else:
            print(f"   Could not launch browser: {e}")
        return False
    finally:
        if xvfb_proc:
            try:
                xvfb_proc.terminate()
            except Exception:
                pass


def get_live_status() -> dict:
    """Rich status for live web.
    Returns e.g.
    {
      "grok": "ok" | "needs_login" | "unavailable" | "error",
      "claude": "...",
      "last_fetch": 1699999999.0 or None,
      "last_attempt": 1699999999.0 or None,
      "delegated": bool,
      "message": "short human note"
    }
    The last_attempt is *always* populated when we actually probe (even on needs_login
    or empty results). This makes `oracle dash` clearly show that live web was tried.
    """
    attempt_at = time.time()
    result = {
        "grok": "unavailable",
        "claude": "unavailable",
        "last_fetch": None,
        "last_attempt": attempt_at,
        "delegated": False,
        "message": "",
    }
    if not PLAYWRIGHT_AVAILABLE:
        bp = _blessed_python()
        if bp:
            # Delegate the whole status call
            try:
                code = """
import json
from token_oracle.live.web import get_live_status
print(json.dumps(get_live_status()))
"""
                out = subprocess.check_output(
                    [bp, "-c", code], text=True, stderr=subprocess.DEVNULL, timeout=60
                )
                delegated = json.loads(out)
                delegated["delegated"] = True
                delegated["message"] = "using dedicated venv"
                delegated.setdefault("last_attempt", time.time())
                return delegated
            except Exception as e:
                return {
                    "grok": "error",
                    "claude": "error",
                    "last_fetch": None,
                    "last_attempt": time.time(),
                    "delegated": True,
                    "message": f"delegation failed: {e}",
                }
        result["last_attempt"] = attempt_at
        return result

    # Current python has playwright
    fetches = {}
    last = None
    data_by_name = {}
    for name, fetcher in (("grok", fetch_grok_live_usage), ("claude", fetch_claude_live_usage)):
        try:
            data = fetcher(headless=True)
            if data:
                data_by_name[name] = data
                if name == "grok" and isinstance(data, ProviderLive):
                    st = data.state
                    fetches[name] = (
                        st
                        if st
                        in ("ok", "rate_data_only", "authenticated_no_data", "needs_login", "error")
                        else "authenticated_no_data"
                    )
                    if data.fetched_at:
                        last = max(last or 0, data.fetched_at)
                elif isinstance(data, dict):
                    # claude or legacy dict path
                    has_specific = (
                        data.get("build_pct") is not None
                        or data.get("overall_pct") is not None
                        or data.get("all_pct") is not None
                        or data.get("fable_pct") is not None
                        or data.get("five_hour_pct") is not None
                        or data.get("five_hour_state")
                    )
                    has_rate_data = data.get("query_remaining") is not None
                    saw_raw_numbers = bool(data.get("pcts_found")) or has_specific or has_rate_data
                    if has_specific:
                        fetches[name] = "ok"
                    elif data.get("authenticated"):
                        if has_rate_data and not has_specific:
                            fetches[name] = "rate_data_only"
                        else:
                            fetches[name] = "authenticated_no_data"
                    else:
                        fetches[name] = "needs_login"
                    if data.get("fetched_at"):
                        last = max(last or 0, data["fetched_at"])
                else:
                    fetches[name] = "authenticated_no_data"
            else:
                fetches[name] = "needs_login"
        except Exception:
            fetches[name] = "error"

    result.update(fetches)
    result["last_fetch"] = last
    result["last_attempt"] = time.time()
    result["delegated"] = False
    result["message"] = "direct"

    # Propagate rate limit info for display in doctor/dash
    for name in ("grok", "claude"):
        if name in data_by_name:
            d = data_by_name[name]
            if isinstance(d, ProviderLive):
                for r in d.readings or []:
                    if r.metric == "rate_window":
                        result[f"{name}_query_used_pct"] = r.value
            elif isinstance(d, dict):
                for k in ("query_remaining", "query_total", "query_window_secs", "query_used_pct"):
                    if k in d:
                        result[f"{name}_{k}"] = d[k]
    if all(v == "ok" for v in fetches.values()):
        result["message"] = "live web active"
    elif any(v == "rate_data_only" for v in fetches.values()):
        result["message"] = (
            "live rate limit data available (query window); no usage % parsed from settings"
        )
    elif any(v == "authenticated_no_data" for v in fetches.values()):
        result["message"] = "authenticated but scraper found no usage numbers"
        # if one of the raw results had extra info, keep a short note
        # (the actual fetch results are what dashboard/doctor primarily use)
    elif any(v == "needs_login" for v in fetches.values()):
        result["message"] = "run `oracle live-setup` to authenticate"
    return result


def _looks_logged_in(provider: str) -> bool:
    """Check if we have a valid authenticated session for the provider.
    Uses the real fetch logic so it's consistent with what `oracle dash` sees.
    """
    if not PLAYWRIGHT_AVAILABLE:
        delegated = _delegate_to_blessed("_looks_logged_in", provider=provider)
        if delegated is not None:
            return delegated
        return False

    try:
        raw_data: Any = None
        if provider.lower().startswith("grok"):
            raw_data = fetch_grok_live_usage(headless=True)
        else:
            raw_data = fetch_claude_live_usage(headless=True)
        data = raw_data

        if not data:
            return False

        if isinstance(data, ProviderLive):
            # per plan: grok authenticated unless explicit needs/unavailable/error
            return data.state not in ("needs_login", "unavailable", "error")

        # Authenticated (passed login wall) is enough to skip re-login in live-setup.
        # We don't require the usage numbers to be parsed for the "one-time" skip.
        if data.get("authenticated"):
            return True

        # Fallback: any usage data key present
        keys = (
            "build_pct",
            "overall_pct",
            "all_pct",
            "fable_pct",
            "five_hour_state",
            "five_hour_reset_in_secs",
            "five_hour_pct",
        )
        return any(data.get(k) is not None for k in keys)
    except Exception:
        return False


if __name__ == "__main__":
    print("Grok live:", fetch_grok_live_usage(headless=True))
    print("Claude live:", fetch_claude_live_usage(headless=True))
