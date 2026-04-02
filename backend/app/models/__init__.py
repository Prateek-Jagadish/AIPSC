"""
models/__init__.py
──────────────────
Import ALL models here so that:
    1. SQLAlchemy's Base.metadata knows about every table
    2. Alembic can auto-detect and generate migrations
    3. Any file that does `from app.models import *` gets everything

Order matters — import parent models before child models.
"""

from app.models.topic          import Topic, Subtopic, MicroTag
from app.models.document       import Document, Chunk
from app.models.pyq            import PYQ
from app.models.current_affair import CurrentAffair
from app.models.visual_asset   import VisualAsset
from app.models.conversation   import Conversation, ConversationTurn, ConversationTopic
from app.models.user_stats     import UserTopicStat, UserMicroTagStat, RevisionLog

__all__ = [
    "Topic", "Subtopic", "MicroTag",
    "Document", "Chunk",
    "PYQ",
    "CurrentAffair",
    "VisualAsset",
    "Conversation", "ConversationTurn", "ConversationTopic",
    "UserTopicStat", "UserMicroTagStat", "RevisionLog",
]
