"""What the rules treat as "now". Windows and ages must use `now()`, never the wall clock,
or the planted problems in the synthetic data age out."""

import os
from datetime import datetime, timezone

# Keep in sync with `as_of` in data/seed.json.
DEMO_AS_OF = "2026-10-09T18:00:00Z"


def now() -> datetime:
    """`AS_OF` env var (ISO 8601, or `wall` for the real clock), else the demo data's as_of. Always UTC."""
    value = os.environ.get("AS_OF", DEMO_AS_OF).strip()
    if value.lower() == "wall":
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
