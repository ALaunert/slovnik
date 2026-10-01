"""Local written-pilot adapter over the existing practice and selector contracts."""

from dataclasses import replace
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.curriculum_policy import CurriculumFrontierPolicy, FrontierAvailability
from app.domain.practice import (
    ActivityInstance, ActivityKind, ActivitySpec, ActivityStatus, CueLevel,
    Evaluation, EvaluationOutcome, EvaluationSource, ExerciseOperation,
    FeedbackSnapshot, GeneratorKind, HintKind, HintSnapshot, LearningEventRequest,
    PracticeRun, PracticeRunStatus, RepairOutcome,
    ResponseKind, ResponseSnapshot, ScorerKind, SelectionMetadata,
)
from app.domain.selection_policy import ActivityValidityPolicy
from app.domain.selection_ports import ActivityCandidate, CurriculumTarget
from app.domain.shared import Modality
from app.domain_models.catalog import LanguageConstruction
from app.domain_models.practice import ActivityInstanceModel, LearningEventModel, PracticeRunModel
from app.models import UserProfile
from app.repositories.catalog import CatalogRepository
from app.repositories.practice import PracticeRepository
from app.repositories.progress import ProgressRepository
from app.reviewed_example_bank import bank_digest, rights_digest
from app.services.answer_policy import ReviewedAnswerPolicy
from app.services.content_publication_service import ContentPublicationService
from app.services.learner_projection_service import LearnerProjectionService
from app.services.learning_event_service import LearningEventService
from app.services.next_activity_service import NextActivityService
from app.services.local_workload import LOCAL_POLICIES, POLICY, LocalWorkloadPolicy
from app.services.practice_service import (
    PracticeLifecycleConflict, PracticeRunNotFound, PracticeService,
)
from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
from app.services.shadow_selection_runtime import _HistoryPort, _ProgressPort


PACK = Path(__file__).resolve().parents[3] / "content/curricula/a1-pilot/publication-v1.json"
WORKLOAD = LocalWorkloadPolicy()
logger = logging.getLogger(__name__)
GENERATOR = "reviewed-written-v1"
SCORER = "reviewed-written-answers-v1"


class _EventSource:
    def __init__(self, session, repository):
        self.session, self.repository = session, repository

    def events_for_target(self, *, learner_id, target_key):
        rows = self.session.scalars(select(LearningEventModel).where(
            LearningEventModel.learner_id == learner_id,
            LearningEventModel.target_key == target_key,
        ).order_by(LearningEventModel.occurred_at, LearningEventModel.id))
        return tuple(self.repository.get_learning_event(row.learner_id, row.idempotency_key)
                     for row in rows)


class _Projector:
    def __init__(self, session, repository):
        self.projection = LearnerProjectionService(
            ProgressRepository(session), _EventSource(session, repository),
        )

    def project(self, event):
        self.projection.apply_event(event)


class _ReviewedFrontier:
    def __init__(self, session, bundle, run, excluded):
        self.session, self.bundle, self.run, self.excluded = session, bundle, run, excluded

    def active_frontier(self, profile):
        active = ContentPublicationService(self.session).active(self.bundle.curriculum.curriculum_code)
        if active is None or active.id != self.run.curriculum_version_id or active.id != self.bundle.curriculum.id:
            return None
        progress = _ProgressPort(self.session).states_for_targets(
            learner_id=profile.learner_id,
            target_keys=(node.target.target_key for node in active.nodes),
        )
        decisions = CurriculumFrontierPolicy().evaluate(
            active, states_by_target_key=progress, requested_level=profile.requested_level,
        )
        result = []
        for decision in decisions:
            node = decision.node
            row = self.session.get(LanguageConstruction, node.target.target_id)
            expected = next((item for item in self.bundle.constructions if item.id == node.target.target_id), None)
            if row is None or expected is None or row.status != "published" or row.revision != expected.revision:
                continue
            if CatalogRepository(self.session).get_construction(row.id) != expected:
                continue
            item = next(item for item in self.bundle.examples["examples"]
                        if item["role"] == "practice" and item["outcome_id"] == node.outcome_code)
            if item["id"] in self.excluded:
                continue
            result.append(CurriculumTarget(
                target_spec=node.target, priority=node.priority, outcome_code=node.outcome_code,
                hard_ready=decision.availability is FrontierAvailability.AVAILABLE,
                soft_ready_count=decision.soft_ready_count, content_published=True,
                stimulus_snapshot={"example": item, "catalog_revision": row.revision},
            ))
        return tuple(result)


