from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginIn, ProfilePatch, SignupIn, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    if not payload.name.strip():raise HTTPException(422,"Please enter your name")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        language="English",
        subjects=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/profile", response_model=UserOut)
def update_profile(
    payload: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        user.name = data["name"].strip()
    if "grade" in data and data["grade"] is not None:
        user.grade = data["grade"]
    if "language" in data and data["language"] is not None:
        user.language = data["language"]
    if "subjects" in data and data["subjects"] is not None:
        user.subjects = [s.strip() for s in data["subjects"] if s.strip()][:8]
    if "prefs" in data and data["prefs"] is not None:
        clean = {str(k): v for k, v in data["prefs"].items() if k in ("struggles", "weekly", "styles", "goals", "exam_date", "daily_minutes", "priorities", "timezone", "onboarded")}
        from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
        from datetime import date
        for key in ('goals','priorities'):
            if key in clean and (not isinstance(clean[key],str) or len(clean[key])>2000):raise HTTPException(422,f'{key} must be text under 2000 characters')
        if 'daily_minutes' in clean and (not isinstance(clean['daily_minutes'],int) or not 5<=clean['daily_minutes']<=480):raise HTTPException(422,'Daily study minutes must be between 5 and 480')
        if clean.get('exam_date'):
            try:date.fromisoformat(clean['exam_date'])
            except (ValueError,TypeError):raise HTTPException(422,'Exam date must be YYYY-MM-DD')
        if 'timezone' in clean:
            try:ZoneInfo(clean['timezone'])
            except (ZoneInfoNotFoundError,ValueError,TypeError):raise HTTPException(422,'Choose a valid IANA timezone')
        user.prefs = clean
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post('/logout',status_code=204)
def logout(user:User=Depends(get_current_user),db:Session=Depends(get_db),creds=Depends(__import__('app.deps',fromlist=['bearer']).bearer)):
    from ..models import RevokedToken
    from ..config import settings
    from datetime import datetime,timezone
    import jwt
    payload=jwt.decode(creds.credentials,settings.jwt_secret,algorithms=[settings.jwt_algorithm])
    db.add(RevokedToken(jti=payload['jti'],expires_at=datetime.fromtimestamp(payload['exp'],timezone.utc)))
    db.commit()
