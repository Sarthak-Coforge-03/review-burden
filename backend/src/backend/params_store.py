"""The rule parameters in effect: the defaults, with any overrides saved from Settings applied."""

from dataclasses import fields, replace

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import RuleParamOverride
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.schemas import RuleSettings

_FIELDS = {f.name for f in fields(RuleParams)}


def to_settings(params: RuleParams) -> RuleSettings:
    return RuleSettings(**{name: getattr(params, name) for name in _FIELDS} | {"stock_phrases": params.stock_phrases})


def from_settings(settings: RuleSettings) -> RuleParams:
    return RuleParams(**settings.model_dump() | {"stock_phrases": frozenset(settings.stock_phrases)})


def load_params(session: Session) -> RuleParams:
    """Saved overrides on top of the defaults. Overrides for parameters that no longer exist are ignored."""
    overrides = {o.name: o.value for o in session.scalars(select(RuleParamOverride)) if o.name in _FIELDS}
    if "stock_phrases" in overrides:
        overrides["stock_phrases"] = frozenset(overrides["stock_phrases"])
    return replace(DEFAULT_PARAMS, **overrides)


def save_params(session: Session, params: RuleParams) -> None:
    """Store whatever differs from the defaults, replacing earlier overrides. Flushes; the caller commits."""
    session.execute(delete(RuleParamOverride))
    for name in sorted(_FIELDS):
        value = getattr(params, name)
        if value != getattr(DEFAULT_PARAMS, name):
            session.add(RuleParamOverride(name=name, value=sorted(value) if isinstance(value, frozenset) else value))
    session.flush()
