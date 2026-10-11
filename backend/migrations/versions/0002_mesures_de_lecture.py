"""Mesures de lecture envoyées par l'application (Phase 2) : table playback_events.

Révision : 0002
Précédente : 0001
Créée le : 2026-10-11 13:07:37.926450

Règles :
- upgrade() ne doit jamais perdre de données (ajouter plutôt que supprimer/renommer).
- downgrade() doit ramener exactement au schéma précédent.
- Tester sur une COPIE de la base de production avant de fusionner dans main.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('playback_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('video_id', sa.Integer(), nullable=True),
    sa.Column('event_type', sa.String(length=32), nullable=False),
    sa.Column('ttff_ms', sa.Integer(), nullable=True),
    sa.Column('stall_ms', sa.Integer(), nullable=True),
    sa.Column('position_s', sa.Float(), nullable=True),
    sa.Column('preloaded', sa.Boolean(), nullable=True),
    sa.Column('network', sa.String(length=16), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('app_version', sa.String(length=32), nullable=True),
    sa.Column('device_model', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('playback_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_playback_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_playback_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_playback_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_playback_events_video_id'), ['video_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('playback_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_playback_events_video_id'))
        batch_op.drop_index(batch_op.f('ix_playback_events_user_id'))
        batch_op.drop_index(batch_op.f('ix_playback_events_event_type'))
        batch_op.drop_index(batch_op.f('ix_playback_events_created_at'))

    op.drop_table('playback_events')
