"""Every threshold the rules use. Rules read these, never literals, so the settings page can change them."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuleParams:
    # rubber_stamp: an approval on a big PR that came too fast or with no substantive comment
    rubber_stamp_min_lines: int = 300
    rubber_stamp_max_seconds: int = 120

    # A comment is substantive if it is a line comment, at least this long, and not a stock phrase.
    substantive_min_chars: int = 30
    stock_phrases: frozenset[str] = field(
        default_factory=lambda: frozenset({"lgtm", "nit", "+1", "approved", "ship it", "looks good", "👍"})
    )

    # escape: a revert or hotfix opened within this many days of the original PR's merge
    escape_window_days: int = 14

    # stale_backlog: a review request still unanswered after this many hours
    stale_after_hours: int = 48

    # load_concentration: over the window, top two reviewers above this share, or anyone above multiple x median
    load_window_days: int = 28
    load_top2_share: float = 0.6
    load_median_multiple: float = 2.0
    # Developers whose job is reviewing: their reviews count toward neither the share nor the median.
    load_dedicated_reviewers: frozenset[int] = frozenset()

    # repeat_pattern: this many non-dismissed flags of one rule for one person and role inside the window
    pattern_window_days: int = 30
    pattern_min_count: int = 3
    self_approval_pattern_window_days: int = 14
    self_approval_pattern_min_count: int = 2

    # health score: a weighted average of five parts, each 0-100, over the last window
    health_window_days: int = 28
    health_weight_coverage: float = 0.25
    health_weight_depth: float = 0.25
    health_weight_escapes: float = 0.20
    health_weight_responsiveness: float = 0.15
    health_weight_load_balance: float = 0.15
    health_escape_rate_floor: float = 0.10  # an escape rate at or above this scores 0


DEFAULT_PARAMS = RuleParams()
