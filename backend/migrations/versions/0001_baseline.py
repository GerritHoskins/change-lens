"""Baseline: the I-22 schema exactly as `Database.create_schema()` built it at b8e3778.

`create_all` of the models at that commit, including every former `DEV_COLUMNS` change and
`account_onboarding`. A dev database built by `create_all` is brought under Alembic by
`python -m changelens.db stamp-baseline`, which checks it against this revision first.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('account_onboarding',
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('onboarding_step', sa.SmallInteger(), nullable=True),
    sa.Column('onboarding_completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('onboarding_completed_at IS NULL OR onboarding_step IS NULL', name='ck_onboarding_done'),
    sa.CheckConstraint('onboarding_step IS NULL OR onboarding_step BETWEEN 1 AND 32', name='ck_onboarding_step'),
    sa.PrimaryKeyConstraint('account_id')
    )
    op.create_index(op.f('ix_account_onboarding_tenant_id'), 'account_onboarding', ['tenant_id'], unique=False)
    op.create_table('comparison_cost_tombstones',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('cost_actual', sa.Numeric(precision=20, scale=10), nullable=False),
    sa.Column('cost_reservations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comparison_cost_tombstones_tenant_id'), 'comparison_cost_tombstones', ['tenant_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('idempotency_key', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key', name='uq_jobs_idempotency_key')
    )
    op.create_index('ix_jobs_claim', 'jobs', ['status', 'run_after'], unique=False)
    op.create_index(op.f('ix_jobs_tenant_id'), 'jobs', ['tenant_id'], unique=False)
    op.create_table('object_purge_intents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('object_key', sa.String(length=300), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('object_key')
    )
    op.create_index(op.f('ix_object_purge_intents_project_id'), 'object_purge_intents', ['project_id'], unique=False)
    op.create_index(op.f('ix_object_purge_intents_tenant_id'), 'object_purge_intents', ['tenant_id'], unique=False)
    op.create_table('object_write_intents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('object_key', sa.String(length=300), nullable=False),
    sa.Column('request_lock_id', sa.BigInteger(), nullable=False),
    sa.Column('write_acknowledged', sa.Boolean(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('object_key')
    )
    op.create_index(op.f('ix_object_write_intents_next_attempt_at'), 'object_write_intents', ['next_attempt_at'], unique=False)
    op.create_index(op.f('ix_object_write_intents_tenant_id'), 'object_write_intents', ['tenant_id'], unique=False)
    op.create_table('project_deletions',
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('project_id')
    )
    op.create_index(op.f('ix_project_deletions_tenant_id'), 'project_deletions', ['tenant_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('client_label', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_tenant_id'), 'projects', ['tenant_id'], unique=False)
    op.create_table('source_versions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('original_object_key', sa.String(length=300), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('reject_reason', sa.String(length=50), nullable=True),
    sa.Column('parsed_pages', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('blocks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('parse_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_versions_tenant_id'), 'source_versions', ['tenant_id'], unique=False)
    op.create_table('comparisons',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('earlier_id', sa.UUID(), nullable=False),
    sa.Column('later_id', sa.UUID(), nullable=False),
    sa.Column('scope_snapshot', sa.String(length=10), nullable=False),
    sa.Column('pipeline_version', sa.String(length=40), nullable=False),
    sa.Column('model_config_id', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    sa.Column('request_fingerprint', sa.String(length=64), nullable=True),
    sa.Column('cost_ceiling', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('cost_estimate', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('cost_actual', sa.Numeric(precision=20, scale=10), nullable=True),
    sa.Column('cost_reservations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('withheld_count', sa.Integer(), nullable=False),
    sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('unexplained', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('presentation_only', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['earlier_id'], ['source_versions.id'], ),
    sa.ForeignKeyConstraint(['later_id'], ['source_versions.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'idempotency_key', name='uq_comparisons_request')
    )
    op.create_index(op.f('ix_comparisons_tenant_id'), 'comparisons', ['tenant_id'], unique=False)
    op.create_table('fact_cache',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('source_version_id', sa.UUID(), nullable=False),
    sa.Column('cache_key', sa.String(length=64), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_version_id'], ['source_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'cache_key', name='uq_fact_cache_tenant_key')
    )
    op.create_index(op.f('ix_fact_cache_tenant_id'), 'fact_cache', ['tenant_id'], unique=False)
    op.create_table('findings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('comparison_id', sa.UUID(), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('change_type', sa.String(length=20), nullable=False),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('uncertainty', sa.String(length=40), nullable=True),
    sa.Column('note', sa.String(length=40), nullable=True),
    sa.Column('review_group', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('supersedes_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['comparison_id'], ['comparisons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_findings_comparison_id'), 'findings', ['comparison_id'], unique=False)
    op.create_index(op.f('ix_findings_tenant_id'), 'findings', ['tenant_id'], unique=False)
    op.create_table('client_approvals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('finding_id', sa.UUID(), nullable=False),
    sa.Column('evidence_text', sa.Text(), nullable=False),
    sa.Column('stated_by', sa.String(length=200), nullable=False),
    sa.Column('stated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recorded_by', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_client_approvals_finding_id'), 'client_approvals', ['finding_id'], unique=False)
    op.create_index(op.f('ix_client_approvals_tenant_id'), 'client_approvals', ['tenant_id'], unique=False)
    op.create_table('review_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('finding_id', sa.UUID(), nullable=False),
    sa.Column('actor', sa.String(length=80), nullable=False),
    sa.Column('action', sa.String(length=12), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('evidence_mode_before', sa.String(length=20), nullable=True),
    sa.Column('evidence_mode_after', sa.String(length=20), nullable=True),
    sa.Column('page_opened', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("evidence_mode_after IS NULL OR evidence_mode_after IN ('pdf_highlight', 'text_fallback', 'text_only')", name='ck_review_evidence_after'),
    sa.CheckConstraint("evidence_mode_before IS NULL OR evidence_mode_before IN ('pdf_highlight', 'text_fallback', 'text_only')", name='ck_review_evidence_before'),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_events_finding_id'), 'review_events', ['finding_id'], unique=False)
    op.create_index(op.f('ix_review_events_tenant_id'), 'review_events', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_review_events_tenant_id'), table_name='review_events')
    op.drop_index(op.f('ix_review_events_finding_id'), table_name='review_events')
    op.drop_table('review_events')
    op.drop_index(op.f('ix_client_approvals_tenant_id'), table_name='client_approvals')
    op.drop_index(op.f('ix_client_approvals_finding_id'), table_name='client_approvals')
    op.drop_table('client_approvals')
    op.drop_index(op.f('ix_findings_tenant_id'), table_name='findings')
    op.drop_index(op.f('ix_findings_comparison_id'), table_name='findings')
    op.drop_table('findings')
    op.drop_index(op.f('ix_fact_cache_tenant_id'), table_name='fact_cache')
    op.drop_table('fact_cache')
    op.drop_index(op.f('ix_comparisons_tenant_id'), table_name='comparisons')
    op.drop_table('comparisons')
    op.drop_index(op.f('ix_source_versions_tenant_id'), table_name='source_versions')
    op.drop_table('source_versions')
    op.drop_index(op.f('ix_projects_tenant_id'), table_name='projects')
    op.drop_table('projects')
    op.drop_index(op.f('ix_project_deletions_tenant_id'), table_name='project_deletions')
    op.drop_table('project_deletions')
    op.drop_index(op.f('ix_object_write_intents_tenant_id'), table_name='object_write_intents')
    op.drop_index(op.f('ix_object_write_intents_next_attempt_at'), table_name='object_write_intents')
    op.drop_table('object_write_intents')
    op.drop_index(op.f('ix_object_purge_intents_tenant_id'), table_name='object_purge_intents')
    op.drop_index(op.f('ix_object_purge_intents_project_id'), table_name='object_purge_intents')
    op.drop_table('object_purge_intents')
    op.drop_index(op.f('ix_jobs_tenant_id'), table_name='jobs')
    op.drop_index('ix_jobs_claim', table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_comparison_cost_tombstones_tenant_id'), table_name='comparison_cost_tombstones')
    op.drop_table('comparison_cost_tombstones')
    op.drop_index(op.f('ix_account_onboarding_tenant_id'), table_name='account_onboarding')
    op.drop_table('account_onboarding')
