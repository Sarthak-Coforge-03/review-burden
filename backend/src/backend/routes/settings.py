from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.deps import ManagerDep, ParamsDep, SessionDep
from backend.models import Developer, Flag, FlagStatus, Role
from backend.params_store import from_settings, save_params, to_settings
from backend.rules.engine import run_engine
from backend.rules.params import DEFAULT_PARAMS, RuleParams
from backend.schemas import EngineRun, RuleSettings, SettingsOut, SettingsSaved

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _run(session: Session, params: RuleParams) -> EngineRun:
    result = run_engine(session, params=params)
    open_flags = session.scalar(select(func.count()).select_from(Flag).where(Flag.status == FlagStatus.open))
    return EngineRun(
        created=result.created, updated=result.updated, removed=result.removed,
        kept_triaged=result.kept_triaged, open_flags=open_flags,
    )


def _save_and_run(session: Session, params: RuleParams) -> SettingsSaved:
    save_params(session, params)
    engine = _run(session, params)
    session.commit()
    return SettingsSaved(values=to_settings(params), defaults=to_settings(DEFAULT_PARAMS), engine=engine)


@router.get("")
def get_settings(_manager: ManagerDep, params: ParamsDep) -> SettingsOut:
    """The rule thresholds and health score weights in effect, and their defaults. Manager only."""
    return SettingsOut(values=to_settings(params), defaults=to_settings(DEFAULT_PARAMS))


@router.put("")
def save_settings(settings: RuleSettings, session: SessionDep, _manager: ManagerDep) -> SettingsSaved:
    """Save every setting and re-run the rules with them. Manager only."""
    developers = set(session.scalars(select(Developer.id).where(Developer.role == Role.dev)))
    unknown = [i for i in settings.load_dedicated_reviewers if i not in developers]
    if unknown:
        raise HTTPException(422, [{
            "type": "value_error",
            "loc": ["body", "load_dedicated_reviewers"],
            "msg": f"Value error, {', '.join(map(str, unknown))} "
            + ("is not a developer" if len(unknown) == 1 else "are not developers"),
        }])
    return _save_and_run(session, from_settings(settings))


@router.delete("")
def reset_settings(session: SessionDep, _manager: ManagerDep) -> SettingsSaved:
    """Go back to the defaults and re-run the rules. Manager only."""
    return _save_and_run(session, DEFAULT_PARAMS)


@router.post("/run-engine")
def rerun_engine(session: SessionDep, _manager: ManagerDep, params: ParamsDep) -> EngineRun:
    """Re-run the rules with the current settings, as of now. Manager only."""
    engine = _run(session, params)
    session.commit()
    return engine
