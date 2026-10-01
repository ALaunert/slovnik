"""Local operator inventory/deletion; no unauthenticated export or erasure HTTP route."""

import argparse
import json

from sqlalchemy import delete, select

from app.config import settings
from app.db import SessionLocal
from app.domain_models.practice import ActivityInstanceModel, LearningEventModel, PracticeRunModel
from app.domain_models.progress import LearnerTargetStateModel
from app.models import UserProfile
from app.services.local_workload import LOCAL_POLICIES


def delete_local_practice(session, learner_id, *, execute=False):
    if not settings.local_pilot_enabled or settings.environment.strip().casefold() not in {"local", "development", "test"}:
        raise ValueError("Explicit local pilot environment required")
    profile = select(UserProfile).where(UserProfile.user_id == learner_id)
    session.scalar(profile.with_for_update() if execute else profile)
    query = select(PracticeRunModel).where(PracticeRunModel.learner_id == learner_id,
                                         PracticeRunModel.selection_policy_version.in_(LOCAL_POLICIES),
                                         PracticeRunModel.legacy_quiz_attempt_id.is_(None))
    runs = tuple(session.scalars(query.with_for_update() if execute else query))
    run_ids = tuple(run.id for run in runs)
    activities = tuple(session.scalars(select(ActivityInstanceModel).where(ActivityInstanceModel.practice_run_id.in_(run_ids))))
    targets = tuple({activity.target_key for activity in activities})
    events = tuple(session.scalars(select(LearningEventModel).where(LearningEventModel.practice_run_id.in_(run_ids))))
    states = tuple(session.scalars(select(LearnerTargetStateModel).where(
        LearnerTargetStateModel.learner_id == learner_id, LearnerTargetStateModel.target_key.in_(targets))))
    shared = session.scalar(select(ActivityInstanceModel.id).join(PracticeRunModel).where(
        PracticeRunModel.learner_id == learner_id, ActivityInstanceModel.target_key.in_(targets),
        ActivityInstanceModel.practice_run_id.not_in(run_ids)).limit(1))
    if shared or any(state.baseline_kind != "neutral" for state in states):
        raise ValueError("Target has shared non-pilot history or non-neutral baseline; deletion requires a reviewed replay plan")
    result = {"schema_version": 1, "runs": len(runs), "activities": len(activities),
              "events": len(events), "states": len(states)}
    if execute:
        session.execute(delete(LearnerTargetStateModel).where(LearnerTargetStateModel.id.in_(tuple(state.id for state in states))))
        session.execute(delete(LearningEventModel).where(LearningEventModel.practice_run_id.in_(run_ids)))
        session.execute(delete(ActivityInstanceModel).where(ActivityInstanceModel.practice_run_id.in_(run_ids)))
        session.execute(delete(PracticeRunModel).where(PracticeRunModel.id.in_(run_ids)))
        session.commit()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("learner_id")
    parser.add_argument("--execute", action="store_true", help="Delete only inventoried local pilot history")
    args = parser.parse_args()
    with SessionLocal() as session:
        print(json.dumps(delete_local_practice(session, args.learner_id, execute=args.execute)))


if __name__ == "__main__":
    main()
