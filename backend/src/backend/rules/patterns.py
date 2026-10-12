"""Repeat patterns: the same rule firing for the same person, in the same role, several times recently.

Computed when read, never stored: a pattern depends on "now" (flags age out of the window, so
patterns expire on their own) and on triage (dismissed flags do not count).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.models import Flag, FlagRole, FlagStatus, RuleKey
from backend.rules.params import RuleParams


@dataclass(frozen=True)
class RepeatPattern:
    person_id: int
    role: FlagRole
    rule_key: RuleKey
    window_days: int
    count: int
    pr_ids: tuple[int, ...]


def _window(rule_key: RuleKey, params: RuleParams) -> tuple[int, int]:
    """(window in days, flags needed inside it) for a rule."""
    if rule_key == RuleKey.self_approval:
        return params.self_approval_pattern_window_days, params.self_approval_pattern_min_count
    return params.pattern_window_days, params.pattern_min_count


def active_patterns(flags: Iterable[Flag], now: datetime, params: RuleParams) -> list[RepeatPattern]:
    """Patterns among person-level, non-dismissed flags whose occurred_at is inside the rule's window.

    A flag exactly `window_days` old still counts; flags after `now` have not happened yet.
    Sorted by person, role and rule.
    """
    groups: dict[tuple[int, FlagRole, RuleKey], list[Flag]] = {}
    for flag in flags:
        if flag.person_id is None or flag.status == FlagStatus.dismissed:
            continue
        groups.setdefault((flag.person_id, flag.role, flag.rule_key), []).append(flag)

    patterns = []
    for (person_id, role, rule_key), group in sorted(groups.items()):
        window_days, needed = _window(rule_key, params)
        since = now - timedelta(days=window_days)
        inside = [f for f in group if since <= f.occurred_at <= now]
        if len(inside) >= needed:
            patterns.append(RepeatPattern(
                person_id=person_id, role=role, rule_key=rule_key, window_days=window_days,
                count=len(inside), pr_ids=tuple(sorted(f.pr_id for f in inside)),
            ))
    return patterns
