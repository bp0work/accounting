"""create_case_attachments_table — `06` §4.5."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_015"
down_revision = "20260521_014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("checksum_sha256", sa.CHAR(64), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
    )
    op.create_index("case_attachments_case_id_idx", "case_attachments", ["case_id"])


def downgrade() -> None:
    op.drop_table("case_attachments")
