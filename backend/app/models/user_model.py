import uuid
from sqlalchemy import Column, String, Boolean, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    profile_picture_url = Column(String(512), nullable=True, default=None)
    is_admin = Column(Boolean, nullable=False, server_default=text("false"))
    bio = Column(String(240), nullable=False, default="", server_default="")
    is_disabled = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    participations = relationship(
        "ConversationParticipant", back_populates="user", cascade="all, delete-orphan"
    )
    messages = relationship("Message", back_populates="sender")
