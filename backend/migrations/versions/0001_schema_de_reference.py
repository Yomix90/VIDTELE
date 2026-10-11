"""Schéma de référence (baseline) : état de la base au début de la Phase 1.

- Base NEUVE : upgrade() crée toutes les tables.
- Base EXISTANTE (production) : cette migration n'est PAS exécutée. Le démarrage
  (app/core/migrations.py) sauvegarde la base, la met à niveau avec l'ancien
  mécanisme, vérifie le schéma puis la marque à cette révision (stamp).

Révision : 0001
Précédente : 
Créée le : 2026-10-11 00:13:08.106097

Règles :
- upgrade() ne doit jamais perdre de données (ajouter plutôt que supprimer/renommer).
- downgrade() doit ramener exactement au schéma précédent.
- Tester sur une COPIE de la base de production avant de fusionner dans main.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('collections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=128), nullable=False),
    sa.Column('title_fr', sa.String(length=255), nullable=False),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('description_fr', sa.Text(), nullable=True),
    sa.Column('description_ar', sa.Text(), nullable=True),
    sa.Column('poster_path', sa.String(length=512), nullable=True),
    sa.Column('banner_path', sa.String(length=512), nullable=True),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('collections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_collections_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_collections_slug'), ['slug'], unique=True)

    op.create_table('genres',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name_fr', sa.String(length=128), nullable=False),
    sa.Column('name_ar', sa.String(length=128), nullable=True),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('genres', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_genres_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_genres_slug'), ['slug'], unique=True)

    op.create_table('home_hero_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content_type', sa.String(length=32), nullable=False),
    sa.Column('content_id', sa.Integer(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('home_hero_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_home_hero_items_id'), ['id'], unique=False)

    op.create_table('media_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('media_type', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('poster_url', sa.String(length=512), nullable=True),
    sa.Column('backdrop_url', sa.String(length=512), nullable=True),
    sa.Column('release_year', sa.Integer(), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('media_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_media_items_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_media_items_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_media_items_is_published'), ['is_published'], unique=False)
        batch_op.create_index(batch_op.f('ix_media_items_title'), ['title'], unique=False)

    op.create_table('series',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('title_fr', sa.String(length=255), nullable=False),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('title_en', sa.String(length=255), nullable=True),
    sa.Column('title_original', sa.String(length=255), nullable=True),
    sa.Column('synopsis_fr', sa.Text(), nullable=True),
    sa.Column('synopsis_ar', sa.Text(), nullable=True),
    sa.Column('synopsis_en', sa.Text(), nullable=True),
    sa.Column('year_start', sa.Integer(), nullable=True),
    sa.Column('year_end', sa.Integer(), nullable=True),
    sa.Column('country', sa.String(length=64), nullable=True),
    sa.Column('language', sa.String(length=32), nullable=True),
    sa.Column('age_rating', sa.String(length=16), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('trailer_url', sa.String(length=512), nullable=True),
    sa.Column('poster_path', sa.String(length=512), nullable=True),
    sa.Column('banner_path', sa.String(length=512), nullable=True),
    sa.Column('logo_path', sa.String(length=512), nullable=True),
    sa.Column('tmdb_id', sa.Integer(), nullable=True),
    sa.Column('is_featured', sa.Boolean(), nullable=False),
    sa.Column('visibility', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('series', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_series_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_series_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_series_title_fr'), ['title_fr'], unique=False)

    op.create_table('system_settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_system_settings_key'), ['key'], unique=False)

    op.create_table('telegram_accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('api_id', sa.Integer(), nullable=True),
    sa.Column('api_hash', sa.String(length=64), nullable=True),
    sa.Column('string_session', sa.Text(), nullable=True),
    sa.Column('session_file', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('account_user_id', sa.BigInteger(), nullable=True),
    sa.Column('account_username', sa.String(length=128), nullable=True),
    sa.Column('account_first_name', sa.String(length=128), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_tested_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('telegram_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_telegram_accounts_id'), ['id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('ads_free', sa.Boolean(), nullable=False),
    sa.Column('max_screens', sa.Integer(), nullable=False),
    sa.Column('max_concurrent_streams', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('invited_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=True),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_id'), ['id'], unique=False)

    op.create_table('devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('device_name', sa.String(length=128), nullable=False),
    sa.Column('device_type', sa.String(length=32), nullable=False),
    sa.Column('app_version', sa.String(length=32), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_devices_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_devices_user_id'), ['user_id'], unique=False)

    op.create_table('home_rows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('row_type', sa.String(length=32), nullable=False),
    sa.Column('title_fr', sa.String(length=255), nullable=False),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('genre_id', sa.Integer(), nullable=True),
    sa.Column('collection_id', sa.Integer(), nullable=True),
    sa.Column('limit_items', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('home_rows', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_home_rows_id'), ['id'], unique=False)

    op.create_table('invite_codes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('used_by_id', sa.Integer(), nullable=True),
    sa.Column('max_uses', sa.Integer(), nullable=False),
    sa.Column('uses_count', sa.Integer(), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['used_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('invite_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invite_codes_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_invite_codes_id'), ['id'], unique=False)

    op.create_table('seasons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('series_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('title_fr', sa.String(length=255), nullable=True),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('poster_path', sa.String(length=512), nullable=True),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['series_id'], ['series.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('series_id', 'number', name='uq_series_season_number')
    )
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_seasons_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_seasons_series_id'), ['series_id'], unique=False)

    op.create_table('sync_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('started_by', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('videos_found', sa.Integer(), nullable=False),
    sa.Column('videos_added', sa.Integer(), nullable=False),
    sa.Column('videos_classified', sa.Integer(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['started_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sync_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sync_logs_id'), ['id'], unique=False)

    op.create_table('videos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_message_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('caption', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('mime_type', sa.String(length=64), nullable=False),
    sa.Column('thumbnail_path', sa.String(length=255), nullable=True),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('views_count', sa.Integer(), nullable=False),
    sa.Column('telegram_date', sa.DateTime(), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('media_item_id', sa.Integer(), nullable=True),
    sa.Column('season_number', sa.Integer(), nullable=False),
    sa.Column('episode_number', sa.Integer(), nullable=False),
    sa.Column('episode_title', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['media_item_id'], ['media_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_videos_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_videos_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_videos_is_published'), ['is_published'], unique=False)
        batch_op.create_index(batch_op.f('ix_videos_media_item_id'), ['media_item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_videos_telegram_message_id'), ['telegram_message_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_videos_title'), ['title'], unique=False)

    op.create_table('active_streams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=False),
    sa.Column('session_token', sa.String(length=64), nullable=False),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('last_active_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('active_streams', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_active_streams_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_active_streams_session_token'), ['session_token'], unique=True)
        batch_op.create_index(batch_op.f('ix_active_streams_user_id'), ['user_id'], unique=False)

    op.create_table('episodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('season_id', sa.Integer(), nullable=False),
    sa.Column('telegram_video_id', sa.Integer(), nullable=True),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('title_fr', sa.String(length=255), nullable=True),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('title_en', sa.String(length=255), nullable=True),
    sa.Column('synopsis_fr', sa.Text(), nullable=True),
    sa.Column('synopsis_ar', sa.Text(), nullable=True),
    sa.Column('synopsis_en', sa.Text(), nullable=True),
    sa.Column('duration_sec', sa.Integer(), nullable=True),
    sa.Column('thumbnail_path', sa.String(length=512), nullable=True),
    sa.Column('release_date', sa.String(length=32), nullable=True),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['telegram_video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('season_id', 'number', name='uq_season_episode_number'),
    sa.UniqueConstraint('telegram_video_id')
    )
    with op.batch_alter_table('episodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_episodes_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_episodes_season_id'), ['season_id'], unique=False)

    op.create_table('favorites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'video_id', name='uq_user_video_favorite')
    )
    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_favorites_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_favorites_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_favorites_video_id'), ['video_id'], unique=False)

    op.create_table('movies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('collection_id', sa.Integer(), nullable=True),
    sa.Column('telegram_video_id', sa.Integer(), nullable=True),
    sa.Column('title_fr', sa.String(length=255), nullable=False),
    sa.Column('title_ar', sa.String(length=255), nullable=True),
    sa.Column('title_en', sa.String(length=255), nullable=True),
    sa.Column('title_original', sa.String(length=255), nullable=True),
    sa.Column('synopsis_fr', sa.Text(), nullable=True),
    sa.Column('synopsis_ar', sa.Text(), nullable=True),
    sa.Column('synopsis_en', sa.Text(), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('duration_sec', sa.Integer(), nullable=True),
    sa.Column('country', sa.String(length=64), nullable=True),
    sa.Column('language', sa.String(length=32), nullable=True),
    sa.Column('age_rating', sa.String(length=16), nullable=True),
    sa.Column('rating', sa.Float(), nullable=True),
    sa.Column('trailer_url', sa.String(length=512), nullable=True),
    sa.Column('poster_path', sa.String(length=512), nullable=True),
    sa.Column('banner_path', sa.String(length=512), nullable=True),
    sa.Column('logo_path', sa.String(length=512), nullable=True),
    sa.Column('tmdb_id', sa.Integer(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('is_featured', sa.Boolean(), nullable=False),
    sa.Column('visibility', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['telegram_video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('telegram_video_id')
    )
    with op.batch_alter_table('movies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_movies_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_movies_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_movies_title_fr'), ['title_fr'], unique=False)

    op.create_table('watch_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=False),
    sa.Column('position_seconds', sa.Float(), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.Column('last_watched_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'video_id', name='uq_user_video_history')
    )
    with op.batch_alter_table('watch_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_watch_history_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_watch_history_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_watch_history_video_id'), ['video_id'], unique=False)



def downgrade() -> None:
    # Revenir avant la référence supprimerait toutes les tables : refusé volontairement.
    # Retour arrière = restaurer la sauvegarde automatique prise avant migration
    # (DATA_DIR/sauvegardes/avant-migration-*.db), voir DEPLOIEMENT.md.
    raise RuntimeError(
        "Retour arrière impossible avant le schéma de référence : restaurez la sauvegarde "
        "automatique DATA_DIR/sauvegardes/avant-migration-*.db."
    )