class _ReviewedCandidates:
    def __init__(self, bundle):
        self.bundle = bundle

    def candidates_for(self, target):
        from app.domain.practice import _plain_json
        item = _plain_json(target.stimulus_snapshot["example"])
        ReviewedAnswerPolicy.from_reviewed_example(item, capability=target.target_spec.capability)
        # These are the original approved contextual tasks, with no new wording.
        operation = ExerciseOperation.COMPLETE if item["task"]["format"] == "form" else ExerciseOperation.TRANSFORM
        snapshot = {
            "snapshot_version": 2,
            "pack": {"id": self.bundle.curriculum.id, "revision": self.bundle.curriculum.version_number,
                     "bank_digest": bank_digest(self.bundle.examples), "rights_digest": rights_digest(self.bundle.sources)},
            "source": {key: next(source for source in self.bundle.sources["sources"]
                                 if source["id"] == item["source_id"])[key]
                       for key in ("id", "release", "checksum", "attribution")},
            "catalog_revision": target.stimulus_snapshot["catalog_revision"],
            "example_id": item["id"], "example_revision": item["revision"],
            "example_hash": item["content_hash"],
            "answer_policy_id": item["answer_policy"]["id"],
            "answer_policy_revision": item["answer_policy"]["revision"],
            "context_family_id": item["context_family"], "target_span": item["target_span"],
            "primary_capability": target.target_spec.capability.value,
            "operation": operation.value,
            "support_capture_complete": True, "context_history_complete": True,
            "support_before_first": False,
            "response_contract": {"kind": "text", "max_codepoints": 2000},
            "task": item["task"], "private_reviewed_example": item,
        }
        yield ActivityCandidate(
            activity_spec=ActivitySpec(
                target_spec=target.target_spec, activity_kind=ActivityKind.EXERCISE,
                operation=operation, cue_level=CueLevel.FULL, output_modality=Modality.WRITTEN,
                scorer_kind=ScorerKind.DETERMINISTIC, snapshot=snapshot,
            ), curriculum_target=target, generator_kind=GeneratorKind.CURATED,
            generator_version=GENERATOR, scorer_version=SCORER, feedback_policy_version="written-feedback-v1",
        )


class _PilotProfile:
    def __init__(self, session):
        self.session = session

    def get_profile(self, learner_id):
        profile = ProgressRepository(self.session).get_profile(learner_id)
        return replace(profile, daily_budget=max(1, WORKLOAD.new_limit)) if profile else None


class _PilotHistory(_HistoryPort):
    def __init__(self, session, now):
        super().__init__(session)
        self.now = now

    def first_acquired_target_keys(self, *, learner_id, started_at, ended_at):
        return tuple(row.target_key for row in WORKLOAD.rows(self._session, learner_id, self.now)
                     if row.retry_of_activity_instance_id is None and row.learning_intent == "acquire")


