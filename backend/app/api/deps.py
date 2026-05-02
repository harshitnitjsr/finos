"""
Shared FastAPI dependencies for authentication and org context.

Every route that touches organisation-scoped data should depend on
`get_org_id` instead of any hardcoded org constant.

The Next.js secure proxy (app/api/backend/[...path]/route.ts) injects:
  X-Org-ID        — the authenticated user's organisation UUID
  X-User-ID       — the authenticated user's UUID
  X-User-Email    — the authenticated user's email
  X-Internal-Token — shared secret proving the request came from Next.js

InternalAuthMiddleware in main.py validates X-Internal-Token before
any route handler runs, so by the time we reach these deps the caller
is already authenticated.
"""
import re
import uuid
from fastapi import Header, HTTPException

# Loose UUID regex — accepts both hyphenated and non-hyphenated forms
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_uuid(value: str, field: str) -> str:
    """Raise 400 if value is not a valid UUID."""
    if not _UUID_RE.match(value.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"{field} must be a valid UUID, got: {value!r}",
        )
    # Return canonical form
    return str(uuid.UUID(value.strip()))


async def get_org_id(x_org_id: str = Header(..., alias="x-org-id")) -> str:
    """
    Extract and validate the org_id from the X-Org-ID request header.
    - Missing header → 422 (FastAPI default for `...` required params)
    - Invalid UUID   → 400
    """
    from app.core.context import org_id_var
    
    if not x_org_id or not x_org_id.strip():
        raise HTTPException(status_code=400, detail="X-Org-ID header is required")
    
    valid_id = _validate_uuid(x_org_id, "X-Org-ID")
    org_id_var.set(valid_id)
    return valid_id


async def get_user_id(x_user_id: str = Header("", alias="x-user-id")) -> str:
    val = x_user_id.strip()
    if val:
        return _validate_uuid(val, "X-User-ID")
    return val


async def get_user_email(x_user_email: str = Header("", alias="x-user-email")) -> str:
    return x_user_email.strip()
