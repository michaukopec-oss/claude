"""Gate: refuse to schedule a Buffer post past the Canva export URL's expiry."""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from email.utils import parsedate_to_datetime


def url_expiry(url: str) -> datetime:
    """Authoritative expiry of a Canva signed export URL, as UTC."""
    q = parse_qs(urlparse(url).query)
    if "response-expires" in q:                      # literal timestamp, preferred
        return parsedate_to_datetime(q["response-expires"][0]).astimezone(timezone.utc)
    signed = datetime.strptime(q["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return signed + timedelta(seconds=int(q["X-Amz-Expires"][0]))


def gate(url: str, due_at: datetime, margin_min: int = 30) -> dict:
    """Decide whether `due_at` is safely inside the URL's validity."""
    exp = url_expiry(url)
    deadline = exp - timedelta(minutes=margin_min)
    ok = due_at <= deadline
    return {
        "ok": ok,
        "expires_utc": exp,
        "deadline_utc": deadline,
        "due_at_utc": due_at,
        "slack_hours": (deadline - due_at).total_seconds() / 3600,
        "action": "schedule" if ok else "RE-EXPORT before scheduling",
    }
