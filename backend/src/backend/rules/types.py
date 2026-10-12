from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.models import FlagRole, RuleKey


@dataclass(frozen=True)
class FlagCandidate:
    """What a rule found. The engine turns these into stored flags.

    `pr_id`, `person_id` and `role` are None for team-level flags (load_concentration).
    `occurred_at` is when the problem happened (merge, approval, request, fix opened); repeat
    patterns use it to decide whether a flag is inside their window.
    """

    rule_key: RuleKey
    pr_id: int | None
    person_id: int | None
    role: FlagRole | None
    occurred_at: datetime
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[RuleKey, int | None, int | None, FlagRole | None]:
        """Identity of a flag across engine runs; triage is keyed by this."""
        return (self.rule_key, self.pr_id, self.person_id, self.role)
