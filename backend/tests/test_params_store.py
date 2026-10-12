"""Saving and loading rule parameters. Each test's session is rolled back when it closes."""

from dataclasses import fields, replace

from sqlalchemy import select

from backend.models import RuleParamOverride
from backend.params_store import from_settings, load_params, save_params, to_settings
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.schemas import RuleSettings
from backend.seed import load_seed


def stored(session) -> dict:
    return {o.name: o.value for o in session.scalars(select(RuleParamOverride))}


def test_defaults_when_nothing_is_saved(session):
    assert load_params(session) == DEFAULT_PARAMS


def test_only_changed_values_are_stored_and_they_round_trip(session):
    params = replace(DEFAULT_PARAMS, rubber_stamp_min_lines=500, stock_phrases=frozenset({"lgtm", "nice"}))
    save_params(session, params)
    assert stored(session) == {"rubber_stamp_min_lines": 500, "stock_phrases": ["lgtm", "nice"]}
    assert load_params(session) == params


def test_saving_again_replaces_earlier_overrides(session):
    save_params(session, replace(DEFAULT_PARAMS, rubber_stamp_min_lines=500))
    save_params(session, replace(DEFAULT_PARAMS, stale_after_hours=24))
    assert stored(session) == {"stale_after_hours": 24}
    save_params(session, DEFAULT_PARAMS)
    assert stored(session) == {}


def test_overrides_for_unknown_parameters_are_ignored(session):
    session.add(RuleParamOverride(name="retired_threshold", value=3))
    session.flush()
    assert load_params(session) == DEFAULT_PARAMS


def test_settings_schema_covers_every_parameter():
    assert set(RuleSettings.model_fields) == {f.name for f in fields(RuleParams)}
    assert from_settings(to_settings(DEFAULT_PARAMS)) == DEFAULT_PARAMS


def test_reseeding_clears_saved_settings(session, seed_data):
    save_params(session, replace(DEFAULT_PARAMS, stale_after_hours=24))
    load_seed(session, seed_data)
    assert stored(session) == {}
