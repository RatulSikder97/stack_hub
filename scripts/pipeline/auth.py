"""Authentication for the local web panel.

Two roles:
    * ``admin``  — full access including the admin file editor.
    * ``user``   — pipeline access (Studio / Library / Translate) but no admin.

Credentials live in ``.env`` (plain or pre-hashed). Sessions are signed
HttpOnly cookies via ``itsdangerous`` — no DB, no JWT, no token refresh.
Localhost-only by default; turn off auth entirely with ``AUTH_DISABLED=true``
during dev if you need to bypass the login screen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import bcrypt
from dotenv import load_dotenv
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Load .env once at import so ADMIN_PASSWORD / USER_PASSWORD / AUTH_SECRET
# are visible via os.environ. pydantic-settings does not push into env.
try:
    from pipeline.paths import ENV_PATH as _ENV_PATH

    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:  # noqa: BLE001 — don't fail import if paths unavailable
    pass

Role = Literal["admin", "user"]
COOKIE_NAME = "stack_hub_session"
DEFAULT_SESSION_DAYS = 30


def _hash_password(plain: str) -> str:
    """Bcrypt hash; truncate to 72 bytes per bcrypt spec."""
    raw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, stored_hash: str) -> bool:
    raw = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(raw, stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class User:
    username: str
    role: Role


class AuthError(Exception):
    """Raised when login fails or session is invalid/expired."""


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def _load_credentials() -> dict[str, tuple[str, Role]]:
    """Build a username → (password_hash, role) map from environment.

    Supports either ``ADMIN_PASSWORD`` (plain, will be hashed once at load)
    or ``ADMIN_PASSWORD_HASH`` (bcrypt). Same for ``USER_*``.
    """
    creds: dict[str, tuple[str, Role]] = {}

    admin_user = (os.environ.get("ADMIN_USERNAME") or "admin").strip()
    admin_hash = (os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()
    admin_plain = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    if admin_hash:
        creds[admin_user] = (admin_hash, "admin")
    elif admin_plain:
        creds[admin_user] = (_hash_password(admin_plain), "admin")
    else:
        # Sensible localhost default so the app boots; .env.example warns.
        creds[admin_user] = (_hash_password("admin"), "admin")

    user_user = (os.environ.get("USER_USERNAME") or "user").strip()
    user_hash = (os.environ.get("USER_PASSWORD_HASH") or "").strip()
    user_plain = (os.environ.get("USER_PASSWORD") or "").strip()
    if user_hash:
        creds[user_user] = (user_hash, "user")
    elif user_plain:
        creds[user_user] = (_hash_password(user_plain), "user")

    return creds


def _serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("AUTH_SECRET") or "stack-hub-default-localhost-secret"
    return URLSafeTimedSerializer(secret, salt="stack-hub-session")


def _max_age_seconds() -> int:
    days_raw = os.environ.get("AUTH_SESSION_DAYS") or str(DEFAULT_SESSION_DAYS)
    try:
        days = int(days_raw)
    except ValueError:
        days = DEFAULT_SESSION_DAYS
    return max(1, days) * 86400


def auth_disabled() -> bool:
    return (os.environ.get("AUTH_DISABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str) -> User:
    """Verify credentials. Raises ``AuthError`` on failure."""
    creds = _load_credentials()
    record = creds.get(username.strip())
    if record is None:
        raise AuthError("invalid credentials")
    password_hash, role = record
    if not _verify_password(password, password_hash):
        raise AuthError("invalid credentials")
    return User(username=username.strip(), role=role)


def encode_session(user: User) -> str:
    """Serialize the user into a signed token suitable for a cookie."""
    return _serializer().dumps({"u": user.username, "r": user.role})


def decode_session(token: str) -> User:
    """Validate a session token. Raises AuthError if invalid or expired."""
    try:
        payload = _serializer().loads(token, max_age=_max_age_seconds())
    except SignatureExpired as exc:
        raise AuthError("session expired") from exc
    except BadSignature as exc:
        raise AuthError("invalid session") from exc
    if not isinstance(payload, dict):
        raise AuthError("invalid session payload")
    role = payload.get("r")
    if role not in {"admin", "user"}:
        raise AuthError("invalid role")
    return User(username=str(payload.get("u", "")), role=role)


def list_known_usernames() -> list[str]:
    """For diagnostics only — never expose hashes."""
    return sorted(_load_credentials().keys())
