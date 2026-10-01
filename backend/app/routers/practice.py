from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.local_pilot import require_local_pilot
from app.services.learning_event_service import LearningEventConflict, LearningEventNotFound
from app.services.local_practice_service import LocalPracticeService
from app.services.practice_service import PracticeLifecycleConflict, PracticeRunNotFound


router = APIRouter(prefix="/api/practice", dependencies=[Depends(require_local_pilot)])


class NextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["exercise", "exposure"] = "exercise"


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=255)
    response: str | None = Field(default=None, max_length=2000)


class RepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_id: UUID
    support: Literal["cue", "reveal", "correction"]


def _call(action):
    try:
        return action()
    except (PracticeRunNotFound, LearningEventNotFound) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (PracticeLifecycleConflict, LearningEventConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/availability")
def availability():
    return {"schema_version": 1, "enabled": True}


@router.put("/{learner_id}/runs/{run_id}")
def create_or_resume(learner_id: str, run_id: UUID, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).create_or_resume(learner_id, str(run_id)))


@router.get("/{learner_id}/runs/{run_id}")
def resume(learner_id: str, run_id: UUID, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).resume(learner_id, str(run_id)))


@router.post("/{learner_id}/runs/{run_id}/next")
def next_activity(learner_id: str, run_id: UUID, body: NextRequest, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).next_activity(learner_id, str(run_id), kind=body.kind))


@router.post("/{learner_id}/activities/{activity_id}/responses")
def submit(learner_id: str, activity_id: UUID, body: AnswerRequest, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).submit(
        learner_id, str(activity_id), idempotency_key=body.idempotency_key, response=body.response,
    ))


@router.get("/{learner_id}/activities/{activity_id}/feedback")
def feedback(learner_id: str, activity_id: UUID, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).feedback(learner_id, str(activity_id)))


@router.post("/{learner_id}/activities/{activity_id}/repair")
def repair(learner_id: str, activity_id: UUID, body: RepairRequest, db: Session = Depends(get_db)):
    return _call(lambda: LocalPracticeService(db).repair(
        learner_id, str(activity_id), retry_id=str(body.retry_id), support=body.support,
    ))
