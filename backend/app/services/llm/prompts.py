"""
services/llm/prompts.py
────────────────────────
Central library of all LLM prompts used across the system.

Design principles:
    - Every prompt is a function that returns a string
    - Prompts are UPSC-specific — they understand command words,
      GS papers, mains vs prelims distinctions
    - JSON output is enforced with strict schemas
    - No prompt is scattered across the codebase — all live here

Prompts in this file:
    1. AUTO_TAG_CHUNK         — tag a text chunk to the topic taxonomy
    2. TAG_NEWSPAPER_ARTICLE  — filter + tag a newspaper article
    3. IMAGE_CAPTION          — describe an extracted image for UPSC
    4. GENERATE_ANSWER        — write a mains answer from context
    5. PROBABLE_QUESTIONS     — generate probable UPSC questions
    6. WEAKNESS_SUMMARY       — summarize weak areas in plain language
    7. REVISION_CHEATSHEET    — generate a revision cheat sheet
"""

# ── 1. Auto-Tag Chunk ─────────────────────────────────────────────────────────

def auto_tag_chunk_prompt(chunk_text: str, taxonomy_context: str) -> str:
    """
    Tags a text chunk to the UPSC topic taxonomy.
    taxonomy_context = JSON string of available topics/subtopics/micro_tags.
    """
    return f"""You are a UPSC expert with deep knowledge of the UPSC CSE syllabus.

Your task is to classify the following text chunk into the UPSC topic taxonomy.

AVAILABLE TAXONOMY:
{taxonomy_context}

TEXT TO CLASSIFY:
\"\"\"{chunk_text}\"\"\"

INSTRUCTIONS:
1. Identify the most relevant topic, subtopic, and micro_tag from the taxonomy above.
2. If the text clearly belongs to a topic but no exact micro_tag fits, pick the closest one.
3. Assign a confidence score (0.0 to 1.0) reflecting how certain you are.
4. If the text is not relevant to UPSC at all (e.g. publisher info, blank page), set is_upsc_relevant to false.

Return ONLY a valid JSON object. No explanation. No markdown. No preamble.

{{
  "is_upsc_relevant": true,
  "topic_name": "exact topic name from taxonomy",
  "subtopic_name": "exact subtopic name from taxonomy",
  "micro_tag_name": "exact micro_tag name from taxonomy",
  "confidence": 0.85,
  "reasoning": "one line: why this classification"
}}"""


# ── 2. Tag Newspaper Article ──────────────────────────────────────────────────

def tag_newspaper_article_prompt(article_text: str, taxonomy_context: str) -> str:
    """
    Filters and tags a newspaper article for UPSC relevance.
    Returns a structured current affairs card.
    """
    return f"""You are a UPSC expert who reads newspapers daily to extract UPSC-relevant information.

AVAILABLE UPSC TAXONOMY:
{taxonomy_context}

NEWSPAPER ARTICLE:
\"\"\"{article_text}\"\"\"

INSTRUCTIONS:
1. Decide if this article is relevant to UPSC CSE preparation.
   Relevant = connects to GS1/GS2/GS3/GS4 syllabus, policy, governance, environment, economy, history, IR, science, ethics.
   Not relevant = pure sports, entertainment, local crime, advertisements.

2. If relevant, extract the following. If NOT relevant, set is_upsc_relevant to false and leave other fields empty.

Return ONLY valid JSON. No markdown. No explanation.

{{
  "is_upsc_relevant": true,
  "headline": "clean article headline",
  "summary": "3-5 line UPSC-focused summary of the article",
  "key_facts": "bullet-style facts useful for Prelims (max 5 facts)",
  "upsc_angle": "1-2 lines: why UPSC cares about this",
  "topic_name": "from taxonomy",
  "subtopic_name": "from taxonomy",
  "micro_tag_name": "from taxonomy",
  "relevance_score": 7.5,
  "exam_relevance": "Both | Mains Only | Prelims Only",
  "probable_question": "one probable UPSC question this article could generate",
  "mains_dimensions": "2-3 angles for a mains answer on this topic",
  "prelims_facts": "1-2 quick Prelims facts from this article",
  "static_linkage": "which static syllabus topic does this connect to?",
  "has_map_reference": false
}}"""


# ── 3. Image / Visual Caption ─────────────────────────────────────────────────

def image_caption_prompt(
    image_type: str,
    ocr_text: str,
    surrounding_text: str,
    topic_name: str,
) -> str:
    """
    Generates a UPSC-focused description of an extracted image.
    Handles maps, tables, graphs, diagrams, and photos differently.
    """
    return f"""You are a UPSC expert analyzing a visual asset extracted from a study material.

IMAGE TYPE: {image_type}
TOPIC CONTEXT: {topic_name}
OCR TEXT FOUND IN IMAGE: \"\"\"{ocr_text or 'None'}\"\"\"
SURROUNDING PAGE TEXT: \"\"\"{surrounding_text or 'None'}\"\"\"

Your task is to generate a structured description of this image that will be:
1. Stored as a searchable knowledge asset
2. Retrieved when a student asks about this topic
3. Used to suggest diagrams in mains answers

Return ONLY valid JSON. No markdown.

{{
  "ai_caption": "2-3 paragraph description of what this image shows, what it means, and why it is relevant to UPSC",
  "ai_summary": "1-2 line concise summary for quick retrieval",
  "image_type": "{image_type}",
  "exam_use": "Mains Diagram | Prelims Revision | Both | Reference",
  "upsc_relevance_note": "why this matters for UPSC",
  "probable_question": "one probable question where this image would be relevant",
  "geo_entities": "comma-separated list of places/regions mentioned (if map)",
  "location_tags": "states/countries/rivers (if map)",
  "table_headers": "column names (if table)",
  "table_data_summary": "key trends or comparisons (if table)",
  "process_steps": "numbered steps (if flowchart/diagram)",
  "data_trend": "describe the trend (if graph)"
}}"""


