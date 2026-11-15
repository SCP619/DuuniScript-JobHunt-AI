"""outcomes and notifications: application.outcome, application.outcome_on; notification

Revision ID: e93b4a07d1c6
Revises: c58e2d71f0a4
Create Date: 2026-11-14 18:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e93b4a07d1c6'
down_revision: str | None = 'c58e2d71f0a4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('notification',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('entity_type', sa.String(length=30), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('message', sa.String(length=600), nullable=False),
    sa.Column('link', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('dismissed_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("kind IN ('good_match', 'deadline_soon', 'ready_not_sent', 'follow_up')", name=op.f('ck_notification_kind')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification')),
    sa.UniqueConstraint('kind', 'entity_id', name='uq_notification_kind_entity')
    )
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.create_index('ix_notification_state', ['dismissed_at', 'read_at', 'created_at'], unique=False)

    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.add_column(sa.Column('outcome', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('outcome_on', sa.Date(), nullable=True))
        batch_op.create_check_constraint(
            'outcome',
            "outcome IS NULL OR outcome IN ('no_response', 'interview', 'rejected', 'offer', 'accepted', 'declined')",
        )


def downgrade() -> None:
    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.drop_constraint('outcome', type_='check')
        batch_op.drop_column('outcome_on')
        batch_op.drop_column('outcome')

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index('ix_notification_state')

    op.drop_table('notification')
