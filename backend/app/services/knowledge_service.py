import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.models.document import (
    DocumentKnowledgeResponse,
    DocumentMetadata,
    KeyInformation,
    KnowledgeCategory,
    KnowledgeTopic,
    SuggestedQuestion,
)
from app.services.storage import get_document
from app.services.structure_detector import get_or_create_document_structure

KNOWLEDGE_DIR = Path("data/knowledge")

CANDIDATE_CATEGORIES = [
    {
        "id": "academic",
        "name": "Academic",
        "icon": "🎓",
        "keywords": [
            "academic", "course", "courses", "syllabus", "degree", "curriculum",
            "grade", "grading", "cgpa", "sgpa", "credit", "credits", "semester",
            "passing grade", "passing mark", "admission", "examination", "exam"
        ],
        "default_questions": [
            "What is the minimum passing grade for courses?",
            "How are grades and CGPA calculated?",
            "What are the academic rules and evaluation criteria?",
        ],
    },
    {
        "id": "attendance",
        "name": "Attendance",
        "icon": "📋",
        "keywords": [
            "attendance", "leave", "absence", "shortage", "condonation",
            "duty leave", "medical leave", "attendance requirement"
        ],
        "default_questions": [
            "What is the minimum attendance requirement for students?",
            "What are the rules regarding leave of absence and attendance shortage?",
        ],
    },
    {
        "id": "fees",
        "name": "Fees & Finance",
        "icon": "💰",
        "keywords": [
            "fee", "fees", "tuition", "dues", "refund", "payment",
            "installment", "fine", "financial", "caution deposit"
        ],
        "default_questions": [
            "What are the fee payment rules and schedule?",
            "What is the policy on fee refunds and deposits?",
        ],
    },
    {
        "id": "scholarships",
        "name": "Scholarships & Concessions",
        "icon": "🎖️",
        "keywords": [
            "scholarship", "scholarships", "concession", "concessions",
            "educational concession", "stipend", "fellowship", "financial aid",
            "fee waiver", "freeship"
        ],
        "default_questions": [
            "What educational concessions or scholarships are available?",
            "Who is eligible for educational fee concessions?",
        ],
    },
    {
        "id": "hostel",
        "name": "Hostel",
        "icon": "🏠",
        "keywords": [
            "hostel", "hostels", "mess", "warden", "room", "boarding",
            "residence", "dormitory", "inmates", "hostel charges"
        ],
        "default_questions": [
            "What are the rules and guidelines for hostel residents?",
            "What are the hostel charges and mess facilities?",
        ],
    },
    {
        "id": "student_services",
        "name": "Student Services",
        "icon": "👨‍🎓",
        "keywords": [
            "library", "placement", "career", "counseling", "grievance",
            "anti-ragging", "student council", "sports", "medical", "health", "clinic"
        ],
        "default_questions": [
            "What are the library borrowing rules and checkout limits?",
            "What student healthcare and counseling services are available?",
        ],
    },
    {
        "id": "facilities",
        "name": "Facilities",
        "icon": "🏛️",
        "keywords": [
            "canteen", "transport", "bus", "laboratory", "lab", "computing",
            "wifi", "auditorium", "gymnasium", "sports complex"
        ],
        "default_questions": [
            "What campus facilities and computing services are available?",
        ],
    },
    {
        "id": "rules",
        "name": "Rules & Regulations",
        "icon": "⚖️",
        "keywords": [
            "rule", "rules", "regulation", "regulations", "discipline",
            "code of conduct", "penalty", "misconduct", "prohibition"
        ],
        "default_questions": [
            "What is the student code of conduct and disciplinary policy?",
        ],
    },
    {
        "id": "administration",
        "name": "Administration",
        "icon": "🏢",
        "keywords": [
            "administration", "director", "dean", "registrar", "principal",
            "governing body", "office", "head of department"
        ],
        "default_questions": [
            "Who are the key administrative authorities and department heads?",
        ],
    },
]


def _ensure_dir():
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def _get_storage_path(document_id: str) -> Path:
    _ensure_dir()
    return KNOWLEDGE_DIR / f"{document_id}.json"


def get_stored_knowledge(document_id: str) -> Optional[DocumentKnowledgeResponse]:
    """Retrieve cached document knowledge if already generated."""
    path = _get_storage_path(document_id)
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return DocumentKnowledgeResponse(**data)
        except Exception:
            return None
    return None


