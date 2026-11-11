"""Authentication: JWT (PyJWT) + PBKDF2 password hashing (stdlib, no
bcrypt dependency). GitHub OAuth flow is real: /github/login redirects
to github.com, /github/callback exchanges the code for a token.
Demo login: demo@codesentry.dev / demo1234 (seeded by /api/demo/seed).
Set CODESENTRY_JWT_SECRET in production — the dev default is only for
local demo and is documented as insecure in README/SECURITY.md.
"""
from __future__ import annotations
import hashlib, hmac, secrets, datetime as dt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database.models import User
from database.session import get_db
from settings import settings

_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return h.hex(), salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    h, _ = hash_password(password, salt)
    return hmac.compare_digest(h, stored_hash)

def create_token(user: User) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user.id), "email": user.email, "role": user.role,
               "exp": now + dt.timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
               "iat": now}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, settings.JWT_SECRET,
                             algorithms=[settings.JWT_ALGORITHM])
        user = db.query(User).filter_by(id=int(payload["sub"])).first()
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not user:
        raise HTTPException(401, "User not found")
    return user

def require_role(*roles: str):
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(403, f"Requires role: {roles}")
        return user
    return _check

def can_access_repo(user: User, repo) -> bool:
    if user.role == "admin":
        return True
    if repo.is_demo:
        return True
    return repo.owner_id == user.id

def can_admin_repo(user: User, repo) -> bool:
    if user.role == "admin":
        return True
    return repo.owner_id == user.id
