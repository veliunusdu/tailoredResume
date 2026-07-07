"""
JWT authentication using Clerk's JWKS endpoint.

Usage:
  Add `user_id: str = Depends(get_current_user)` to any FastAPI endpoint
  to require a valid Clerk JWT. The returned string is the Clerk user ID
  (e.g., "user_2abc...") which is used to scope all DB queries.

Environment Variables:
  CLERK_JWKS_URL  — JWKS endpoint from Clerk dashboard
                    e.g. https://YOUR_APP.clerk.accounts.dev/.well-known/jwks.json
"""
from __future__ import annotations

import os
import time
import httpx

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.logger import get_logger

_logger = get_logger(__name__)

# Cache the JWKS keys so we don't hit the network on every request
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0
_JWKS_TTL_SEC = 3600  # Re-fetch JWKS every hour

bearer_scheme = HTTPBearer(auto_error=False)


def _get_jwks() -> dict:
    """Fetch and cache Clerk's JSON Web Key Set."""
    global _jwks_cache, _jwks_fetched_at

    jwks_url = os.getenv("CLERK_JWKS_URL", "")
    if not jwks_url:
        raise RuntimeError(
            "CLERK_JWKS_URL is not set. Add it to your .env file.\n"
            "Find it in the Clerk Dashboard → API Keys → Advanced → JWKS URL."
        )

    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL_SEC:
        return _jwks_cache

    try:
        resp = httpx.get(jwks_url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
        _logger.info("✅ Refreshed JWKS from Clerk (%d keys)", len(_jwks_cache.get("keys", [])))
        return _jwks_cache
    except Exception as exc:
        _logger.error("Failed to fetch JWKS from %s: %s", jwks_url, exc)
        if _jwks_cache:
            _logger.warning("Using stale JWKS cache.")
            return _jwks_cache
        raise


def _decode_jwt(token: str) -> dict:
    """
    Decode and verify a Clerk JWT.
    Uses PyJWT with the RS256 public key from JWKS.
    """
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError:
        raise RuntimeError(
            "PyJWT is not installed. Run: pip install PyJWT cryptography"
        )

    jwks_url = os.getenv("CLERK_JWKS_URL", "")
    if not jwks_url:
        raise RuntimeError("CLERK_JWKS_URL is not set.")

    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """
    FastAPI dependency. Validates the Bearer JWT and returns the Clerk user ID.
    Raises 401 if token is missing or invalid.
    Falls back to a guest_user ID if CLERK_JWKS_URL is not configured for easy local testing.
    """
    jwks_url = os.getenv("CLERK_JWKS_URL", "")
    if not jwks_url or "your-app" in jwks_url:
        # Operating in local guest mode
        return "guest_user"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_jwt(credentials.credentials)

    # Clerk puts the user ID in the `sub` claim
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the 'sub' claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id

