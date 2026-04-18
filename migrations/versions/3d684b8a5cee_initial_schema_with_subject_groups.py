"""initial schema with subject groups

Revision ID: 3d684b8a5cee
Revises: 
Create Date: 2026-04-18 16:16:02.618505

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = '3d684b8a5cee'
down_revision = None
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    insp = inspect(bind)
    return column in {c['name'] for c in insp.get_columns(table)}


def _table_exists(table):
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade():
    # ── Legacy schema additions (idempotent) ─────────────────────────────────
    # These columns were previously added at runtime via _ensure_legacy_schema_updates.
    # We add them here so existing installations get them via migration.
    if _table_exists('questions'):
        if not _column_exists('questions', 'reference_text'):
            op.add_column('questions', sa.Column('reference_text', sa.Text(), nullable=True))
        if not _column_exists('questions', 'explanation_image_path'):
            op.add_column('questions', sa.Column('explanation_image_path', sa.String(256), nullable=True))

    if _table_exists('answer_options'):
        if not _column_exists('answer_options', 'image_path'):
            op.add_column('answer_options', sa.Column('image_path', sa.String(256), nullable=True))

    # ── Subject groups ────────────────────────────────────────────────────────
    if not _table_exists('subject_groups'):
        op.create_table('subject_groups',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    if _table_exists('subjects') and not _column_exists('subjects', 'group_id'):
        with op.batch_alter_table('subjects', schema=None) as batch_op:
            batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_subjects_group_id', 'subject_groups', ['group_id'], ['id'])


def downgrade():
    if _table_exists('subjects') and _column_exists('subjects', 'group_id'):
        with op.batch_alter_table('subjects', schema=None) as batch_op:
            batch_op.drop_constraint('fk_subjects_group_id', type_='foreignkey')
            batch_op.drop_column('group_id')

    if _table_exists('subject_groups'):
        op.drop_table('subject_groups')
