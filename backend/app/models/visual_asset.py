"""
models/visual_asset.py
──────────────────────
Maps, tables, graphs, diagrams, and photos extracted from PDFs.

Every image in the system is a first-class knowledge asset, not just
a file. It has:
    - the raw image path (for display)
    - OCR text (any labels/text inside the image)
    - AI-generated caption (what it shows + why UPSC cares)
    - topic tagging
    - vector embedding (of the caption, for semantic retrieval)

So when you ask about Western Ghats biodiversity, the system can
retrieve the map AND explain it.
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


# ── Enums ─────────────────────────────────────────────────────────────────────

class ImageType(str, enum.Enum):
    MAP         = "Map"
    TABLE       = "Table"
    GRAPH       = "Graph"
    DIAGRAM     = "Diagram"
    FLOWCHART   = "Flowchart"
    PHOTO       = "Photo"
    INFOGRAPHIC = "Infographic"
    OTHER       = "Other"


class ExamUse(str, enum.Enum):
    MAINS_DIAGRAM     = "Mains Diagram"     # draw in answer
    PRELIMS_REVISION  = "Prelims Revision"  # location/fact recall
    BOTH              = "Both"
    REFERENCE         = "Reference"         # study reference only


# ── Visual Asset ──────────────────────────────────────────────────────────────

class VisualAsset(Base):
    """
    A single image (map / table / graph / diagram / photo)
    extracted from a PDF page.

    The magic is in ai_caption:
        - AI understands what the image shows
        - relates it to its source topic
        - explains why UPSC cares
        - notes geo_entities, process_steps, or data_points

    This caption is then embedded for semantic retrieval.
    The raw image is always preserved for display.
    """
    __tablename__ = "visual_assets"

    id                  = Column(Integer, primary_key=True, index=True)
    document_id         = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number         = Column(Integer, nullable=True)
    image_index         = Column(Integer, nullable=True)             # order on page

    # ── Storage ────────────────────────────────────────────────────────────
    image_path          = Column(String(1000), nullable=False)       # local path / S3 key
    image_format        = Column(String(10), nullable=True)          # png, jpg, etc.
    width_px            = Column(Integer, nullable=True)
    height_px           = Column(Integer, nullable=True)

    # ── Classification ─────────────────────────────────────────────────────
    image_type          = Column(SAEnum(ImageType), default=ImageType.OTHER)
    exam_use            = Column(SAEnum(ExamUse),   default=ExamUse.REFERENCE)

    # ── Extracted Content ──────────────────────────────────────────────────
    ocr_text            = Column(Text, nullable=True)                # text labels inside image
    surrounding_text    = Column(Text, nullable=True)                # text around image on page

    # ── AI Understanding ───────────────────────────────────────────────────
    ai_caption          = Column(Text, nullable=True)                # full AI description
    ai_summary          = Column(Text, nullable=True)                # 2–3 line concise summary

    # For Maps specifically:
    geo_entities        = Column(Text, nullable=True)                # "Western Ghats, Nilgiri Hills..."
    location_tags       = Column(Text, nullable=True)                # states, countries, rivers

    # For Tables specifically:
    table_headers       = Column(Text, nullable=True)                # column names
    table_data_summary  = Column(Text, nullable=True)                # key trends/comparisons

    # For Graphs/Diagrams:
    process_steps       = Column(Text, nullable=True)                # flowchart steps
    data_trend          = Column(Text, nullable=True)                # graph trend description

    # ── Topic Mapping ──────────────────────────────────────────────────────
    topic_id            = Column(Integer, ForeignKey("topics.id"),     nullable=True, index=True)
    subtopic_id         = Column(Integer, ForeignKey("subtopics.id"),  nullable=True, index=True)
    micro_tag_id        = Column(Integer, ForeignKey("micro_tags.id"), nullable=True, index=True)

    # ── UPSC Relevance ─────────────────────────────────────────────────────
    upsc_relevance_note = Column(Text, nullable=True)                # why this matters for UPSC
    probable_question   = Column(Text, nullable=True)                # question this image could appear in

    # ── Embedding (of ai_caption) ──────────────────────────────────────────
    embedding           = Column(Vector(3072), nullable=True)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    document            = relationship("Document",  back_populates="visual_assets")
    topic               = relationship("Topic",     back_populates="visual_assets")
    subtopic            = relationship("Subtopic",  back_populates="visual_assets")
    micro_tag           = relationship("MicroTag",  back_populates="visual_assets")

    def __repr__(self):
        return (
            f"<VisualAsset id={self.id} type={self.image_type} "
            f"doc_id={self.document_id} page={self.page_number}>"
        )
