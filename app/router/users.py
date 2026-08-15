from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.deps import get_current_admin, get_current_user
from app.schema.user import AssignedCredentialOut, UserOut, UserRoleUpdate, UserStatusUpdate
from app.service.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    return UserService(db).list_users()


@router.patch("/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    # get_current_admin is the actual security boundary here -- this route
    # is unreachable at all unless the caller's own token proves they're
    # already an admin. See app/deps.py.
    return UserService(db).set_role(acting_admin=admin, target_user_id=user_id, is_admin=payload.is_admin)


@router.patch("/{user_id}/status", response_model=UserOut)
def update_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    return UserService(db).set_status(acting_admin=admin, target_user_id=user_id, is_active=payload.is_active)


@router.get("/me/credentials", response_model=list[AssignedCredentialOut])
def my_credentials(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return UserService(db).my_credentials(current_user.id)
