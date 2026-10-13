"""The rule parameters in effect: the defaults, with any overrides saved from Settings applied."""

from dataclasses import fields, replace

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import RuleParamOverride
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.schemas import RuleSettings

_FIELDS = {f.name for f in fields(RuleParams)}
# Set-valued parameters: frozensets in RuleParams, sorted lists in the API and the database.
_SETS = {name for name in _FIELDS if isinstance(getattr(DEFAULT_PARAMS, name), frozenset)}


def _as_sets(values: dict) -> dict:
    return {name: frozenset(value) if name in _SETS else value for name, value in values.items()}


def to_settings(params: RuleParams) -> RuleSettings:
    return RuleSettings(**{name: getattr(params, name) for name in _FIELDS})


def from_settings(settings: RuleSettings) -> RuleParams:
    return RuleParams(**_as_sets(settings.model_dump()))


def load_params(session: Session) -> RuleParams:
    """Saved overrides on top of the defaults. Overrides for parameters that no longer exist are ignored."""
    overrides = {o.name: o.value for o in session.scalars(select(RuleParamOverride)) if o.name in _FIELDS}
    return replace(DEFAULT_PARAMS, **_as_sets(overrides))


def save_params(session: Session, params: RuleParams) -> None:
    """Store whatever differs from the defaults, replacing earlier overrides. Flushes; the caller commits."""
    session.execute(delete(RuleParamOverride))
    for name in sorted(_FIELDS):
        value = getattr(params, name)
        if value != getattr(DEFAULT_PARAMS, name):
            session.add(RuleParamOverride(name=name, value=sorted(value) if isinstance(value, frozenset) else value))
    session.flush()
