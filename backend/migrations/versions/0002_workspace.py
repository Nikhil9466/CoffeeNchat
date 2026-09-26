"""Session records, reliable messages, attachments and moderation; existing data retained."""

from alembic import op

revision = "0002_workspace"
down_revision = "0001_baseline"


def upgrade():
    statements = [
        "ALTER TABLE users ADD COLUMN bio VARCHAR(240) NOT NULL DEFAULT '', ADD COLUMN is_disabled BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE conversations ADD COLUMN direct_key VARCHAR(73) UNIQUE",
        "ALTER TABLE conversation_participants ADD COLUMN last_read_at TIMESTAMPTZ",
        "ALTER TABLE messages ADD COLUMN client_id UUID, ADD COLUMN deleted_at TIMESTAMPTZ, ADD CONSTRAINT uq_message_sender_client UNIQUE(sender_id,client_id)",
        "CREATE INDEX ix_participants_user ON conversation_participants(user_id)",
        "CREATE INDEX ix_messages_created ON messages(created_at)",
        "CREATE INDEX ix_messages_sender ON messages(sender_id)",
        "CREATE INDEX ix_revoked_expiry ON revoked_tokens(expires_at)",
        "CREATE TABLE auth_sessions (id VARCHAR(64) PRIMARY KEY,user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,label VARCHAR(256) NOT NULL,created_at TIMESTAMPTZ NOT NULL,expires_at TIMESTAMPTZ NOT NULL)",
        "CREATE INDEX ix_auth_sessions_user_id ON auth_sessions(user_id)",
        "CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions(expires_at)",
        "CREATE TABLE attachments (id UUID PRIMARY KEY,conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,owner_id UUID REFERENCES users(id) ON DELETE SET NULL,filename VARCHAR(255) NOT NULL,content_type VARCHAR(128) NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX ix_attachments_conversation_id ON attachments(conversation_id)",
        "CREATE TABLE saved_messages (user_id UUID REFERENCES users(id) ON DELETE CASCADE,message_id UUID REFERENCES messages(id) ON DELETE CASCADE,PRIMARY KEY(user_id,message_id))",
        "CREATE TABLE reports (id UUID PRIMARY KEY,message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,reason VARCHAR(1000) NOT NULL,status VARCHAR(20) NOT NULL DEFAULT 'open',created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,CONSTRAINT uq_report_user_message UNIQUE(message_id,reporter_id))",
        "CREATE TABLE password_resets (token_hash VARCHAR(64) PRIMARY KEY,user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at TIMESTAMPTZ NOT NULL)",
    ]
    for sql in statements:
        op.execute(sql)


def downgrade():
    raise RuntimeError(
        "Destructive downgrades are intentionally disabled. Restore a verified backup."
    )