class LocalPracticeService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = PracticeRepository(session)
        self.lifecycle = PracticeService(self.repository)

    def _owned_run(self, learner_id, run_id):
        run = self.lifecycle.get_run(learner_id, run_id)
        if run.selection_policy_version not in LOCAL_POLICIES or run.legacy_quiz_attempt_id is not None:
            raise PracticeRunNotFound("Local practice run not found")
        return run

    def create_or_resume(self, learner_id, run_id):
        if self.repository.get_run(run_id) is not None:
            return self.resume(learner_id, run_id)
        if self.session.get(UserProfile, learner_id) is None:
            raise PracticeRunNotFound("Learner profile not found")
        bundle = load_reviewed_pilot_bundle(PACK)
        active = ContentPublicationService(self.session).active(bundle.curriculum.curriculum_code)
        if active is None or active.id != bundle.curriculum.id:
            raise PracticeLifecycleConflict("Reviewed local pack is not active")
        run = PracticeRun(
            id=run_id, learner_id=learner_id, curriculum_version_id=active.id,
            legacy_quiz_attempt_id=None, status=PracticeRunStatus.ACTIVE,
            selection_policy_version=POLICY, started_at=self.repository.database_now(), ended_at=None,
        )
        try:
            self.lifecycle.start_run(learner_id, run)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            if self.repository.get_run(run_id) is None:
                raise
        return self.resume(learner_id, run_id)

    def resume(self, learner_id, run_id):
        run = self._owned_run(learner_id, run_id)
        return {
            "schema_version": 1, "id": run.id, "status": run.status.value,
            "policy_version": run.selection_policy_version,
            "workload": WORKLOAD.report(WORKLOAD.rows(self.session, learner_id, self.repository.database_now())),
            "activities": [self.public_activity(item, learner_id)
                           for item in self.repository.list_activities(run.id)],
        }

    def next_activity(self, learner_id, run_id, *, kind="exercise"):
        self._owned_run(learner_id, run_id)
        self.session.scalar(select(UserProfile).where(UserProfile.user_id == learner_id).with_for_update())
        run = self.repository.lock_run(run_id)
        if run.status.is_terminal:
            raise PracticeLifecycleConflict("Practice run is terminal")
        activities = self.repository.list_activities(run_id)
        pending = next((item for item in activities if item.status is ActivityStatus.PENDING), None)
        if pending is not None:
            return self._next_result(learner_id, self.public_activity(pending, learner_id), None)
        now = self.repository.database_now()
        today = WORKLOAD.rows(self.session, learner_id, now)
        reason = "policy_retired" if run.selection_policy_version != POLICY else WORKLOAD.reason(today)
        if reason:
            self.session.commit()
            return self._next_result(learner_id, None, reason)
        bundle = load_reviewed_pilot_bundle(PACK)
        excluded = {item.spec.snapshot["example_id"] for item in activities}
        history = tuple(self.session.scalars(select(ActivityInstanceModel).join(PracticeRunModel).where(
            PracticeRunModel.learner_id == learner_id, PracticeRunModel.selection_policy_version.in_(LOCAL_POLICIES),
        )))
        excluded.update(row.spec_payload["snapshot"]["example_id"] for row in today)
        excluded.update(row.spec_payload["snapshot"]["example_id"] for row in history if row.status == "pending")
        seen = frozenset(row.target_key for row in history)
        selector = NextActivityService(
            profile_port=_PilotProfile(self.session),
            progress_port=_ProgressPort(self.session), history_port=_PilotHistory(self.session, now),
            curriculum_port=_ReviewedFrontier(self.session, bundle, run, excluded),
            candidate_provider=_ReviewedCandidates(bundle), validity_policy=ActivityValidityPolicy(),
        )
        decision = selector.select_next(learner_id=learner_id, now=now, fallback_invalid_intents=True,
                                        prefer_acquire=WORKLOAD.report(today)["issued"]["new"] == 0,
                                        seen_target_keys=seen,
                                        acquire_exhausted=WORKLOAD.report(today)["remaining"]["new"] == 0)
        if decision.activity_spec is None:
            self.session.commit()
            return self._next_result(learner_id, None, decision.decision_code.value)
        spec = decision.activity_spec
        snapshot = spec.to_payload()["snapshot"]
        snapshot["workload_policy"] = WORKLOAD.report(today)
        snapshot["selection_decision"] = decision.to_payload() | {"activity_spec": None}
        spec = replace(spec, snapshot=snapshot)
        if kind == "exposure":
            snapshot = spec.to_payload()["snapshot"]
            snapshot["operation"] = None
            snapshot["support_before_first"] = True
            spec = replace(spec, activity_kind=ActivityKind.EXPOSURE, operation=None,
                           output_modality=None, scorer_kind=None, snapshot=snapshot)
        activity = ActivityInstance(
            id=str(uuid4()), practice_run_id=run_id, spec=spec, learning_intent=decision.intent,
            sequence_number=1, retry_of_activity_instance_id=None, attempt_number=1,
            selection=SelectionMetadata(policy_version=POLICY, reasons=decision.reason_codes),
            generator_kind=GeneratorKind.CURATED, generator_version=GENERATOR,
            scorer_version=SCORER if spec.activity_kind is ActivityKind.EXERCISE else None,
            feedback_policy_version="written-feedback-v1", status=ActivityStatus.PENDING,
            selected_at=now, terminal_at=None,
        )
        issued = self.lifecycle.add_activity(learner_id, run_id, activity)
        self.session.commit()
        return self._next_result(learner_id, self.public_activity(issued, learner_id), None)

    def _next_result(self, learner_id, activity, reason):
        if reason:
            logger.info("Local written selection stopped", extra={"selection_policy": POLICY, "decision_code": reason})
        return {"activity": activity, "reason": reason,
                "workload": WORKLOAD.report(WORKLOAD.rows(self.session, learner_id, self.repository.database_now()))}

    def submit(self, learner_id, activity_id, *, idempotency_key, response):
        activity = self.repository.get_activity(activity_id)
        if activity is None:
            raise PracticeRunNotFound("Local practice activity not found")
        self._owned_run(learner_id, activity.practice_run_id)
        # Use the same profile -> run order as issuance; event FK locks must not invert it.
        self.session.scalar(select(UserProfile).where(UserProfile.user_id == learner_id).with_for_update())
        evaluation = None
        first_response = None
        if activity.spec.activity_kind is ActivityKind.EXPOSURE:
            if response is not None:
                raise ValueError("Exposure cannot accept an answer")
        else:
            if response is None:
                raise ValueError("Exercise requires a text answer")
            item = activity.spec.to_payload()["snapshot"]["private_reviewed_example"]
            decision = ReviewedAnswerPolicy.from_reviewed_example(
                item, capability=activity.spec.target_spec.capability,
            ).evaluate(response)
            evaluation = Evaluation(
                source=EvaluationSource.DETERMINISTIC, outcome=EvaluationOutcome(decision.verdict.value),
                error_tags=(decision.error_category,) if decision.error_category else (),
            )
            first_response = ResponseSnapshot(kind=ResponseKind.TEXT, value=response)
        request = LearningEventRequest(
            event_id=str(uuid4()), learner_id=learner_id, activity_instance_id=activity_id,
            idempotency_key=idempotency_key, occurred_at=self.repository.database_now(),
            first_response=first_response, evaluation=evaluation,
            hints=(HintSnapshot(kind=HintKind(activity.spec.snapshot["repair_support"]), sequence_number=1),)
            if activity.retry_of_activity_instance_id else (),
            feedback=FeedbackSnapshot(code="local_repair_support", delivered_at=activity.selected_at)
            if activity.retry_of_activity_instance_id else None,
            repair_outcome=self._repair_outcome(activity, evaluation, learner_id),
        )
        event = LearningEventService(
            self.session, repository=self.repository, projector=_Projector(self.session, self.repository),
        ).record(request)
        return self.public_result(event)

    @staticmethod
    def public_result(event):
        return {
            "event_id": event.event_id,
            "outcome": event.evaluation_outcome.value if event.evaluation_outcome else None,
            "first_response": event.first_response.value if event.first_response else None,
            "evidence_kind": (
                "repair" if event.repair_outcome is RepairOutcome.REPAIRED
                else "supported_retry" if event.hints
                else "first_answer" if event.first_response else "exposure"
            ),
        }

    def _event_for_activity(self, learner_id, activity_id):
        row = self.session.scalar(select(LearningEventModel).where(
            LearningEventModel.learner_id == learner_id,
            LearningEventModel.activity_instance_id == activity_id,
        ))
        return self.repository.get_learning_event(learner_id, row.idempotency_key) if row else None

    def _repair_outcome(self, activity, evaluation, learner_id):
        if not activity.retry_of_activity_instance_id or evaluation is None:
            return None
        parent = self._event_for_activity(learner_id, activity.retry_of_activity_instance_id)
        if parent is None or parent.evaluation_outcome is not EvaluationOutcome.INCORRECT:
            return None
        if evaluation.outcome is EvaluationOutcome.CORRECT:
            return RepairOutcome.REPAIRED
        if evaluation.outcome is EvaluationOutcome.INCORRECT:
            return RepairOutcome.NOT_REPAIRED
        return None

    def feedback(self, learner_id, activity_id):
        activity = self.repository.get_activity(activity_id)
        if activity is None:
            raise PracticeRunNotFound("Local practice activity not found")
        self._owned_run(learner_id, activity.practice_run_id)
        event = self._event_for_activity(learner_id, activity_id)
        if event is None or activity.spec.activity_kind is not ActivityKind.EXERCISE:
            raise PracticeLifecycleConflict("Feedback requires a saved first response")
        child = next((item for item in self.repository.list_activities(activity.practice_run_id)
                      if item.retry_of_activity_instance_id == activity.id), None)
        if activity.retry_of_activity_instance_id is None and event.evaluation_outcome in {
            EvaluationOutcome.INCORRECT, EvaluationOutcome.UNRESOLVED,
        }:
            if child is None or (child.status is ActivityStatus.PENDING
                                 and child.spec.snapshot.get("repair_support") == "cue"):
                raise PracticeLifecycleConflict("Reserve revealed support before displaying an answer")
        item = activity.spec.snapshot["private_reviewed_example"]
        return {
            "first_result": self.public_result(event),
            "instruction_ru": item["task"]["instruction_ru"],
            "error_tags": list(event.error_tags),
            "example": {"serbian": item["text"], "translation": item["translation"],
                        "answer": item["accepted_answers"][0]},
            "can_repair": activity.retry_of_activity_instance_id is None
            and event.evaluation_outcome in {EvaluationOutcome.INCORRECT, EvaluationOutcome.UNRESOLVED}
            and child is None,
        }

    def repair(self, learner_id, parent_id, *, retry_id, support):
        reference = self.repository.get_activity(parent_id)
        if reference is None:
            raise PracticeRunNotFound("Local practice activity not found")
        self._owned_run(learner_id, reference.practice_run_id)
        self.session.scalar(select(UserProfile).where(UserProfile.user_id == learner_id).with_for_update())
        run = self.repository.lock_run(reference.practice_run_id)
        parent = self.repository.lock_activity(parent_id)
        if run.status.is_terminal or parent.retry_of_activity_instance_id is not None:
            raise PracticeLifecycleConflict("Only one immediate repair is allowed")
        HintKind(support)
        activities = self.repository.list_activities(run.id)
        existing = next((item for item in activities if item.retry_of_activity_instance_id == parent_id), None)
        if existing is not None:
            if existing.id != retry_id or existing.spec.snapshot.get("repair_support") != support:
                raise PracticeLifecycleConflict("A different repair is already issued")
            return self.public_activity(existing, learner_id)
        if run.selection_policy_version != POLICY:
            raise PracticeLifecycleConflict("Retired policy cannot issue a repair; start a new run")
        now = self.repository.database_now()
        today = WORKLOAD.rows(self.session, learner_id, now)
        if WORKLOAD.reason(today, repair=True):
            raise PracticeLifecycleConflict("Daily repair workload budget reached")
        if any(item.status is ActivityStatus.PENDING for item in activities):
            raise PracticeLifecycleConflict("Finish the pending activity before repair")
        event = self._event_for_activity(learner_id, parent_id)
        if (event is None or parent.spec.activity_kind is not ActivityKind.EXERCISE
                or event.evaluation_outcome not in {EvaluationOutcome.INCORRECT, EvaluationOutcome.UNRESOLVED}):
            raise PracticeLifecycleConflict("Repair requires an incorrect or unresolved first answer")
        if self.repository.get_activity(retry_id) is not None:
            raise PracticeLifecycleConflict("Repair ID already belongs to another activity")
        bundle = load_reviewed_pilot_bundle(PACK)
        active = ContentPublicationService(self.session).active(bundle.curriculum.curriculum_code)
        expected = next((item for item in bundle.constructions if item.id == parent.target_spec.target_id), None)
        if (active is None or active.id != run.curriculum_version_id or active.id != bundle.curriculum.id
                or expected is None or CatalogRepository(self.session).get_construction(expected.id) != expected):
            raise PracticeLifecycleConflict("Retired or changed content cannot issue repair")
        snapshot = parent.spec.to_payload()["snapshot"]
        snapshot["workload_policy"] = WORKLOAD.report(today)
        snapshot["repair_support"] = support
        snapshot["support_before_first"] = True
        child = replace(parent.retry(
            retry_id=retry_id, sequence_number=self.repository.next_sequence_number(run.id),
            selected_at=now,
        ), spec=replace(parent.spec, snapshot=snapshot))
        self.repository.add_activity(run, child)
        self.session.commit()
        return self.public_activity(child, learner_id)

    def public_activity(self, activity, learner_id):
        snapshot = activity.spec.to_payload()["snapshot"]
        event = self._event_for_activity(learner_id, activity.id)
        item = snapshot["private_reviewed_example"]
        return {
            "id": activity.id, "kind": activity.spec.activity_kind.value,
            "operation": activity.spec.operation.value if activity.spec.operation else None,
            "cue_level": activity.spec.cue_level.value, "status": activity.status.value,
            "sequence_number": activity.sequence_number,
            "capability": activity.spec.target_spec.capability.value,
            "context_family": snapshot["context_family_id"],
            "task": {name: snapshot["task"][name] for name in ("input", "instruction_ru", "format")},
            "response_contract": snapshot["response_contract"] if activity.spec.operation else None,
            "presentation": {"serbian": item["text"], "translation": item["translation"]}
            if activity.spec.activity_kind is ActivityKind.EXPOSURE else None,
            "selection_reasons": activity.selection.to_payload(),
            "result": self.public_result(event) if event else None,
            "retry_of": activity.retry_of_activity_instance_id,
            "support": {
                "kind": snapshot["repair_support"], "instruction_ru": item["task"]["instruction_ru"],
                "example": {"serbian": item["text"], "translation": item["translation"],
                            "answer": item["accepted_answers"][0]}
                if snapshot["repair_support"] in {"reveal", "correction"} else None,
            } if activity.retry_of_activity_instance_id else None,
        }
