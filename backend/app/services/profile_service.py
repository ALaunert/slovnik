from sqlalchemy.orm import Session

from app.models import UserProfile
from app.schemas import ProfileUpdate


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
    profile = get_or_create_profile(db, user_id)
    for field, value in update.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
