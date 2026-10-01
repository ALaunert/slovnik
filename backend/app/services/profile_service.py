from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserProfile
from app.schemas import ProfileUpdate
from app.learner_time import allocation_window, request_timezone
from app.repositories.practice import PracticeRepository


def get_or_create_profile(db: Session, user_id: str) -> UserProfile:
    profile = db.get(UserProfile, user_id)
    if profile:
        return profile
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user_id: str, update: ProfileUpdate) -> UserProfile:
    get_or_create_profile(db, user_id)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id)
                        .with_for_update().execution_options(populate_existing=True))
    now = PracticeRepository(db).database_now()
    for field, value in update.model_dump(exclude_unset=True, exclude_none=True).items():
        if field == "timezone":
            request_timezone(profile, value, now)
        else:
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def public_profile(db: Session, profile: UserProfile):
    window = allocation_window(profile, PracticeRepository(db).database_now())
    return {"user_id": profile.user_id, "preferred_level": profile.preferred_level,
            "daily_new_word_count": profile.daily_new_word_count, "ui_language": profile.ui_language,
            "timezone": profile.timezone, "effective_timezone": window.zone,
            "allocation_window": window.payload()}