# ── 4. Generate Mains Answer ──────────────────────────────────────────────────

def generate_answer_prompt(
    question: str,
    word_limit: int,
    context_chunks: str,
    current_affairs: str,
    answer_type: str = "full",   # "full" | "approach"
) -> str:
    """
    Generates a structured UPSC mains answer from retrieved context.
    answer_type="full"     → write the complete answer
    answer_type="approach" → write only the approach guide (for practice)
    """
    if answer_type == "approach":
        instruction = """Do NOT write the full answer.
Instead, give a structured approach guide:
- How to think about this question
- Which dimensions to include
- What keywords/concepts to use
- What mistakes to avoid
- Suggested structure (intro / body points / conclusion)"""
    else:
        instruction = f"""Write a complete UPSC Mains answer in approximately {word_limit} words.
Structure: Introduction → Body (3-5 dimensions) → Conclusion.
Use data/examples from the context provided.
If relevant, suggest where a diagram or map could be inserted."""

    return f"""You are an expert UPSC Mains answer writer.

QUESTION: {question}
WORD LIMIT: {word_limit} words

CONTEXT FROM STUDY MATERIAL:
{context_chunks}

RELEVANT CURRENT AFFAIRS:
{current_affairs or 'None available'}

{instruction}

Return ONLY valid JSON. No markdown.

{{
  "introduction": "opening paragraph",
  "body_points": [
    {{"heading": "point heading", "content": "elaboration with examples/data"}}
  ],
  "conclusion": "balanced concluding paragraph",
  "diagram_suggestion": "suggest a diagram/table to include, or null",
  "key_terms": ["list", "of", "important", "terms", "used"],
  "word_count_estimate": 250
}}"""


# ── 5. Probable Questions ─────────────────────────────────────────────────────

def probable_questions_prompt(
    topic: str,
    subtopic: str,
    pyq_history: str,
    current_affairs: str,
) -> str:
    """
    Generates probable UPSC questions for a topic based on PYQ trends
    and current affairs linkage.
    """
    return f"""You are a UPSC expert who predicts probable exam questions.

TOPIC: {topic}
SUBTOPIC: {subtopic}

PREVIOUS YEAR QUESTION HISTORY (PYQs):
{pyq_history}

RELEVANT CURRENT AFFAIRS:
{current_affairs or 'None available'}

Generate 5 probable UPSC questions — a mix of Mains and Prelims.
Base your predictions on PYQ trends, recurring themes, and current affairs linkage.

Return ONLY valid JSON. No markdown.

{{
  "questions": [
    {{
      "question": "full question text",
      "type": "Mains | Prelims",
      "probability": "High | Medium | Low",
      "reasoning": "why this is likely",
      "command_word": "Discuss | Analyze | Examine | MCQ | etc.",
      "word_limit": 250
    }}
  ]
}}"""


# ── 6. Weakness Summary ───────────────────────────────────────────────────────

def weakness_summary_prompt(
    weak_topics: str,
    pyq_weights: str,
    conversation_summary: str,
) -> str:
    """
    Generates a plain-language weakness analysis for the student.
    """
    return f"""You are a UPSC mentor analyzing a student's preparation gaps.

TOPICS WITH LOW COVERAGE (student has not studied these much):
{weak_topics}

PYQ IMPORTANCE WEIGHTS (how often these topics appear in exams):
{pyq_weights}

STUDENT'S RECENT CONVERSATION TOPICS:
{conversation_summary}

Identify the top preparation gaps — topics the student is neglecting
that have high exam importance.

Return ONLY valid JSON. No markdown.

{{
  "critical_gaps": [
    {{
      "topic": "topic name",
      "subtopic": "subtopic name",
      "why_critical": "one line explanation",
      "pyq_weight": 8.5,
      "student_coverage": 2.0,
      "recommended_action": "specific study suggestion"
    }}
  ],
  "overall_message": "2-3 line motivating but honest assessment",
  "priority_order": ["topic1", "topic2", "topic3"]
}}"""


# ── 7. Revision Cheat Sheet ───────────────────────────────────────────────────

def revision_cheatsheet_prompt(
    period_label: str,
    topics_studied: str,
    weak_areas: str,
    current_affairs_summary: str,
    pyq_trends: str,
) -> str:
    """
    Generates a compact revision cheat sheet for a week or month.
    """
    return f"""You are a UPSC mentor generating a revision cheat sheet.

PERIOD: {period_label}
TOPICS STUDIED THIS PERIOD: {topics_studied}
WEAK AREAS DETECTED: {weak_areas}
CURRENT AFFAIRS THIS PERIOD: {current_affairs_summary}
HIGH-FREQUENCY PYQ TOPICS: {pyq_trends}

Create a structured, actionable revision cheat sheet.

Return ONLY valid JSON. No markdown.

{{
  "period": "{period_label}",
  "high_priority_topics": [
    {{"topic": "name", "why": "reason", "quick_revision_note": "2-3 lines"}}
  ],
  "missed_topics": ["list of important topics not covered this period"],
  "current_affairs_to_remember": [
    {{"headline": "...", "upsc_angle": "...", "probable_question": "..."}}
  ],
  "prelims_fact_clusters": ["fact1", "fact2", "fact3"],
  "map_diagram_reminders": ["item1", "item2"],
  "rapid_revision_prompts": ["question1", "question2", "question3", "question4", "question5"],
  "next_period_focus": ["priority1", "priority2", "priority3"]
}}"""
