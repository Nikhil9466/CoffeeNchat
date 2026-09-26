from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .user_schema import PublicUser


class ParticipantBase(BaseModel):
    user_id: UUID


class ParticipantResponse(ParticipantBase):
    conversation_id: UUID
    last_read_at: datetime | None = None
    joined_at: datetime
    role: str = "member"
    user: PublicUser | None = None  # Optional nested user profile

    model_config = ConfigDict(from_attributes=True)


class ConversationBase(BaseModel):
    is_group: bool = False
    name: str | None = Field(default=None, max_length=255)
    group_picture_url: str | None = Field(default=None, max_length=512)


class ConversationCreate(ConversationBase):
    participant_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class ConversationResponse(ConversationBase):
    id: UUID
    is_group: bool
    name: str | None = None
    group_picture_url: str | None = None
    created_at: datetime
    participants: list[ParticipantResponse] = []

    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    group_picture_url: str | None = Field(default=None, max_length=512)
    participant_ids: list[UUID] = Field(default_factory=list, max_length=100)


class AddParticipantRequest(BaseModel):
    user_id: UUID


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    group_picture_url: str | None = Field(default=None, max_length=512)
