"""Time parsing, hour-of-week bucketing, and display formatters. Stdlib only."""

from datetime import datetime


def parse_ts(s):
    """ISO8601 (trailing Z ok) -> epoch seconds. None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def bucket_key(ts):
    """Local-time hour-of-week index: weekday(Mon=0)*24 + hour -> 0..167."""
    dt = datetime.fromtimestamp(ts).astimezone()
    return dt.weekday() * 24 + dt.hour


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n // 1000}k"


def fmt_hms(secs):
    secs = max(0, int(secs))
    return f"{secs // 3600}:{(secs % 3600) // 60:02d}"


def fmt_dh(secs):
    secs = max(0, int(secs))
    return f"{secs // 86400}d{(secs % 86400) // 3600}h"


def fmt_dur(secs):
    """Compact elapsed: 59s, 1m20s, 12m, 1h05m."""
    secs = max(0, int(secs))
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if secs < 600:
        return f"{m}m{s}s"
    if secs < 3600:
        return f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def fmt_dh_long(secs):
    """Verbose days/hours: '5 days 18 hours', '1 day', '18 hours'."""
    secs = max(0, int(secs))
    d, rem = divmod(secs, 86400)
    h = rem // 3600
    parts = []
    if d:
        parts.append(f"{d} day{'s' if d != 1 else ''}")
    if h or not d:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    return " ".join(parts)
