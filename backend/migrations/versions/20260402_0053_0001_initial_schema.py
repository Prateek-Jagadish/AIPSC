"""initial_schema — all 11 tables for UPSC Intelligence System

Revision ID: 0001
Revises: None
Create Date: 2026-04-02 00:53:00

Tables created:
    1.  topics
    2.  subtopics
    3.  micro_tags
    4.  documents
    5.  chunks
    6.  pyqs
    7.  current_affairs
    8.  visual_assets
    9.  conversations
    10. conversation_turns
    11. conversation_topics
    12. user_topic_stats
    13. user_microtag_stats
    14. revision_logs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── ENUM types ────────────────────────────────────────────────────────
    # Topics
    gspaper = postgresql.ENUM(
        "GS1", "GS2", "GS3", "GS4", "Essay", "Prelims_GS1", "Prelims_GS2",
        name="gspaper", create_type=True,
    )
    examfocus = postgresql.ENUM(
        "Mains", "Prelims", "Both",
        name="examfocus", create_type=True,
    )
    casensitivity = postgresql.ENUM(
        "High", "Medium", "Low",
        name="currentaffairssensitivity", create_type=True,
    )
    diagramtype = postgresql.ENUM(
        "Flowchart", "Map", "Table", "Graph", "None",
        name="diagramtype", create_type=True,
    )

    # Documents
    documenttype = postgresql.ENUM(
        "PYQ", "NCERT", "Book", "Notes", "Syllabus", "Newspaper", "JSON", "Other",
        name="documenttype", create_type=True,
    )
    documentstatus = postgresql.ENUM(
        "Uploaded", "Processing", "Tagged", "Embedded", "Failed",
        name="documentstatus", create_type=True,
    )
    pdftype = postgresql.ENUM(
        "Text", "Scanned", "Mixed",
        name="pdftype", create_type=True,
    )

    # PYQs
    examtype = postgresql.ENUM(
        "Mains", "Prelims",
        name="examtype", create_type=True,
    )
    gsspaper = postgresql.ENUM(
        "GS1", "GS2", "GS3", "GS4", "Essay", "Prelims_GS1", "Prelims_GS2",
        name="gsspaper", create_type=True,
    )
    commandword = postgresql.ENUM(
        "Discuss", "Analyze", "Examine", "Evaluate", "Comment",
        "Critically Examine", "Explain", "Highlight", "Enumerate", "Other",
        name="commandword", create_type=True,
    )
    questiontype = postgresql.ENUM(
        "Conceptual", "Analytical", "Case Study", "Factual",
        "Opinion", "Statement Based", "MCQ",
        name="questiontype", create_type=True,
    )
    difficulty = postgresql.ENUM(
        "Easy", "Medium", "Hard",
        name="difficulty", create_type=True,
    )

    # Current Affairs
    relevancelevel = postgresql.ENUM(
        "High", "Medium", "Low",
        name="relevancelevel", create_type=True,
    )
    examrelevance = postgresql.ENUM(
        "Mains Only", "Prelims Only", "Both", "None",
        name="examrelevance", create_type=True,
    )

    # Visual Assets
    imagetype = postgresql.ENUM(
        "Map", "Table", "Graph", "Diagram", "Flowchart", "Photo", "Infographic", "Other",
        name="imagetype", create_type=True,
    )
    examuse = postgresql.ENUM(
        "Mains Diagram", "Prelims Revision", "Both", "Reference",
        name="examuse", create_type=True,
    )

    # Conversations
    queryintent = postgresql.ENUM(
        "Concept Query", "PYQ Search", "CA Link", "Answer Writing",
        "Weakness Check", "Revision", "Map Query", "Trend Analysis", "General",
        name="queryintent", create_type=True,
    )
    engagementdepth = postgresql.ENUM(
        "Shallow", "Medium", "Deep",
        name="engagementdepth", create_type=True,
    )

    # User Stats
    weaknesslevel = postgresql.ENUM(
        "Critical", "High", "Medium", "Low", "Strong",
        name="weaknesslevel", create_type=True,
    )
    revisiontype = postgresql.ENUM(
        "Daily", "Weekly", "Monthly", "Adhoc",
        name="revisiontype", create_type=True,
    )

    # ══════════════════════════════════════════════════════════════════════
    # 1. topics
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("paper", gspaper, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Float(), server_default="5.0"),
        sa.Column("exam_focus", examfocus, server_default="'Both'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_topics_id", "topics", ["id"])

    # ══════════════════════════════════════════════════════════════════════
    # 2. subtopics
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "subtopics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Float(), server_default="5.0"),
        sa.Column("ca_sensitivity", casensitivity, server_default="'Medium'"),
        sa.Column("exam_focus", examfocus, server_default="'Both'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subtopics_id", "subtopics", ["id"])
    op.create_index("ix_subtopics_topic_id", "subtopics", ["topic_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 3. micro_tags
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "micro_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pyq_weight", sa.Float(), server_default="5.0"),
        sa.Column("current_affairs_weight", sa.Float(), server_default="5.0"),
        sa.Column("diagram_relevant", sa.Boolean(), server_default="false"),
        sa.Column("diagram_type", diagramtype, server_default="'None'"),
        sa.Column("exam_focus", examfocus, server_default="'Both'"),
        sa.Column("answer_type", sa.String(100), nullable=True),
        sa.Column("common_command_words", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_micro_tags_id", "micro_tags", ["id"])
    op.create_index("ix_micro_tags_subtopic_id", "micro_tags", ["subtopic_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 4. documents
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", documenttype, nullable=False),
        sa.Column("pdf_type", pdftype, server_default="'Text'"),
        sa.Column("status", documentstatus, server_default="'Uploaded'"),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size_kb", sa.Float(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("paper", sa.String(50), nullable=True),
        sa.Column("publication", sa.String(200), nullable=True),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("class_level", sa.String(50), nullable=True),
        sa.Column("ocr_applied", sa.Boolean(), server_default="false"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("image_count", sa.Integer(), server_default="0"),
        sa.Column("upload_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_id", "documents", ["id"])

    # ══════════════════════════════════════════════════════════════════════
    # 5. chunks
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id"), nullable=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=True),
        sa.Column("tag_confidence", sa.Float(), server_default="0.0"),
        sa.Column("search_vector", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_id", "chunks", ["id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_topic_id", "chunks", ["topic_id"])
    op.create_index("ix_chunks_subtopic_id", "chunks", ["subtopic_id"])
    op.create_index("ix_chunks_micro_tag_id", "chunks", ["micro_tag_id"])

    # Add vector column separately (Alembic doesn't handle custom types well inline)
    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(3072)")

    # ══════════════════════════════════════════════════════════════════════
    # 6. pyqs
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "pyqs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("exam_type", examtype, nullable=False),
        sa.Column("paper", gsspaper, nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=True),
        sa.Column("marks", sa.Integer(), nullable=True),
        sa.Column("word_limit", sa.Integer(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("option_a", sa.Text(), nullable=True),
        sa.Column("option_b", sa.Text(), nullable=True),
        sa.Column("option_c", sa.Text(), nullable=True),
        sa.Column("option_d", sa.Text(), nullable=True),
        sa.Column("correct_option", sa.String(1), nullable=True),
        sa.Column("option_analysis", sa.Text(), nullable=True),
        sa.Column("model_answer", sa.Text(), nullable=True),
        sa.Column("answer_intro", sa.Text(), nullable=True),
        sa.Column("answer_body", sa.Text(), nullable=True),
        sa.Column("answer_conclusion", sa.Text(), nullable=True),
        sa.Column("diagram_suggested", sa.Boolean(), server_default="false"),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id"), nullable=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=True),
        sa.Column("command_word", commandword, server_default="'Other'"),
        sa.Column("question_type", questiontype, server_default="'Conceptual'"),
        sa.Column("difficulty", difficulty, server_default="'Medium'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pyqs_id", "pyqs", ["id"])
    op.create_index("ix_pyqs_year", "pyqs", ["year"])
    op.create_index("ix_pyqs_exam_type", "pyqs", ["exam_type"])
    op.create_index("ix_pyqs_paper", "pyqs", ["paper"])
    op.create_index("ix_pyqs_topic_id", "pyqs", ["topic_id"])
    op.create_index("ix_pyqs_subtopic_id", "pyqs", ["subtopic_id"])
    op.create_index("ix_pyqs_micro_tag_id", "pyqs", ["micro_tag_id"])

    op.execute("ALTER TABLE pyqs ADD COLUMN embedding vector(3072)")

    # ══════════════════════════════════════════════════════════════════════
    # 7. current_affairs
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "current_affairs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("newspaper_date", sa.Date(), nullable=False),
        sa.Column("publication", sa.String(200), nullable=True),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_facts", sa.Text(), nullable=True),
        sa.Column("upsc_angle", sa.Text(), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id"), nullable=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=True),
        sa.Column("relevance_score", sa.Float(), server_default="5.0"),
        sa.Column("relevance_level", relevancelevel, server_default="'Medium'"),
        sa.Column("exam_relevance", examrelevance, server_default="'Both'"),
        sa.Column("probable_question", sa.Text(), nullable=True),
        sa.Column("mains_dimensions", sa.Text(), nullable=True),
        sa.Column("prelims_facts", sa.Text(), nullable=True),
        sa.Column("static_linkage", sa.Text(), nullable=True),
        sa.Column("has_map_reference", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_current_affairs_id", "current_affairs", ["id"])
    op.create_index("ix_current_affairs_newspaper_date", "current_affairs", ["newspaper_date"])
    op.create_index("ix_current_affairs_source_document_id", "current_affairs", ["source_document_id"])
    op.create_index("ix_current_affairs_topic_id", "current_affairs", ["topic_id"])

    op.execute("ALTER TABLE current_affairs ADD COLUMN embedding vector(3072)")

    # ══════════════════════════════════════════════════════════════════════
    # 8. visual_assets
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "visual_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("image_index", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(1000), nullable=False),
        sa.Column("image_format", sa.String(10), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("image_type", imagetype, server_default="'Other'"),
        sa.Column("exam_use", examuse, server_default="'Reference'"),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("surrounding_text", sa.Text(), nullable=True),
        sa.Column("ai_caption", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("geo_entities", sa.Text(), nullable=True),
        sa.Column("location_tags", sa.Text(), nullable=True),
        sa.Column("table_headers", sa.Text(), nullable=True),
        sa.Column("table_data_summary", sa.Text(), nullable=True),
        sa.Column("process_steps", sa.Text(), nullable=True),
        sa.Column("data_trend", sa.Text(), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id"), nullable=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=True),
        sa.Column("upsc_relevance_note", sa.Text(), nullable=True),
        sa.Column("probable_question", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_visual_assets_id", "visual_assets", ["id"])
    op.create_index("ix_visual_assets_document_id", "visual_assets", ["document_id"])
    op.create_index("ix_visual_assets_topic_id", "visual_assets", ["topic_id"])

    op.execute("ALTER TABLE visual_assets ADD COLUMN embedding vector(3072)")

    # ══════════════════════════════════════════════════════════════════════
    # 9. conversations
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("session_title", sa.String(300), nullable=True),
        sa.Column("turn_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversations_id", "conversations", ["id"])
    op.create_index("ix_conversations_session_date", "conversations", ["session_date"])

    # ══════════════════════════════════════════════════════════════════════
    # 10. conversation_turns
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("assistant_reply", sa.Text(), nullable=False),
        sa.Column("intent", queryintent, server_default="'General'"),
        sa.Column("engagement_depth", engagementdepth, server_default="'Medium'"),
        sa.Column("follow_up_suggested", sa.Boolean(), server_default="false"),
        sa.Column("unresolved_doubt", sa.Boolean(), server_default="false"),
        sa.Column("unresolved_note", sa.Text(), nullable=True),
        sa.Column("system_conclusion", sa.Text(), nullable=True),
        sa.Column("urgency_score", sa.Float(), server_default="5.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_turns_id", "conversation_turns", ["id"])
    op.create_index("ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 11. conversation_topics
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "conversation_topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("conversation_turns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("subtopic_id", sa.Integer(), sa.ForeignKey("subtopics.id"), nullable=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("was_revised", sa.Boolean(), server_default="false"),
        sa.Column("action_taken", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_topics_id", "conversation_topics", ["id"])
    op.create_index("ix_conversation_topics_turn_id", "conversation_topics", ["turn_id"])
    op.create_index("ix_conversation_topics_topic_id", "conversation_topics", ["topic_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 12. user_topic_stats
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "user_topic_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False, unique=True),
        sa.Column("coverage_score", sa.Float(), server_default="0.0"),
        sa.Column("revision_count", sa.Integer(), server_default="0"),
        sa.Column("question_count", sa.Integer(), server_default="0"),
        sa.Column("last_revised", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weakness_score", sa.Float(), server_default="5.0"),
        sa.Column("weakness_level", weaknesslevel, server_default="'Medium'"),
        sa.Column("is_anomaly", sa.Boolean(), server_default="false"),
        sa.Column("anomaly_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_topic_stats_id", "user_topic_stats", ["id"])
    op.create_index("ix_user_topic_stats_topic_id", "user_topic_stats", ["topic_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 13. user_microtag_stats
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "user_microtag_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("micro_tag_id", sa.Integer(), sa.ForeignKey("micro_tags.id"), nullable=False, unique=True),
        sa.Column("confidence_level", sa.Float(), server_default="0.5"),
        sa.Column("times_asked", sa.Integer(), server_default="0"),
        sa.Column("times_revised", sa.Integer(), server_default="0"),
        sa.Column("times_answered_well", sa.Integer(), server_default="0"),
        sa.Column("weak_flag", sa.Boolean(), server_default="false"),
        sa.Column("never_touched", sa.Boolean(), server_default="true"),
        sa.Column("last_interaction", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_revision_due", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_microtag_stats_id", "user_microtag_stats", ["id"])
    op.create_index("ix_user_microtag_stats_micro_tag_id", "user_microtag_stats", ["micro_tag_id"])

    # ══════════════════════════════════════════════════════════════════════
    # 14. revision_logs
    # ══════════════════════════════════════════════════════════════════════
    op.create_table(
        "revision_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("revision_type", revisiontype, nullable=False),
        sa.Column("period_label", sa.String(100), nullable=True),
        sa.Column("topics_covered", sa.Text(), nullable=True),
        sa.Column("weak_areas", sa.Text(), nullable=True),
        sa.Column("ca_highlights", sa.Text(), nullable=True),
        sa.Column("cheat_sheet", sa.Text(), nullable=True),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_revision_logs_id", "revision_logs", ["id"])

    # ══════════════════════════════════════════════════════════════════════
    # Performance indexes for retrieval
    # ══════════════════════════════════════════════════════════════════════
    # HNSW indexes for fast vector search on the 4 embedding tables
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pyqs_embedding_hnsw
        ON pyqs USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_current_affairs_embedding_hnsw
        ON current_affairs USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_visual_assets_embedding_hnsw
        ON visual_assets USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("revision_logs")
    op.drop_table("user_microtag_stats")
    op.drop_table("user_topic_stats")
    op.drop_table("conversation_topics")
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
    op.drop_table("visual_assets")
    op.drop_table("current_affairs")
    op.drop_table("pyqs")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("micro_tags")
    op.drop_table("subtopics")
    op.drop_table("topics")

    # Drop ENUM types
    for enum_name in [
        "revisiontype", "weaknesslevel", "engagementdepth", "queryintent",
        "examuse", "imagetype", "examrelevance", "relevancelevel",
        "difficulty", "questiontype", "commandword", "gsspaper", "examtype",
        "pdftype", "documentstatus", "documenttype",
        "diagramtype", "currentaffairssensitivity", "examfocus", "gspaper",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP EXTENSION IF EXISTS vector")
