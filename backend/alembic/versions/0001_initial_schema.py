"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBED_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_email_verified", sa.Boolean(), server_default="false"),
        sa.Column("is_admin", sa.Boolean(), server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "candidate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(512), nullable=True),
        sa.Column("portfolio_url", sa.String(512), nullable=True),
        sa.Column("github_url", sa.String(512), nullable=True),
        sa.Column("current_area", sa.String(120), nullable=True),
        sa.Column("current_city", sa.String(120), nullable=True),
        sa.Column("current_state", sa.String(120), nullable=True),
        sa.Column("current_country", sa.String(120), nullable=True),
        sa.Column("professional_summary", sa.Text(), nullable=True),
        sa.Column("career_level", sa.String(50), nullable=True),
        sa.Column("total_experience_months", sa.Integer(), server_default="0"),
        sa.Column("relevant_experience_months", sa.Integer(), server_default="0"),
        sa.Column("resume_score", sa.Float(), nullable=True),
        sa.Column("resume_score_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("ai_strengths", postgresql.JSONB(), nullable=True),
        sa.Column("ai_recommended_roles", postgresql.JSONB(), nullable=True),
        sa.Column("profile_embedding", Vector(EMBED_DIM), nullable=True),
        sa.Column("skill_embedding", Vector(EMBED_DIM), nullable=True),
        sa.Column("is_profile_complete", sa.Boolean(), server_default="false"),
        sa.Column("profile_completion_pct", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "candidate_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(60), server_default="other"),
        sa.Column("proficiency", sa.String(30), nullable=True),
        sa.Column("months_experience", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), server_default="resume"),
    )
    op.create_index("ix_candidate_skills_normalized_name", "candidate_skills", ["normalized_name"])

    op.create_table(
        "candidate_experience",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("designation", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default="false"),
        sa.Column("duration_months", sa.Integer(), server_default="0"),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=True),
        sa.Column("technologies", postgresql.JSONB(), nullable=True),
        sa.Column("domain", postgresql.JSONB(), nullable=True),
        sa.Column("achievements", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "candidate_education",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("degree", sa.String(255), nullable=True),
        sa.Column("institution", sa.String(255), nullable=True),
        sa.Column("field", sa.String(255), nullable=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        sa.Column("certifications", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "candidate_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("technologies", postgresql.JSONB(), nullable=True),
        sa.Column("domain", postgresql.JSONB(), nullable=True),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=True),
        sa.Column("complexity", sa.String(30), nullable=True),
    )

    op.create_table(
        "candidate_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("preferred_roles", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_locations", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_domains", postgresql.JSONB(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("work_mode", postgresql.JSONB(), nullable=True),
        sa.Column("employment_type", postgresql.JSONB(), nullable=True),
        sa.Column("min_match_score", sa.Integer(), server_default="50"),
        sa.Column("willing_to_relocate", sa.Boolean(), server_default="false"),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "job_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("adapter_key", sa.String(80), nullable=False),
        sa.Column("trust_tier", sa.String(20), server_default="aggregator"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), server_default="never_run"),
        sa.Column("jobs_fetched_total", sa.Integer(), server_default="0"),
        sa.Column("jobs_accepted_total", sa.Integer(), server_default="0"),
        sa.Column("duplicates_total", sa.Integer(), server_default="0"),
        sa.Column("failures_total", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_sources.id"), nullable=False),
        sa.Column("source_job_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("normalized_title", sa.String(255), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("company_name_raw", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=True),
        sa.Column("requirements_required", postgresql.JSONB(), nullable=True),
        sa.Column("requirements_preferred", postgresql.JSONB(), nullable=True),
        sa.Column("area", sa.String(120), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(120), nullable=True),
        sa.Column("country", sa.String(120), nullable=True),
        sa.Column("work_mode", sa.String(20), server_default="onsite"),
        sa.Column("employment_type", sa.String(20), server_default="full_time"),
        sa.Column("experience_min", sa.Integer(), server_default="0"),
        sa.Column("experience_max", sa.Integer(), server_default="0"),
        sa.Column("domain", postgresql.JSONB(), nullable=True),
        sa.Column("education", postgresql.JSONB(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_status", sa.String(20), server_default="active"),
        sa.Column("application_url", sa.String(1024), nullable=False),
        sa.Column("company_url", sa.String(1024), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=True),
        sa.Column("trust_score", sa.Float(), server_default="0.5"),
        sa.Column("is_verified", sa.Boolean(), server_default="false"),
        sa.Column("is_duplicate", sa.Boolean(), server_default="false"),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "source_job_id", name="uq_jobs_source_sourcejobid"),
    )
    op.create_index("ix_jobs_normalized_title", "jobs", ["normalized_title"])
    op.create_index("ix_jobs_city", "jobs", ["city"])
    op.create_index("ix_jobs_state", "jobs", ["state"])
    op.create_index("ix_jobs_country", "jobs", ["country"])
    op.create_index("ix_jobs_work_mode", "jobs", ["work_mode"])
    op.create_index("ix_jobs_employment_type", "jobs", ["employment_type"])
    op.create_index("ix_jobs_experience_min", "jobs", ["experience_min"])
    op.create_index("ix_jobs_experience_max", "jobs", ["experience_max"])
    op.create_index("ix_jobs_posted_at", "jobs", ["posted_at"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])
    op.create_index("ix_jobs_canonical_job_id", "jobs", ["canonical_job_id"])
    op.create_index("ix_jobs_is_duplicate", "jobs", ["is_duplicate"])
    op.execute("CREATE INDEX ix_jobs_title_trgm ON jobs USING gin (title gin_trgm_ops)")
    op.execute(
        "CREATE INDEX ix_jobs_embedding_ivfflat ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "job_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_job_skills_normalized_name", "job_skills", ["normalized_name"])

    op.create_table(
        "job_duplicates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("duplicate_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("signals", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "job_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("skills_score", sa.Float(), server_default="0"),
        sa.Column("experience_score", sa.Float(), server_default="0"),
        sa.Column("role_score", sa.Float(), server_default="0"),
        sa.Column("semantic_score", sa.Float(), server_default="0"),
        sa.Column("location_score", sa.Float(), server_default="0"),
        sa.Column("domain_score", sa.Float(), server_default="0"),
        sa.Column("education_score", sa.Float(), server_default="0"),
        sa.Column("work_mode_score", sa.Float(), server_default="0"),
        sa.Column("recency_score", sa.Float(), server_default="0"),
        sa.Column("trust_score", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_job_matches_candidate_job"),
    )
    op.create_index("ix_job_matches_candidate_id", "job_matches", ["candidate_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])

    op.create_table(
        "match_reasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_matches.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("matched_skills", postgresql.JSONB(), nullable=True),
        sa.Column("missing_skills", postgresql.JSONB(), nullable=True),
        sa.Column("transferable_skills", postgresql.JSONB(), nullable=True),
        sa.Column("experience_reason", sa.String(500), nullable=True),
        sa.Column("location_reason", sa.String(500), nullable=True),
        sa.Column("role_reason", sa.String(500), nullable=True),
        sa.Column("domain_reason", sa.String(500), nullable=True),
        sa.Column("overall_reason", sa.String(1000), nullable=True),
        sa.Column("concerns", postgresql.JSONB(), nullable=True),
        sa.Column("llm_validated", sa.Boolean(), server_default="false"),
    )

    op.create_table(
        "saved_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_saved_jobs_candidate_job"),
    )
    op.create_index("ix_saved_jobs_candidate_id", "saved_jobs", ["candidate_id"])

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="apply_clicked"),
        sa.Column("application_url", sa.String(1024), nullable=False),
        sa.Column("apply_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])

    op.create_table(
        "resume_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resume_files_candidate_id", "resume_files", ["candidate_id"])

    op.create_table(
        "resume_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resume_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resume_files.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Integer(), server_default="0"),
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("raw_llm_output", postgresql.JSONB(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(), nullable=True),
        sa.Column("improvement_suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("recommended_roles", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resume_analysis_candidate_id", "resume_analysis", ["candidate_id"])

    op.create_table(
        "search_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_query", sa.Text(), nullable=True),
        sa.Column("parsed_filters", postgresql.JSONB(), nullable=True),
        sa.Column("result_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_search_history_candidate_id", "search_history", ["candidate_id"])

    op.create_table(
        "recommendation_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_history_candidate_id", "recommendation_history", ["candidate_id"])

    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_job_ids", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_conversations_candidate_id", "ai_conversations", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("ai_conversations")
    op.drop_table("recommendation_history")
    op.drop_table("search_history")
    op.drop_table("resume_analysis")
    op.drop_table("resume_files")
    op.drop_table("applications")
    op.drop_table("saved_jobs")
    op.drop_table("match_reasons")
    op.drop_table("job_matches")
    op.drop_table("job_duplicates")
    op.drop_table("job_skills")
    op.drop_table("jobs")
    op.drop_table("companies")
    op.drop_table("job_sources")
    op.drop_table("candidate_preferences")
    op.drop_table("candidate_projects")
    op.drop_table("candidate_education")
    op.drop_table("candidate_experience")
    op.drop_table("candidate_skills")
    op.drop_table("candidate_profiles")
    op.drop_table("users")
