import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    TIMESTAMP,
    CheckConstraint,
    text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    client_id = Column(UUID(as_uuid=True), nullable=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    content = Column(Text, nullable=True)
    media_url = Column(String(512), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    __table_args__ = (
        UniqueConstraint("sender_id", "client_id", name="uq_message_sender_client"),
        CheckConstraint(
            "content IS NOT NULL OR media_url IS NOT NULL", name="chk_content_or_media"
        ),
        Index("idx_messages_conversation_created", conversation_id, created_at.desc()),
    )
