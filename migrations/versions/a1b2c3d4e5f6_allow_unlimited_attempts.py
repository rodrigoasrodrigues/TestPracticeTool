"""allow unlimited attempts (nullable max_attempts)

Revision ID: a1b2c3d4e5f6
Revises: 3d684b8a5cee
Create Date: 2026-04-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3d684b8a5cee'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    insp = inspect(bind)
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    # Make max_attempts nullable so None means unlimited
    with op.batch_alter_table('student_exams', schema=None) as batch_op:
        batch_op.alter_column('max_attempts',
                              existing_type=sa.Integer(),
                              nullable=True)


def downgrade():
    # Revert NULLs to 1 before making non-nullable again
    op.execute("UPDATE student_exams SET max_attempts = 1 WHERE max_attempts IS NULL")
    with op.batch_alter_table('student_exams', schema=None) as batch_op:
        batch_op.alter_column('max_attempts',
                              existing_type=sa.Integer(),
                              nullable=False)
