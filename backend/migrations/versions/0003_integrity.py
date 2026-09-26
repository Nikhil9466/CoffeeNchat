"""Validate legacy boundaries and add domain/search indexes without rewriting history."""

from alembic import op
from sqlalchemy import text

revision = "0003_integrity"
down_revision = "0002_workspace"


def upgrade():
    connection = op.get_bind()
    checks = {
        "case-insensitive duplicate emails": "SELECT 1 FROM users GROUP BY lower(email) HAVING count(*)>1 LIMIT 1",
        "direct conversations with more than two members": "SELECT 1 FROM conversations c JOIN conversation_participants p ON p.conversation_id=c.id WHERE NOT c.is_group GROUP BY c.id HAVING count(*)>2 LIMIT 1",
        "groups without an administrator": "SELECT 1 FROM conversations c JOIN conversation_participants p ON p.conversation_id=c.id WHERE c.is_group GROUP BY c.id HAVING count(*) FILTER(WHERE p.role='admin')=0 LIMIT 1",
    }
    for problem, query in checks.items():
        if connection.scalar(text(query)):
            raise RuntimeError(
                "Migration stopped: "
                + problem
                + ". Review affected records in a database copy; no histories are merged automatically."
            )
    for sql in [
        "CREATE UNIQUE INDEX uq_users_email_lower ON users(lower(email))",
        "ALTER TABLE conversation_participants ADD CONSTRAINT ck_participant_role CHECK (role IN ('member','admin'))",
        "ALTER TABLE reports ADD CONSTRAINT ck_report_status CHECK (status IN ('open','resolved'))",
        "ALTER TABLE conversations ADD CONSTRAINT ck_group_direct_key CHECK (NOT is_group OR direct_key IS NULL)",
        "CREATE INDEX ix_messages_cursor ON messages(conversation_id,created_at DESC,id DESC)",
        "CREATE INDEX ix_reports_status_created ON reports(status,created_at,id)",
        "CREATE INDEX ix_attachments_cursor ON attachments(conversation_id,created_at DESC,id)",
        "CREATE INDEX ix_password_resets_expiry ON password_resets(expires_at)",
    ]:
        op.execute(sql)


def downgrade():
    raise RuntimeError("Restore a verified backup; destructive downgrade is disabled.")
