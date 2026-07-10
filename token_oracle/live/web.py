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
from typing import Optional, Dict, Any

PLAYWRIGHT_AVAILABLE = False
sync_playwright = None  # type: ignore
PlaywrightTimeout = Exception  # type: ignore

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout  # type: ignore
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
                text=True, stderr=subprocess.DEVNULL, timeout=5
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
kwargs = json.loads({arg_json!r})
data = {func_name}(**kwargs)
print(json.dumps(data, default=str))
"""
        out = subprocess.check_output([bp, "-c", code], text=True, stderr=subprocess.DEVNULL, timeout=60)
        return json.loads(out)
    except Exception:
        return None

# Re-export for doctor / other modules
__all__ = ["fetch_grok_live_usage", "fetch_claude_live_usage", "PLAYWRIGHT_AVAILABLE", "get_live_status", "launch_login_session"]

# Very small in-memory TTL cache so the live dash doesn't launch a full browser on every 1s tick.
_LIVE_CACHE: Dict[str, Any] = {}
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


def fetch_grok_live_usage(headless: bool = True, timeout_ms: int = 15000) -> Optional[Dict[str, Any]]:
    """Fetch current Grok usage from grok.com Settings → Usage.

    Returns dict like:
      {
        "overall_pct": 1.0,
        "build_pct": 1.0,   # for "Grok build"
        "reset_in_secs": 3600*24*3 + ...,  # or None
        "reset_at": "2026-07-17 ...", 
        "source": "grok-web",
        "fetched_at": time.time()
      }
    or None if unavailable / not logged in.
    Uses short TTL cache so live dashboard is not expensive.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _delegate_to_blessed("fetch_grok_live_usage", headless=headless, timeout_ms=timeout_ms)

    ck = f"grok:{headless}"
    now = time.time()
    ent = _LIVE_CACHE.get(ck)
    if ent and now - ent["ts"] < _LIVE_TTL:
        return ent["val"]

    url = "https://grok.com/settings/usage"
    profile_dir = _get_profile_dir("grok")

    try:
        if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
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

            # Many SPAs (especially Next.js) do not fully populate deep-link
            # content (like /settings/usage quota panel) on the first goto.
            # Warm the session on the main app first, then navigate to usage.
            # This greatly increases the chance the real usage numbers hydrate.
            if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
                print("   • warming main grok.com page...")
            try:
                page.goto("https://grok.com", wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_load_state("networkidle", timeout=6000)
                # small settle for the logged-in shell (name, "Grok Build", chat input etc.)
                page.wait_for_timeout(400)
            except Exception:
                pass

            # Now go for the usage view
            if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
                print("   • loading grok usage page and waiting for data...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass

            # Capture any JSON usage payloads that the app fetches in the background.
            # SPAs frequently load the authoritative numbers via XHR/fetch rather than
            # putting NN% directly in the initial DOM text.
            captured_usage: Dict[str, Any] = {}
            def _on_response(resp):
                try:
                    ct = resp.headers.get("content-type", "") or ""
                    if "json" in ct.lower():
                        j = resp.json()
                        if isinstance(j, dict):
                            # Broad capture: any json with usage-like keys or numeric values.
                            # This catches rate limits, quotas, build usage etc even if URL doesn't hint.
                            for k, v in list(j.items())[:30]:
                                kl = str(k).lower()
                                if any(x in kl for x in ("usage", "limit", "quota", "percent", "reset", "used", "remaining", "build", "heavy", "weekly", "query", "rate", "token", "cap")):
                                    captured_usage[k] = v
                                elif isinstance(v, (int, float)) or (isinstance(v, str) and re.search(r'\d', v)):
                                    captured_usage.setdefault(k, v)
                            # nested shallow
                            for sub in list(j.values()):
                                if isinstance(sub, dict):
                                    for k, v in list(sub.items())[:10]:
                                        if isinstance(v, (int, float)):
                                            captured_usage.setdefault(k, v)
                except Exception:
                    pass
            try:
                page.on("response", _on_response)
            except Exception:
                pass

            # If login wall, bail out. Be conservative...
            content = page.content().lower()
            looks_like_login_wall = ("sign in" in content or "log in" in content) and ("usage" not in content and "limit" not in content[:3000] and "settings" not in content[:1500])
            if looks_like_login_wall:
                context.close()
                val = None
            else:
                # We got past the obvious login wall → consider authenticated.
                # (We may still fail to parse the specific usage numbers.)
                result: Dict[str, Any] = {"source": "grok-web", "fetched_at": time.time(), "authenticated": True}

                # Give the SPA plenty of time + active interaction to surface the usage panel.
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                # Try to surface the usage numbers by clicking likely tabs/labels.
                # Also try a settings nav if present.
                for _ in range(4):
                    try:
                        for label in ("Usage", "usage", "Limits", "Stats", "Settings", "Account"):
                            try:
                                loc = page.get_by_text(label, exact=False).first
                                if loc and loc.is_visible():
                                    loc.click()
                                    page.wait_for_timeout(300)
                            except Exception:
                                pass
                        # also try role-based or href-ish
                        for sel in ('a[href*="usage"]', 'a[href*="limit"]', '[data-testid*="usage"]', 'button:has-text("Usage")'):
                            try:
                                loc = page.locator(sel).first
                                if loc and loc.is_visible():
                                    loc.click()
                                    page.wait_for_timeout(300)
                            except Exception:
                                pass
                        page.wait_for_selector("text=/usage|limit|reset|build|super|weekly|quota/i", timeout=2000)
                    except Exception:
                        pass
                    time.sleep(0.4)

                # Extra settle so any late XHR finish and React renders the meters
                page.wait_for_timeout(700)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                # If we are still on the main chat shell (common SPA behavior), try opening
                # the user menu / settings / Build section to surface the usage panel.
                try:
                    cur = (page.url or "")
                    if "/settings" not in cur and "/usage" not in cur:
                        for sel in [
                            'button[aria-haspopup="menu"]',
                            '[aria-label*="user" i], [aria-label*="account" i], [aria-label*="profile" i]',
                            'text=/Grok Build|Build Beta/i',
                            'a[href*="/settings"]',
                            'text=Settings',
                        ]:
                            try:
                                loc = page.locator(sel).first
                                if loc and loc.is_visible():
                                    loc.click()
                                    page.wait_for_timeout(400)
                                    # now click into usage/limits if submenu appeared
                                    for us in ("Usage", "usage", "Limits", "limits", "Usage & limits"):
                                        try:
                                            ul = page.get_by_text(us, exact=False).first
                                            if ul and ul.is_visible():
                                                ul.click()
                                                page.wait_for_timeout(400)
                                                break
                                        except Exception:
                                            pass
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass

                # Final waits after possible menu navigation
                page.wait_for_timeout(600)
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass

                # Snapshot where we actually ended up (critical for debugging "why no numbers")
                try:
                    final_url = getattr(page, "url", url)
                    page_title = page.title()
                except Exception:
                    final_url = url
                    page_title = ""

                if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
                    print("   • parsing grok usage numbers from page...")
                text = page.inner_text("body") or page.content()

                # Merge any JSON payloads we saw over the wire (often has the real % / reset)
                if captured_usage:
                    try:
                        text += "\n__CAPTURED_API__:" + json.dumps(captured_usage, separators=(',',':'))[:2800]
                    except Exception:
                        pass

                # Mine Next.js embedded JSON state (very often contains the real usage/quotas as source of truth)
                try:
                    next_json = page.evaluate("""
() => {
  const el = document.querySelector('#__NEXT_DATA__') || document.querySelector('script#__NEXT_DATA__');
  if (!el || !el.textContent) return null;
  try { return JSON.parse(el.textContent); } catch(e) { return {parse_error: String(e).slice(0,120)}; }
}
""")
                    if next_json:
                        try:
                            flat = json.dumps(next_json, separators=(',',':'))[:4500]
                            text += "\n__NEXT_DATA__:" + flat
                        except Exception:
                            pass
                except Exception:
                    pass

                # Extra aggressive extraction for modern SPAs (aria, progress, style widths, sub-elements, labels, digit text)
                try:
                    extra = page.evaluate("""
() => {
  const out = [];
  document.querySelectorAll('[aria-valuenow],[role=progressbar],progress,[data-percent],[data-value],[data-usage],[data-limit]').forEach(el => {
    const v = el.getAttribute('aria-valuenow') || el.value || el.getAttribute('data-percent') || el.getAttribute('data-value') || (el.style && el.style.width) || '';
    if (v) out.push('progress:' + String(v));
    const maxv = el.getAttribute('aria-valuemax');
    if (maxv) out.push('progressmax:' + String(maxv));
  });
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = (n.nodeValue || '').trim();
    if (t.length > 0 && t.length < 200 && (/[0-9]/.test(t) || /%/.test(t))) out.push('txt:' + t);
  }
  // Capture headings/labels/usage sections that may sit next to numbers (no % on the node itself)
  document.querySelectorAll('h1,h2,h3,h4,h5,div,span,section,[class*="usage" i],[class*="limit" i],[class*="quota" i],[class*="progress" i],[class*="rate" i]').forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
    if (t.length > 0 && t.length < 180 && (/[0-9]/.test(t) || /usage|limit|reset|build|heavy|weekly|quota/i.test(t))) {
      out.push('label:' + t);
    }
  });
  return out.slice(0, 30);
}
""")
                    if extra:
                        text += "\n" + "\n".join(extra)
                except Exception:
                    pass

                low = text.lower()

                # Try specific labels first for SuperGrok / Build / Heavy
                for label in ("supergrok", "grok build", "build", "heavy", "weekly", "super grok", "grok 4", "advanced", "usage"):
                    idx = low.find(label)
                    if idx >= 0:
                        after = text[idx: idx+220]
                        mp = re.search(r'(\d+(?:\.\d+)?)\s*%', after)
                        if mp:
                            pct = float(mp.group(1))
                            if any(k in label for k in ("build", "heavy", "super", "advanced")):
                                result["build_pct"] = pct
                            else:
                                result.setdefault("overall_pct", pct)

                # Generic first % (augmented text now includes __NEXT + many more candidates)
                if "overall_pct" not in result and "build_pct" not in result:
                    m = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
                    if m:
                        result["overall_pct"] = float(m.group(1))

                # --- Richer parsers for modern Grok UI (fractions, progress vals, contextual %) ---
                # Fractions e.g. "142 / 200" or "72/100 messages" near relevant keywords
                frac_patterns = [
                    r'(?i)(build|heavy|supergrok|super.?grok|grok.?build|advanced|weekly|usage|limit)[^\d\n]{0,40}(\d{1,4})\s*/\s*(\d{1,4})',
                    r'(?i)(\d{1,4})\s*/\s*(\d{1,4})[^\d\n]{0,30}(build|heavy|weekly|usage|limit|quota)',
                ]
                for pat in frac_patterns:
                    fm = re.search(pat, text)
                    if fm:
                        try:
                            # groups vary; find the two numbers
                            nums = re.findall(r'\d{1,4}', fm.group(0))
                            if len(nums) >= 2:
                                used, tot = float(nums[0]), float(nums[1])
                                if tot > 0:
                                    pct = round(used / tot * 100.0, 1)
                                    grp = fm.group(0).lower()
                                    if any(k in grp for k in ('build','heavy','super','advanced')):
                                        result.setdefault("build_pct", pct)
                                    else:
                                        result.setdefault("overall_pct", pct)
                        except Exception:
                            pass

                # Parse progress:NN  (from aria-valuenow or style) — treat 0-100 as pct, 0-1 as fraction
                # Also progressmax helps confirm scale
                for line in re.findall(r'progress:[^\s]+', text):
                    try:
                        raw = line.split(':', 1)[1].rstrip('%').strip()
                        num = float(raw)
                        if 0 < num <= 1.0:
                            num *= 100.0
                        if 0 < num <= 150:
                            result.setdefault("overall_pct", round(num, 1))
                            # if we also saw a build-ish label nearby in the text, prefer build
                            if re.search(r'(?i)(build|heavy|super)', text[max(0, text.find(line)-80): text.find(line)+80] or ''):
                                result["build_pct"] = result["overall_pct"]
                    except Exception:
                        pass

                # Contextual % with broader keywords (catches more label placements)
                for m in re.finditer(r'(?i)(build|heavy|supergrok|super|weekly|usage|limit|quota|grok)[^%\n]{0,90}?(\d+(?:\.\d+)?)\s*%', text):
                    try:
                        pct = float(m.group(2))
                        lbl = (m.group(1) or '').lower()
                        if any(k in lbl for k in ('build','heavy','super')):
                            result["build_pct"] = pct
                        else:
                            result.setdefault("overall_pct", pct)
                    except Exception:
                        pass

                # Always record any % we saw (like claude) for diagnostics
                pcts = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
                if pcts:
                    result.setdefault("pcts_found", [float(x) for x in pcts[:8]])

                # If the network capture gave us numbers, try to promote them
                if captured_usage:
                    for key in ("percent", "usage_pct", "weekly_pct", "build_pct", "overall"):
                        v = captured_usage.get(key)
                        if isinstance(v, (int, float)) and 0 <= v <= 100:
                            if "build" in str(key).lower() or "heavy" in str(key).lower():
                                result.setdefault("build_pct", float(v))
                            else:
                                result.setdefault("overall_pct", float(v))
                    # also look for reset times in captured
                    for key in ("reset_in", "reset_secs", "reset_in_secs", "seconds_until_reset"):
                        v = captured_usage.get(key)
                        if isinstance(v, (int, float)) and 100 < v < 86400*40:
                            result.setdefault("reset_in_secs", int(v))

                    # Special case we actually saw in the wild: remainingQueries / totalQueries
                    # (this is often the short-term chat query window, e.g. 2h)
                    rem = captured_usage.get("remainingQueries")
                    tot = captured_usage.get("totalQueries")
                    if isinstance(rem, (int, float)) and isinstance(tot, (int, float)) and tot > 0:
                        used = round( (tot - rem) / tot * 100.0 , 1)
                        # Do NOT set overall_pct or build_pct from this.
                        # It is the short-term chat query rate limit (e.g. 2h window),
                        # not the weekly/build usage cap that the forecast tracks.
                        # We surface it for info only.
                        result.setdefault("query_window_secs", captured_usage.get("windowSizeSeconds"))
                        result["query_remaining"] = int(rem)
                        result["query_total"] = int(tot)
                        result["query_used_pct"] = used  # informational only

                # Attach lightweight scrape metadata + navigation evidence
                result["scrape_len"] = len(text or "")
                result["final_url"] = final_url
                result["page_title"] = page_title
                if "build_pct" not in result and "overall_pct" not in result:
                    result.setdefault("scrape_note", "loaded page + __NEXT + labels but no usage % or build quota numbers mapped")

                # Reset hints (broader window + more variants)
                # Only trust a reset time if we actually saw a "reset(s)" keyword nearby
                # or we have at least one usage % (otherwise we mis-parse "Thought for 2.5s" etc.)
                reset_m = re.search(r'(?i)(reset|resets)[^\n]{0,140}', text)
                if reset_m:
                    result["reset_text"] = reset_m.group(0).strip()

                have_pct = bool(result.get("build_pct") or result.get("overall_pct") or result.get("pcts_found"))
                if result.get("reset_text") or have_pct:
                    rel = re.search(r'(?i)(?:in\s+)?(\d+)\s*(d|day|h|hr|hour|m|min|minute)', (result.get("reset_text", "") or "") + " " + text)
                    if rel:
                        val = int(rel.group(1))
                        unit = rel.group(2).lower()
                        secs = val * (86400 if "d" in unit or "day" in unit else 3600 if "h" in unit or "hr" in unit else 60)
                        # only set if it looks like a real future reset window (a few minutes to ~30 days)
                        if 120 < secs < 86400 * 32:
                            result["reset_in_secs"] = secs

                # Return the result even without pcts, so callers can distinguish
                # "we loaded the page while authenticated" vs "hit login wall".
                # Only return None on hard failure or explicit login wall.

                # Debug aid: when no concrete numbers were extracted, let the user inspect
                # exactly what text/attributes/JSON the scraper observed on the live page.
                # Run with TOKEN_ORACLE_LIVE_DEBUG=1 oracle dash   (or doctor) and then:
                #   cat /tmp/token-oracle-grok-usage.txt
                if ("build_pct" not in result and "overall_pct" not in result and
                        os.environ.get("TOKEN_ORACLE_LIVE_DEBUG")):
                    try:
                        sample = (text or "")[:2200]
                        print("[live-debug grok] authenticated page loaded but no mapped usage % extracted.", file=sys.stderr)
                        print("  (see /tmp/token-oracle-grok-usage.txt for the full captured text + __NEXT + labels)", file=sys.stderr)
                        with open("/tmp/token-oracle-grok-usage.txt", "w", encoding="utf-8") as df:
                            df.write("URL: https://grok.com/settings/usage (attempted)\n")
                            df.write("final_url: " + str(result.get("final_url")) + "\n")
                            df.write("page_title: " + str(result.get("page_title")) + "\n")
                            df.write("fetched_at: " + str(result.get("fetched_at")) + "\n")
                            df.write("keys_present: " + str(list(result.keys())) + "\n\n")
                            df.write("=== FULL CAPTURED TEXT (+__NEXT + progress + labels) ===\n")
                            df.write(sample + "\n... [truncated; file has more]\n\n")
                            df.write("=== low (first 800) ===\n" + low[:800] + "\n")
                        # also write a longer version
                        with open("/tmp/token-oracle-grok-usage.txt", "a", encoding="utf-8") as df:
                            df.write("\n=== COMPLETE TEXT (may be long) ===\n")
                            df.write(text or "")
                    except Exception:
                        pass

                val = result

            context.close()
            _LIVE_CACHE[ck] = {"ts": time.time(), "val": val}
            return val

    except Exception:
        _LIVE_CACHE[ck] = {"ts": time.time(), "val": None}
        return None


def fetch_claude_live_usage(headless: bool = True, timeout_ms: int = 15000) -> Optional[Dict[str, Any]]:
    """Fetch current Claude usage from claude.ai/settings/usage .

    Returns similar dict with 5h and weekly info.
    Uses TTL cache.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _delegate_to_blessed("fetch_claude_live_usage", headless=headless, timeout_ms=timeout_ms)

    ck = f"claude:{headless}"
    nowt = time.time()
    ent = _LIVE_CACHE.get(ck)
    if ent and nowt - ent["ts"] < _LIVE_TTL:
        return ent["val"]

    url = "https://claude.ai/settings/usage"
    profile_dir = _get_profile_dir("claude")

    val = None
    try:
        if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
            print("   • launching browser (Chromium) for claude.ai ...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1100, "height": 800},
            )
            page = context.new_page()
            if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
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

            if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'):
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

            result: Dict[str, Any] = {"source": "claude-web", "fetched_at": time.time(), "authenticated": True}

            # Better structured scrape for Claude /settings/usage
            # Separate All models (weekly) vs Fable, and 5h state.
            # The site shows distinct % for "All models" and "Fable", plus reset times.

            low = text.lower()

            # All models (the main weekly cloud pool) — use .*? to cross newlines/labels like "Resets Thu..."
            m_all = re.search(r'(?i)all\s*models.*?(?P<pct>\d+(?:\.\d+)?)\s*%', text, re.S)
            if m_all:
                result["all_pct"] = float(m_all.group("pct"))
            elif "all models" in low:
                after = text[low.find("all models"):]
                mp = re.search(r'(\d+(?:\.\d+)?)\s*%', after)
                if mp:
                    result["all_pct"] = float(mp.group(1))

            # Fable specific weekly
            m_fab = re.search(r'(?i)\bfable\b.*?(?P<pct>\d+(?:\.\d+)?)\s*%', text, re.S)
            if m_fab:
                result["fable_pct"] = float(m_fab.group("pct"))
            elif "fable" in low:
                after = text[low.find("fable"):]
                mp = re.search(r'(\d+(?:\.\d+)?)\s*%', after)
                if mp:
                    result["fable_pct"] = float(mp.group(1))

            # Capture reset hints (e.g. "Resets Thu 9:00 PM")
            reset_hit = re.search(r'(?i)resets\s+([A-Za-z]{3,9}\s+\d{1,2}:\d{2}\s*(?:[AP]M)?)', text)
            if reset_hit:
                result["reset_text"] = "Resets " + reset_hit.group(1).strip()

            # 5h / current window state — the label and the "starts when..." may be on separate lines
            m5 = re.search(r'(?i)(5\s*h|5-hour|five.?hour|current[^.]*limit|5h)[^\n]{0,160}', text, re.S)
            if m5:
                t5 = m5.group(0).strip()
                result["five_hour_text"] = t5
            # independent state probe (covers "Starts when a message is sent" on its own line)
            if re.search(r'start.*(message|sent)|starts when|when you send|idle until|begins (on|when)|not (yet )?active', low):
                result["five_hour_state"] = "starts_on_first_message"
                result["five_hour_pct"] = 0.0
            elif m5:
                t5 = result.get("five_hour_text", "")
                mins = re.search(r'(\d+)\s*(minute|min)', t5, re.I)
                if mins:
                    result["five_hour_reset_in_secs"] = int(mins.group(1)) * 60
                mp = re.search(r'(\d+(?:\.\d+)?)\s*%', t5)
                if mp:
                    result["five_hour_pct"] = float(mp.group(1))

            # General fallback pcts (in case structure changes)
            pcts = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
            if pcts:
                result["pcts_found"] = [float(x) for x in pcts[:6]]

            context.close()
            # Return even without specific data keys, so we can tell "authenticated but scrape didn't find numbers"

            # Debug aid for Claude too
            if ("all_pct" not in result and "fable_pct" not in result and "five_hour_pct" not in result and
                    not result.get("five_hour_state") and os.environ.get("TOKEN_ORACLE_LIVE_DEBUG")):
                try:
                    print("[live-debug claude] authenticated but no mapped usage numbers.", file=sys.stderr)
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
            usage_url = "https://grok.com/settings/usage" if provider.lower().startswith("grok") else "https://claude.ai/settings/usage"
            page.goto(usage_url, wait_until="domcontentloaded", timeout=30000)

            # We intentionally do NOT call webbrowser.open() here.
            # The Playwright persistent context (with headless=False) is the one
            # that uses the correct profile directory. Opening the system's default
            # browser would log in to the wrong cookie jar and open a second window.

            if not headless:
                print("  1. A browser window should open (this is the one using the token-oracle profile).")
                print("  2. Log in with your normal account if needed.")
                print("  3. You should now see your usage numbers on the page.")
                print("  4. Close the window when done, then press Enter here.")
                print("     This is a ONE-TIME step. Future `oracle live-setup` runs will detect the session and skip opening the browser.")
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
            print("   This can happen if you closed the window too early, or due to system Chrome issues.")
            print("   Run `oracle live-setup` again — it will skip providers that are already logged in.")
            return False
        if "X server" in err or "DISPLAY" in err or not os.environ.get("DISPLAY"):
            print("   No graphical display available for the browser.")
            print("")
            print("   Practical options for remote/no-GUI machines:")
            print("   • ssh -X user@host   then run `oracle live-setup` (X11 forwarding)")
            print("   • On a machine with a GUI run `oracle live-setup`, then copy the profiles:")
            print(f"       rsync -av ~/.config/token-oracle/browser-profiles/ user@remote:~/.config/token-oracle/")
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
    result = {"grok": "unavailable", "claude": "unavailable", "last_fetch": None, "last_attempt": attempt_at, "delegated": False, "message": ""}
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
                out = subprocess.check_output([bp, "-c", code], text=True, stderr=subprocess.DEVNULL, timeout=60)
                delegated = json.loads(out)
                delegated["delegated"] = True
                delegated["message"] = "using dedicated venv"
                delegated.setdefault("last_attempt", time.time())
                return delegated
            except Exception as e:
                return {"grok": "error", "claude": "error", "last_fetch": None, "last_attempt": time.time(), "delegated": True, "message": f"delegation failed: {e}"}
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
                has_specific = (
                    data.get("build_pct") is not None or data.get("overall_pct") is not None or
                    data.get("all_pct") is not None or data.get("fable_pct") is not None or
                    data.get("five_hour_pct") is not None or data.get("five_hour_state")
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
                fetches[name] = "needs_login"
        except Exception as e:
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
            for k in ("query_remaining", "query_total", "query_window_secs", "query_used_pct"):
                if k in d:
                    result[f"{name}_{k}"] = d[k]
    if all(v == "ok" for v in fetches.values()):
        result["message"] = "live web active"
    elif any(v == "rate_data_only" for v in fetches.values()):
        result["message"] = "live rate limit data available (query window); no usage % parsed from settings"
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
        if provider.lower().startswith("grok"):
            data = fetch_grok_live_usage(headless=True)
        else:
            data = fetch_claude_live_usage(headless=True)

        if not data:
            return False

        # Authenticated (passed login wall) is enough to skip re-login in live-setup.
        # We don't require the usage numbers to be parsed for the "one-time" skip.
        if data.get("authenticated"):
            return True

        # Fallback: any usage data key present
        keys = ("build_pct", "overall_pct", "all_pct", "fable_pct",
                "five_hour_state", "five_hour_reset_in_secs", "five_hour_pct")
        return any(data.get(k) is not None for k in keys)
    except Exception:
        return False


if __name__ == "__main__":
    print("Grok live:", fetch_grok_live_usage(headless=True))
    print("Claude live:", fetch_claude_live_usage(headless=True))
