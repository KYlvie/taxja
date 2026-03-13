"""merge_multiple_heads

Revision ID: 35954ae63c9d
Revises: 011, add_7_einkunftsarten, add_bescheid_doctype, add_gmbh_user_type, add_uat_feedback
Create Date: 2026-03-08 19:20:05.420668

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '35954ae63c9d'
down_revision = ('011', 'add_7_einkunftsarten', 'add_bescheid_doctype', 'add_gmbh_user_type', 'add_uat_feedback')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
