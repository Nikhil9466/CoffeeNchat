from sqlalchemy import Column, String, TIMESTAMP
from app.db import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti = Column(String(64), primary_key=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
