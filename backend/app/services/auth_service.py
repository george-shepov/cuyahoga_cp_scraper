"""
Auth service: bcrypt password verification + TOTP (RFC 6238) + JWT issuance.

Credentials are loaded exclusively from environment variables — nothing is
hard-coded in source.  Required env vars:
  ADMIN_USERNAME        – the login username  (e.g. "brockler")
  ADMIN_PASSWORD_HASH   – bcrypt hash of the password
  ADMIN_TOTP_SECRET     – base-32 TOTP secret for Google Authenticator
  JWT_SECRET_KEY        – random 32-byte hex secret for signing JWTs
  JWT_ALGORITHM         – (optional, default HS256)
  JWT_EXPIRE_MINUTES    – (optional, default 480 = 8 hours)

Run  python scripts/setup_admin_auth.py  once to generate all four values.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── env-driven config ────────────────────────────────────────────────────────
def _require_env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Environment variable {key!r} is not set. "
            "Run scripts/setup_admin_auth.py to generate credentials."
        )
    return val


def _get_jwt_secret() -> str:
    return _require_env("JWT_SECRET_KEY")


def _get_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def _get_expire_minutes() -> int:
    return int(os.getenv("JWT_EXPIRE_MINUTES", "480"))


# ── password ──────────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


# ── TOTP ──────────────────────────────────────────────────────────────────────
def verify_totp(code: str) -> bool:
    """Verify a 6-digit TOTP code using the server-side secret.

    Accepts the current window ±1 to tolerate minor clock skew.
    """
    secret = _require_env("ADMIN_TOTP_SECRET")
    totp = pyotp.TOTP(secret)
    # valid=True means code matches current or adjacent window
    return totp.verify(code, valid_window=1)


# ── credentials ───────────────────────────────────────────────────────────────
def check_credentials(username: str, password: str, totp_code: str) -> bool:
    """Return True only when username, password, AND TOTP are all correct."""
    expected_user = _require_env("ADMIN_USERNAME")
    expected_hash = _require_env("ADMIN_PASSWORD_HASH")
    if username.strip() != expected_user:
        return False
    if not verify_password(password, expected_hash):
        return False
    if not verify_totp(totp_code):
        return False
    return True


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_get_expire_minutes())
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_get_algorithm())


def decode_access_token(token: str) -> Optional[str]:
    """Return the username from a valid token, or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, _get_jwt_secret(), algorithms=[_get_algorithm()]
        )
        return payload.get("sub")
    except JWTError:
        return None
