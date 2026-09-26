"""Register all ORM entities together so CLI tools and migrations see complete metadata."""

from . import (
    conversation_model,
    feature_model,
    message_model,
    revoked_token_model,
    session_model,
    user_model,
)

__all__ = [
    "conversation_model",
    "feature_model",
    "message_model",
    "revoked_token_model",
    "session_model",
    "user_model",
]
