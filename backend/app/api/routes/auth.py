"""Auth endpoints: login (password + optional TOTP) → JWT."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.auth_service import check_credentials, create_access_token, totp_enabled

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str = ""  # optional — only checked when ADMIN_TOTP_SECRET is set


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthConfigResponse(BaseModel):
    totp_required: bool


@router.get("/auth/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    """Return whether TOTP is required.  Frontend uses this to show/hide the field."""
    return AuthConfigResponse(totp_required=totp_enabled())


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    """Authenticate with username + password (+ TOTP if configured)."""
    if not check_credentials(body.username, body.password, body.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials" + (" or authenticator code" if totp_enabled() else "") + ".",
        )
    token = create_access_token(body.username)
    return TokenResponse(access_token=token)
