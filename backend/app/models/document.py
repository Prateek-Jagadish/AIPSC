"""
models/document.py
──────────────────
Represents every source file that enters the system.
A Document is the parent; Chunks are its processed, tagged, embedded pieces.

Tables:
    documents  → metadata about uploaded files
    chunks     → extracted, tagged, embedded text blocks (the RAG core)
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Enum as SAEnum, DateTime, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum

from app.core.database import Base
from app.core.config import settings


# ── Enums ─────────────────────────────────────────────────────────────────────

class DocumentType(str, enum.Enum):
    PYQ        = "PYQ"           # Previous Year Question paper
    NCERT      = "NCERT"         # NCERT textbook
    BOOK       = "Book"          # Standard reference book
    NOTES      = "Notes"         # Personal class/study notes
    SYLLABUS   = "Syllabus"      # Official UPSC syllabus
    NEWSPAPER  = "Newspaper"     # Daily newspaper
    JSON       = "JSON"          # PYQ JSON with model answers
    OTHER      = "Other"


class DocumentStatus(str, enum.Enum):
    UPLOADED    = "Uploaded"     # File received, not yet processed
    PROCESSING  = "Processing"   # OCR / extraction in progress
    TAGGED      = "Tagged"       # Topics auto-tagged
    EMBEDDED    = "Embedded"     # Embeddings stored in pgvector
    FAILED      = "Failed"       # Processing error


class PDFType(str, enum.Enum):
    TEXT_BASED  = "Text"         # Selectable text PDF
    SCANNED     = "Scanned"      # Image-only, needs OCR
    MIXED       = "Mixed"        # Some pages text, some scanned


# ── Document ──────────────────────────────────────────────────────────────────

class Document(Base):
    """
    Every file uploaded to the system (PDF, JSON, etc.)
    Tracks its origin, processing status, and storage location.
    """
    __tablename__ = "documents"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(500), nullable=False)
    source_type     = Column(SAEnum(DocumentType), nullable=False)
    pdf_type        = Column(SAEnum(PDFType), default=PDFType.TEXT_BASED)
    status          = Column(SAEnum(DocumentStatus), default=DocumentStatus.UPLOADED)

    # ── Storage ────────────────────────────────────────────────────────────
    file_path       = Column(String(1000), nullable=False)   # local path / S3 key
    file_size_kb    = Column(Float, nullable=True)
    page_count      = Column(Integer, nullable=True)

    # ── Source Metadata ────────────────────────────────────────────────────
    # For PYQs
    year            = Column(Integer, nullable=True)         # e.g. 2023
    paper           = Column(String(50), nullable=True)      # e.g. "GS2", "Essay"

    # For newspapers
    publication     = Column(String(200), nullable=True)     # e.g. "The Hindu"
    publish_date    = Column(DateTime(timezone=True), nullable=True)

    # For books / NCERTs
    subject         = Column(String(200), nullable=True)
    class_level     = Column(String(50), nullable=True)      # e.g. "Class 10"

    # ── Processing ─────────────────────────────────────────────────────────
    ocr_applied     = Column(Boolean, default=False)
    error_message   = Column(Text, nullable=True)            # if status=Failed
    chunk_count     = Column(Integer, default=0)
    image_count     = Column(Integer, default=0)

    upload_date     = Column(DateTime(timezone=True), server_default=func.now())
    processed_at    = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    chunks          = relationship("Chunk",       back_populates="document", cascade="all, delete-orphan")
    visual_assets   = relationship("VisualAsset", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document id={self.id} title='{self.title}' type={self.source_type} status={self.status}>"


# ── Chunk ─────────────────────────────────────────────────────────────────────

class Chunk(Base):
    """
    A processed, tagged, embedded block of text from a Document.
    This is the fundamental unit used by the RAG retrieval system.

    Each chunk:
    - belongs to a Document (+ page number)
    - is tagged to topic / subtopic / micro_tag
    - has a vector embedding for semantic search
    - has a tsvector for keyword search (managed by PostgreSQL trigger)
    """
    __tablename__ = "chunks"

    id              = Column(Integer, primary_key=True, index=True)
    document_id     = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Content ────────────────────────────────────────────────────────────
    text            = Column(Text, nullable=False)
    page_number     = Column(Integer, nullable=True)
    chunk_index     = Column(Integer, nullable=True)         # sequence within doc

    # ── Topic Tagging (the intelligence anchor) ────────────────────────────
    topic_id        = Column(Integer, ForeignKey("topics.id"),    nullable=True, index=True)
    subtopic_id     = Column(Integer, ForeignKey("subtopics.id"), nullable=True, index=True)
    micro_tag_id    = Column(Integer, ForeignKey("micro_tags.id"),nullable=True, index=True)
    tag_confidence  = Column(Float, default=0.0)             # 0.0 – 1.0

    # ── Vector Embedding ───────────────────────────────────────────────────
    # Dimension 3072 = text-embedding-3-large output size
    embedding       = Column(Vector(3072), nullable=True)

    # ── Full-text Search (PostgreSQL tsvector) ─────────────────────────────
    # Populated by a DB trigger or background job
    search_vector   = Column(Text, nullable=True)            # stores tsvector as text

    # ── Metadata ───────────────────────────────────────────────────────────
    token_count     = Column(Integer, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    document        = relationship("Document",  back_populates="chunks")
    topic           = relationship("Topic",     back_populates="chunks")
    subtopic        = relationship("Subtopic",  back_populates="chunks")
    micro_tag       = relationship("MicroTag",  back_populates="chunks")

    def __repr__(self):
        return (
            f"<Chunk id={self.id} doc_id={self.document_id} "
            f"page={self.page_number} topic_id={self.topic_id}>"
        )
