from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import get_or_create_profile, update_profile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.post("", response_model=ProfileRead)
def create_or_load_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    return get_or_create_profile(db, payload.user_id)


@router.patch("/{user_id}", response_model=ProfileRead)
def patch_profile(user_id: str, payload: ProfileUpdate, db: Session = Depends(get_db)):
    return update_profile(db, user_id, payload)