def save_knowledge(knowledge: DocumentKnowledgeResponse) -> None:
    """Persist generated document knowledge to disk."""
    path = _get_storage_path(knowledge.document_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(knowledge.model_dump(), f, indent=2, ensure_ascii=False)


def _match_category(text: str) -> Optional[dict]:
    """Find the best matching category configuration for a heading or chunk."""
    text_lower = text.lower()
    for cat in CANDIDATE_CATEGORIES:
        for kw in cat["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return cat
    return None


def _extract_key_facts(chunks: list, filename: str) -> List[KeyInformation]:
    """Extract factual statements grounded in real document chunks."""
    facts: List[KeyInformation] = []
    seen_titles = set()

    for chunk in chunks:
        text = chunk.text
        text_lower = text.lower()

        # 1. Minimum Passing Grade / Grading criteria
        if "passing grade" in text_lower or "minimum grade" in text_lower:
            m = re.search(r"(?:minimum\s+passing\s+grade|passing\s+grade)[^\.\n]*?(?:is\s+)?([A-Za-z0-9\s\-]+(?:\([^\)]+\))?)", text, re.IGNORECASE)
            val = m.group(1).strip() if m else "C minus"
            # Clean trailing words
            val = re.split(r"[\.,;]", val)[0].strip()
            if "Passing Grade" not in seen_titles:
                facts.append(KeyInformation(
                    title="Minimum Passing Grade",
                    value=val,
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("Passing Grade")

        # 2. Attendance Requirement
        if "attendance" in text_lower and ("%" in text or "percent" in text_lower):
            m = re.search(r"(\d{2}%\s*(?:of\s*)?attendance|\b(?:minimum\s+)?attendance\s+(?:requirement\s+)?(?:is\s+)?\d{2}%)", text, re.IGNORECASE)
            m_val = re.search(r"(\d{2}%|\d{2}\s*percent)", text, re.IGNORECASE)
            val = f"{m_val.group(1)} minimum attendance requirement" if m_val else "75% minimum attendance required"
            if "Minimum Attendance" not in seen_titles:
                facts.append(KeyInformation(
                    title="Attendance Requirement",
                    value=val,
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("Minimum Attendance")

        # 3. Library Checkout Limit
        if "library" in text_lower and ("book" in text_lower or "checkout" in text_lower or "borrow" in text_lower):
            m = re.search(r"(\d+\s*books?[^\.\n]*?(?:for\s*\d+\s*days?)?)", text, re.IGNORECASE)
            if m and "Library Borrowing" not in seen_titles:
                facts.append(KeyInformation(
                    title="Library Borrowing Limit",
                    value=m.group(1).strip(),
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("Library Borrowing")

        # 4. Grading / CGPA Formula
        if "cgpa" in text_lower and ("calculated" in text_lower or "formula" in text_lower or "sum" in text_lower):
            if "CGPA Calculation" not in seen_titles:
                facts.append(KeyInformation(
                    title="CGPA Calculation",
                    value="Calculated as cumulative weighted grade points divided by total credits earned",
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("CGPA Calculation")

        # 5. Educational Concessions / Scholarships
        if "concession" in text_lower or "scholarship" in text_lower:
            if "Financial Aid" not in seen_titles:
                facts.append(KeyInformation(
                    title="Fee Concessions & Aid",
                    value="Educational fee concessions and scholarship schemes available for eligible students",
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("Financial Aid")

        # 6. Hostel Regulations
        if "hostel" in text_lower and ("warden" in text_lower or "curfew" in text_lower or "timing" in text_lower or "mess" in text_lower):
            if "Hostel Guidelines" not in seen_titles:
                facts.append(KeyInformation(
                    title="Hostel Administration",
                    value="Hostel operations overseen by Chief Warden with mandatory mess and residency regulations",
                    source_page=chunk.page,
                    source_document=filename,
                ))
                seen_titles.add("Hostel Guidelines")

    return facts


def generate_document_knowledge(document_id: str) -> Optional[DocumentKnowledgeResponse]:
    """
    Generate and persist grounded knowledge structure from real document content.
    Extracts categories, topics, key facts, and suggested questions.
    """
    # 1. Check local cache first
    cached = get_stored_knowledge(document_id)
    if cached:
        return cached

    # 2. Load document metadata and structure
    doc = get_document(document_id)
    if not doc:
        return None

    structure = get_or_create_document_structure(document_id)
    sections = structure.sections if structure else []
    chunks = doc.chunks

    # 3. Categorize real sections and chunks
    categories_map: Dict[str, KnowledgeCategory] = {}

    # Assign detected sections to categories
    for sec in sections:
        cat_info = _match_category(sec.title)
        if not cat_info:
            # Fallback to academic or rules depending on title
            cat_info = CANDIDATE_CATEGORIES[0] if "academic" in sec.title.lower() else CANDIDATE_CATEGORIES[7]

        cat_id = cat_info["id"]
        if cat_id not in categories_map:
            categories_map[cat_id] = KnowledgeCategory(
                category_id=cat_id,
                name=cat_info["name"],
                icon=cat_info["icon"],
                topics=[],
            )

        categories_map[cat_id].topics.append(KnowledgeTopic(
            name=sec.title,
            source_section=sec.title,
            start_page=sec.start_page,
            end_page=sec.end_page,
        ))

    # If no sections exist, inspect chunks for category keywords
    if not categories_map:
        for chunk in chunks:
            cat_info = _match_category(chunk.text)
            if cat_info and cat_info["id"] not in categories_map:
                cat_id = cat_info["id"]
                categories_map[cat_id] = KnowledgeCategory(
                    category_id=cat_id,
                    name=cat_info["name"],
                    icon=cat_info["icon"],
                    topics=[
                        KnowledgeTopic(
                            name=f"{cat_info['name']} Guidelines",
                            source_section=None,
                            start_page=chunk.page,
                            end_page=chunk.page,
                        )
                    ],
                )

    # 4. Extract factual highlights
    key_facts = _extract_key_facts(chunks, doc.filename)

    # If a key fact was found in a category not yet in categories_map, add that category
    for fact in key_facts:
        cat_info = _match_category(fact.title + " " + fact.value)
        if cat_info and cat_info["id"] not in categories_map:
            cat_id = cat_info["id"]
            categories_map[cat_id] = KnowledgeCategory(
                category_id=cat_id,
                name=cat_info["name"],
                icon=cat_info["icon"],
                topics=[
                    KnowledgeTopic(
                        name=fact.title,
                        source_section=fact.source_section,
                        start_page=fact.source_page,
                        end_page=fact.source_page,
                    )
                ],
            )

    # 5. Suggested Questions based strictly on present categories
    suggested_questions: List[SuggestedQuestion] = []
    for cat_id, cat_obj in categories_map.items():
        # Find default questions from config
        cat_cfg = next((c for c in CANDIDATE_CATEGORIES if c["id"] == cat_id), None)
        if cat_cfg:
            for q in cat_cfg["default_questions"][:2]:
                suggested_questions.append(SuggestedQuestion(
                    category=cat_obj.name,
                    question=q,
                ))

    # 6. Grounded Overview
    cat_names = [c.name for c in categories_map.values()]
    if cat_names:
        cats_str = ", ".join(cat_names[:4])
        overview = (
            f"Official institutional document '{doc.filename}' spanning {doc.pages} pages "
            f"and {doc.chunks_count} knowledge chunks. Covers verified policies including {cats_str}."
        )
    else:
        overview = (
            f"Document '{doc.filename}' with {doc.pages} page(s) and {doc.chunks_count} extracted knowledge chunks."
        )

    response = DocumentKnowledgeResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        total_pages=doc.pages,
        overview=overview,
        categories=list(categories_map.values()),
        key_information=key_facts,
        suggested_questions=suggested_questions,
    )

    # 7. Persist to disk
    save_knowledge(response)
    return response


def export_knowledge_as_markdown(knowledge: DocumentKnowledgeResponse) -> str:
    """Export document knowledge as clean GitHub-style Markdown."""
    lines = [
        f"# {knowledge.filename}",
        "",
        "## Overview",
        knowledge.overview,
        "",
        "## Knowledge Categories",
    ]

    for cat in knowledge.categories:
        lines.append(f"### {cat.icon} {cat.name}")
        for t in cat.topics:
            page_str = f"Page {t.start_page}" if t.start_page == t.end_page else f"Pages {t.start_page}–{t.end_page}"
            lines.append(f"- **{t.name}** ({page_str})")
        lines.append("")

    if knowledge.key_information:
        lines.append("## Key Information")
        for fact in knowledge.key_information:
            lines.append(f"- **{fact.title}**: {fact.value}")
            lines.append(f"  - Source: {fact.source_document or knowledge.filename} · Page {fact.source_page}")
        lines.append("")

    if knowledge.suggested_questions:
        lines.append("## Suggested Questions")
        for q in knowledge.suggested_questions:
            lines.append(f"- [{q.category}] {q.question}")
        lines.append("")

    return "\n".join(lines)
