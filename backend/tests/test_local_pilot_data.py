import pytest
from sqlalchemy import select

import test_local_practice_api as pilot_tests
import test_reviewed_pilot_publication as publication_tests
from app.domain_models.practice import ActivityInstanceModel, LearningEventModel, PracticeRunModel
from app.domain_models.progress import LearnerTargetStateModel
from app.models import UserProfile

pilot_client = pilot_tests.pilot_client
postgresql_publication_engine = publication_tests.postgresql_publication_engine


def test_local_deletion_removes_raw_and_derived_pilot_records_and_preserves_profile(pilot_client, db_session):
    from app.local_pilot_data import delete_local_practice
    run_id, _ = pilot_tests.start(pilot_client)
    activity = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{activity['id']}/responses",
                      json={"idempotency_key": "raw", "response": "private test answer"})
    db_session.add(UserProfile(user_id="unrelated"))
    db_session.commit()
    inventory = delete_local_practice(db_session, "pilot-test")
    assert inventory["events"] == inventory["activities"] == inventory["states"] == inventory["runs"] == 1
    assert db_session.scalar(select(LearningEventModel)) is not None
    assert delete_local_practice(db_session, "pilot-test", execute=True) == inventory
    for model in (ActivityInstanceModel, LearningEventModel, LearnerTargetStateModel, PracticeRunModel):
        assert db_session.scalar(select(model)) is None
    assert db_session.get(UserProfile, "pilot-test") is not None
    assert db_session.get(UserProfile, "unrelated") is not None
    assert delete_local_practice(db_session, "pilot-test", execute=True)["runs"] == 0


def test_local_deletion_refuses_non_neutral_projection_before_mutation(pilot_client, db_session):
    from app.local_pilot_data import delete_local_practice
    run_id, _ = pilot_tests.start(pilot_client)
    activity = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{activity['id']}/responses",
                      json={"idempotency_key": "raw", "response": "unknown"})
    state = db_session.scalar(select(LearnerTargetStateModel))
    state.baseline_kind = "legacy_bootstrap"
    db_session.commit()
    with pytest.raises(ValueError, match="shared|baseline"):
        delete_local_practice(db_session, "pilot-test", execute=True)
    assert db_session.scalar(select(LearningEventModel)) is not None


@pytest.mark.parametrize("mode,flag", [("production", True), ("test", False)])
def test_local_data_operator_fails_closed(pilot_client, db_session, monkeypatch, mode, flag):
    from app.config import settings
    from app.local_pilot_data import delete_local_practice
    monkeypatch.setattr(settings, "environment", mode)
    monkeypatch.setattr(settings, "local_pilot_enabled", flag)
    with pytest.raises(ValueError, match="local pilot"):
        delete_local_practice(db_session, "pilot-test", execute=True)


def test_postgresql_local_erasure_with_linked_repair_preserves_legacy_data(postgresql_publication_engine, monkeypatch):
    from datetime import datetime, timezone
    from uuid import uuid4
    from sqlalchemy.orm import Session
    from app.config import settings
    from app.local_pilot_data import delete_local_practice
    from app.models import UserWordProgress, VocabularyItem
    from app.services.reviewed_pilot_publication_service import ContentPublicationService
    from app.services.local_practice_service import LocalPracticeService
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    monkeypatch.setattr(settings, "local_pilot_enabled", True)
    with Session(postgresql_publication_engine) as session:
        session.add(UserProfile(user_id="erase-test"))
        word = VocabularyItem(serbian_cyrillic="вода", serbian_latin="voda", russian_translation="вода", cefr_level="A1", theme="daily")
        session.add(word)
        session.commit()
        session.add(UserWordProgress(user_id="erase-test", word_id=word.id, status="seen"))
        session.commit()
        ContentPublicationService(session).publish(load_reviewed_pilot_bundle(pilot_tests.PACK),
                                                   published_at=datetime.now(timezone.utc))
        service = LocalPracticeService(session)
        run_id = str(uuid4())
        service.create_or_resume("erase-test", run_id)
        parent = service.next_activity("erase-test", run_id)["activity"]
        service.submit("erase-test", parent["id"], idempotency_key="first", response="")
        child = service.repair("erase-test", parent["id"], retry_id=str(uuid4()), support="reveal")
        service.submit("erase-test", child["id"], idempotency_key="repair", response=child["support"]["example"]["answer"])
        result = delete_local_practice(session, "erase-test", execute=True)
        assert result["activities"] == result["events"] == 2
        assert session.scalar(select(LearningEventModel)) is None
        assert session.scalar(select(LearnerTargetStateModel)) is None
        assert session.scalar(select(UserWordProgress)) is not None
        assert session.scalar(select(VocabularyItem)) is not None
        assert session.get(UserProfile, "erase-test") is not None
