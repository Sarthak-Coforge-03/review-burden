"""Replace everything in the database with the demo: data/seed.json, the flags the rule engine finds
in it, and the starting triage from data/triage.json (read from next to the seed file, if present).

    python -m backend.seed [path/to/seed.json]
"""

import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from backend import clock
from backend.db import Base, SessionLocal, UTCDateTime, create_tables
from backend.models import (
    Developer,
    Flag,
    FlagRole,
    FlagStatus,
    PullRequest,
    Review,
    ReviewComment,
    ReviewRequest,
    RuleKey,
)
from backend.rules.engine import EngineResult, run_engine
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.patterns import active_patterns

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed.json"
TRIAGE_FILENAME = "triage.json"

# Parents before children: inserted in this order, deleted in reverse.
TABLES: list[tuple[str, type[Base]]] = [
    ("developers", Developer),
    ("pull_requests", PullRequest),
    ("reviews", Review),
    ("review_comments", ReviewComment),
    ("review_requests", ReviewRequest),
]


@dataclass(frozen=True)
class SeedResult:
    rows: dict[str, int]
    engine: EngineResult
    triaged: int


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


def apply_triage(session: Session, triage: list[dict[str, Any]]) -> int:
    """Set status, note and dismiss reason on existing flags, matched by identity.

    Raises ValueError if an entry matches no flag: the triage file and the rules disagree.
    """
    flags = {flag.key: flag for flag in session.scalars(select(Flag))}
    for entry in triage:
        role = entry.get("role")
        key = (RuleKey(entry["rule_key"]), entry.get("pr_id"), entry.get("person_id"), role and FlagRole(role))
        flag = flags.get(key)
        if flag is None:
            raise ValueError(f"triage entry matches no flag: {entry}")
        flag.status = FlagStatus(entry["status"])
        flag.note = entry.get("note")
        flag.dismiss_reason = entry.get("dismiss_reason")
    session.flush()
    return len(triage)


def seed_demo(session: Session, data: dict[str, Any], triage: list[dict[str, Any]]) -> SeedResult:
    """Load the data, run the rule engine, apply the triage. Caller owns the transaction."""
    rows = load_seed(session, data)
    engine = run_engine(session)
    triaged = apply_triage(session, triage)
    return SeedResult(rows=rows, engine=engine, triaged=triaged)


def main(argv: list[str]) -> None:
    path = Path(argv[0]) if argv else DEFAULT_SEED_PATH
    data = json.loads(path.read_text())
    triage_path = path.parent / TRIAGE_FILENAME
    triage = json.loads(triage_path.read_text()) if triage_path.exists() else []

    create_tables()
    with SessionLocal.begin() as session:
        result = seed_demo(session, data, triage)
        flags = list(session.scalars(select(Flag)))
        patterns = active_patterns(flags, clock.now(), DEFAULT_PARAMS)

    print(f"Seeded from {path}")
    for table, count in result.rows.items():
        print(f"  {table:<16} {count}")
    statuses = Counter(str(flag.status) for flag in flags)
    print(f"Flags: {len(flags)} ({', '.join(f'{n} {s}' for s, n in sorted(statuses.items()))})")
    print(f"Repeat patterns: {len(patterns)}")

    seed_as_of = data.get("as_of")
    if seed_as_of and datetime.fromisoformat(seed_as_of) != clock.now():
        print(
            f"Warning: data is as of {seed_as_of} but the rules will use {clock.now().isoformat()} as now; "
            "unset AS_OF or set it to the data's as_of.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main(sys.argv[1:])
