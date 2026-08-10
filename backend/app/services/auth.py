"""Small, explicit API-key authorization boundary for the single-tenant demo.

This is deliberately not a replacement for SSO/OIDC in a multi-user utility
environment.  It creates a safe deployment default: the public API can be
locked to an operator key while ingestion remains admin-only.
"""

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    role: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "ApiKey"})


def authenticate(api_key: Annotated[str | None, Security(_api_key_header)] = None) -> Principal:
    settings = get_settings()
    if not settings.auth_required:
        return Principal(role="local-development")

    if not settings.operator_api_key or not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="Authentication is required but operator/admin API keys are not configured.",
        )
    if not api_key:
        raise _unauthorized("An X-API-Key header is required.")
    if secrets.compare_digest(api_key, settings.admin_api_key):
        return Principal(role="admin")
    if secrets.compare_digest(api_key, settings.operator_api_key):
        return Principal(role="operator")
    raise _unauthorized("Invalid API key.")


def require_operator(principal: Principal = Depends(authenticate)) -> Principal:
    """Allow either an operator or an administrator."""
    return principal


def require_admin(principal: Principal = Depends(authenticate)) -> Principal:
    if principal.role not in {"admin", "local-development"}:
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return principal
