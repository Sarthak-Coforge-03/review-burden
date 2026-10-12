"""Repeat patterns: unit cases on in-memory flags, then the planted patterns in the seeded data."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend import clock
from backend.models import Flag, FlagRole, FlagStatus, RuleKey
from backend.rules.engine import run_engine
from backend.rules.params import DEFAULT_PARAMS
from backend.rules.patterns import RepeatPattern, active_patterns

NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
D = timedelta(days=1)
S = timedelta(seconds=1)
OMAR, JIN = 4, 7


def flag(
    ago: timedelta,
    pr_id: int,
    *,
    rule: RuleKey = RuleKey.rubber_stamp,
    person: int | None = OMAR,
    role: FlagRole | None = FlagRole.reviewer,
    status: FlagStatus = FlagStatus.open,
) -> Flag:
    return Flag(rule_key=rule, pr_id=pr_id, person_id=person, role=role, occurred_at=NOW - ago, evidence={}, status=status)


def stamps(*days_ago: float) -> list[Flag]:
    return [flag(d * D, pr_id=100 + i) for i, d in enumerate(days_ago)]


def test_three_in_the_window_is_a_pattern():
    [pattern] = active_patterns(stamps(1, 10, 29), NOW, DEFAULT_PARAMS)
    assert pattern == RepeatPattern(OMAR, FlagRole.reviewer, RuleKey.rubber_stamp, 30, 3, (100, 101, 102))


def test_two_is_not_enough():
    assert not active_patterns(stamps(1, 10), NOW, DEFAULT_PARAMS)


def test_window_edge_is_inclusive():
    assert active_patterns(stamps(1, 2, 30), NOW, DEFAULT_PARAMS)
    assert not active_patterns([*stamps(1, 2), flag(30 * D + S, 200)], NOW, DEFAULT_PARAMS)


def test_patterns_expire_as_time_passes():
    flags = stamps(1, 10, 29)
    assert active_patterns(flags, NOW, DEFAULT_PARAMS)
    assert not active_patterns(flags, NOW + 2 * D, DEFAULT_PARAMS)


def test_flags_after_now_have_not_happened_yet():
    assert not active_patterns([*stamps(1, 2), flag(-S, 200)], NOW, DEFAULT_PARAMS)


def test_dismissed_flags_do_not_count_but_acknowledged_ones_do():
    flags = stamps(1, 2, 3)
    flags[0].status = FlagStatus.dismissed
    assert not active_patterns(flags, NOW, DEFAULT_PARAMS)

    flags[0].status = FlagStatus.acknowledged
    assert active_patterns(flags, NOW, DEFAULT_PARAMS)


def test_self_approval_needs_two_within_fourteen_days():
    def self_approvals(*days_ago):
        return [flag(d * D, 300 + i, rule=RuleKey.self_approval, person=JIN, role=FlagRole.author)
                for i, d in enumerate(days_ago)]

    [pattern] = active_patterns(self_approvals(1, 14), NOW, DEFAULT_PARAMS)
    assert (pattern.window_days, pattern.count) == (14, 2)
    assert not active_patterns(self_approvals(1, 15), NOW, DEFAULT_PARAMS)


def test_different_rules_and_people_are_counted_separately():
    flags = [
        *stamps(1, 2),
        flag(3 * D, 200, rule=RuleKey.escape),
        flag(4 * D, 201, person=JIN),
    ]
    assert not active_patterns(flags, NOW, DEFAULT_PARAMS)


def test_team_level_flags_are_ignored():
    team = [flag(d * D, None, rule=RuleKey.load_concentration, person=None, role=None) for d in (1, 2, 3)]
    assert not active_patterns(team, NOW, DEFAULT_PARAMS)


# ---------------------------------------------------------------- seeded data (patterns with triage: test_expected_flags)

def test_without_the_dismissal_omar_has_four_stamps_in_the_window(session):
    run_engine(session)
    patterns = active_patterns(session.scalars(select(Flag)), clock.now(), DEFAULT_PARAMS)
    [omar] = [p for p in patterns if p.person_id == OMAR]
    assert omar.pr_ids == (151, 188, 209, 247)
