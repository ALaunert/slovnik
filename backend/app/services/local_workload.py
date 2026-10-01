"""Fixed issuance limits in learner allocation windows; not efficacy estimates."""

from dataclasses import dataclass

from sqlalchemy import select

from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
from app.models import UserProfile
from app.learner_time import DayWindow, allocation_window

LEGACY_POLICY = "local-written-selector-v1"
POLICY = "local-written-selector-v2"
LOCAL_POLICIES = (LEGACY_POLICY, POLICY)


@dataclass(frozen=True)
class IssuedWindow:
    rows: tuple
    window: DayWindow

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)


@dataclass(frozen=True)
class LocalWorkloadPolicy:
    version: str = "written-local-budget-v2"
    total_limit: int = 8
    root_limit: int = 6
    new_limit: int = 2
    repair_limit: int = 2
    probe_limit: int = 0

    def __post_init__(self):
        if any(value < 0 for value in (self.total_limit, self.root_limit, self.new_limit,
                                       self.repair_limit, self.probe_limit)):
            raise ValueError("Workload limits cannot be negative")

    def rows(self, session, learner_id, now, *, lock=False):
        statement = select(UserProfile).where(UserProfile.user_id == learner_id).execution_options(populate_existing=True)
        profile = session.scalar(statement.with_for_update() if lock else statement)
        window = allocation_window(profile, now)
        rows = tuple(session.scalars(select(ActivityInstanceModel).join(PracticeRunModel).where(
            PracticeRunModel.learner_id == learner_id,
            PracticeRunModel.selection_policy_version.in_(LOCAL_POLICIES),
            ActivityInstanceModel.selected_at >= window.start,
            ActivityInstanceModel.selected_at < window.end,
        )))
        return IssuedWindow(rows, window)

    def report(self, rows):
        roots = [row for row in rows if row.retry_of_activity_instance_id is None]
        issued = {"total": len(rows), "root": len(roots),
                  "new": sum(row.learning_intent == "acquire" for row in roots),
                  "due": sum(row.learning_intent == "review" for row in roots),
                  "weak": sum(row.learning_intent == "strengthen" for row in roots),
                  "assessment": sum(row.learning_intent == "assess" for row in roots),
                  "repair": len(rows)-len(roots), "probe": 0}
        limits = {"total": self.total_limit, "root": self.root_limit, "new": self.new_limit,
                  "repair": self.repair_limit, "probe": self.probe_limit}
        return {"policy_version": self.version, "timezone": rows.window.zone, "window": rows.window.payload(),
                "issued": issued, "limits": limits,
                "remaining": {key: max(0, min(value-issued[key], self.total_limit-issued["total"]))
                              for key, value in limits.items()}}

    def reason(self, rows, *, repair=False):
        remaining = self.report(rows)["remaining"]
        if remaining["total"] == 0 or remaining["repair" if repair else "root"] == 0:
            return "daily_workload_budget_reached"
        return None
