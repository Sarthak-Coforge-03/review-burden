"""Replace everything in the database with data/seed.json (or another ingest-shaped file).

    python -m backend.seed [path/to/seed.json]
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from backend import clock
from backend.db import Base, SessionLocal, UTCDateTime, create_tables
from backend.models import Developer, Flag, PullRequest, Review, ReviewComment, ReviewRequest

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed.json"

# Parents before children: inserted in this order, deleted in reverse.
TABLES: list[tuple[str, type[Base]]] = [
    ("developers", Developer),
    ("pull_requests", PullRequest),
    ("reviews", Review),
    ("review_comments", ReviewComment),
    ("review_requests", ReviewRequest),
]


def _to_row(model: type[Base], record: dict[str, Any]) -> dict[str, Any]:
    """Parse ISO timestamps for datetime columns. Unknown keys raise KeyError instead of being dropped."""
    columns = model.__table__.columns
    return {
        key: datetime.fromisoformat(value)
        if value is not None and isinstance(columns[key].type, UTCDateTime)
        else value
        for key, value in record.items()
    }


def load_seed(session: Session, data: dict[str, Any]) -> dict[str, int]:
    """Delete all rows, flags included, then insert `data`. Returns rows inserted per table.
    Caller owns the transaction."""
    session.execute(delete(Flag))
    for _, model in reversed(TABLES):
        session.execute(delete(model))
    counts = {}
    for key, model in TABLES:
        rows = [_to_row(model, record) for record in data.get(key, [])]
        if rows:
            session.execute(insert(model), rows)
        counts[key] = len(rows)
    return counts


def main(argv: list[str]) -> None:
    path = Path(argv[0]) if argv else DEFAULT_SEED_PATH
    data = json.loads(path.read_text())

    create_tables()
    with SessionLocal.begin() as session:
        counts = load_seed(session, data)

    print(f"Seeded from {path}")
    for table, count in counts.items():
        print(f"  {table:<16} {count}")

    seed_as_of = data.get("as_of")
    if seed_as_of and datetime.fromisoformat(seed_as_of) != clock.now():
        print(
            f"Warning: data is as of {seed_as_of} but the rules will use {clock.now().isoformat()} as now; "
            "unset AS_OF or set it to the data's as_of.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main(sys.argv[1:])
