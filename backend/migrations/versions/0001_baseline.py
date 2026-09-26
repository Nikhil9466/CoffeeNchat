"""Original schema. Existing verified databases may be stamped at this revision."""

from alembic import op

revision = "0001_baseline"
down_revision = None


def upgrade():
    statements = [
        "CREATE TABLE users (id UUID PRIMARY KEY,email VARCHAR(255) NOT NULL UNIQUE,username VARCHAR(50) NOT NULL UNIQUE,password_hash VARCHAR(255) NOT NULL,profile_picture_url VARCHAR(512),is_admin BOOLEAN NOT NULL DEFAULT false,created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE conversations (id UUID PRIMARY KEY,is_group BOOLEAN DEFAULT false,name VARCHAR(255),group_picture_url VARCHAR(512),created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE conversation_participants (conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,user_id UUID REFERENCES users(id) ON DELETE CASCADE,role VARCHAR(20) NOT NULL DEFAULT 'member',joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(conversation_id,user_id))",
        "CREATE TABLE messages (id UUID PRIMARY KEY,conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,sender_id UUID REFERENCES users(id) ON DELETE SET NULL,content TEXT,media_url VARCHAR(512),created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,CONSTRAINT chk_content_or_media CHECK(content IS NOT NULL OR media_url IS NOT NULL))",
        "CREATE INDEX idx_messages_conversation_created ON messages(conversation_id,created_at DESC)",
        "CREATE TABLE revoked_tokens (jti VARCHAR(64) PRIMARY KEY,expires_at TIMESTAMPTZ NOT NULL)",
    ]
    for sql in statements:
        op.execute(sql)


def downgrade():
    raise RuntimeError(
        "Destructive downgrades are intentionally disabled. Restore a verified backup."
    )
