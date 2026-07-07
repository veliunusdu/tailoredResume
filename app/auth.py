from pydantic import BaseModel
from fastapi import Header
from typing import Optional

class User(BaseModel):
    id: str
    email: str

def get_current_user(x_session_id: Optional[str] = Header(None)) -> User:
    """Mock authentication, returning a user mapped to the client's session ID."""
    session_id = x_session_id or "00000000-0000-0000-0000-000000000000"
    return User(
        id=session_id,
        email="default@example.com"
    )
