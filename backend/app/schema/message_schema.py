from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .user_schema import PublicUser


class MessageBase(BaseModel):
    content: str | None = Field(default=None, max_length=10000)
    media_url: str | None = Field(default=None, max_length=512)


class MessageCreate(MessageBase):
    conversation_id: UUID
    client_id: UUID | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if self.content is not None:
            self.content = self.content.strip() or None
        if not self.content and not self.media_url:
            raise ValueError("Message cannot be empty")
        return self


class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    sender_id: UUID | None = None
    client_id: UUID | None = None
    created_at: datetime
    deleted_at: datetime | None = None
    sender: PublicUser | None = None
    model_config = ConfigDict(from_attributes=True)
