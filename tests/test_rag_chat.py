import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.models.chat import ChatResponse
from app.models.document import Chunk
from app.models.search import SearchResult
from app.services.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
    clean_model_output,
)
from app.services.rag_service import (
    NO_EVIDENCE_ANSWER,
    RAGService,
    get_rag_service,
)

client = TestClient(app)


# ==============================================================================
# 1. Output Cleaner Tests
# ==============================================================================

def test_clean_model_output_removes_thinking_tags():
    raw_with_think = "<think>Let me calculate attendance: 75%.</think>The minimum attendance requirement is 75%."
    cleaned = clean_model_output(raw_with_think)
    assert cleaned == "The minimum attendance requirement is 75%."
    assert "<think>" not in cleaned


def test_clean_model_output_plain_text():
    plain = "The minimum attendance is 75%."
    assert clean_model_output(plain) == plain


# ==============================================================================
# 2. RAG Service Unit Tests
# ==============================================================================

def test_rag_service_pipeline_calls_retrieval_and_builds_sources():
    # Mock vector store
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 5
    mock_vs.search.return_value = [
        SearchResult(
            chunk_id="doc1_page1_chunk1",
            document_id="doc1",
            text="All students must maintain 75% attendance.",
            source="College_Handbook_2026.pdf",
            page=1,
            score=0.82,
        ),
        SearchResult(
            chunk_id="doc1_page2_chunk1",
            document_id="doc1",
            text="Absences exceeding 3 days require a medical certificate.",
            source="College_Handbook_2026.pdf",
            page=2,
            score=0.74,
        ),
    ]

    # Mock Ollama client
    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = "The minimum attendance requirement is 75%."

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama, similarity_threshold=0.25)
    response = service.answer_question("What is the attendance requirement?")

    assert response.answer == "The minimum attendance requirement is 75%."
    assert len(response.sources) == 2
    assert response.sources[0].document == "College_Handbook_2026.pdf"
    assert response.sources[0].page == 1
    assert response.sources[1].page == 2

    # Verify existing retrieval was called
    mock_vs.search.assert_called_once()
    # Verify prompt passed to Ollama includes the context chunks
    call_args = mock_ollama.generate.call_args
    passed_prompt = call_args.kwargs.get("prompt") or call_args.args[0]
    assert "75% attendance" in passed_prompt
    assert "College_Handbook_2026.pdf" in passed_prompt


def test_rag_service_deduplicates_redundant_chunks():
    # Mock vector store returning duplicates of the same text
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 10
    mock_vs.search.return_value = [
        SearchResult(
            chunk_id="doc1_chunk1",
            document_id="doc1",
            text="Minimum passing grade for undergraduate courses is C minus.",
            source="Academic_Rules.pdf",
            page=1,
            score=0.58,
        ),
        SearchResult(
            chunk_id="doc2_chunk1",
            document_id="doc2",
            text="Minimum passing grade for undergraduate courses is C minus.",
            source="Academic_Rules.pdf",
            page=1,
            score=0.58,
        ),
        SearchResult(
            chunk_id="doc3_chunk1",
            document_id="doc3",
            text="Grade A+ is awarded for 95% - 100%.",
            source="College_Handbook_2026.pdf",
            page=2,
            score=0.48,
        ),
    ]

    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = "95% - 100% is required for an A+ grade."

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama, similarity_threshold=0.25, top_k=2)
    response = service.answer_question("What is required for an A+ grade?")

    assert response.answer == "95% - 100% is required for an A+ grade."
    # Verified deduplication: 1 duplicate removed, leaving 2 unique chunks
    assert len(response.sources) == 2
    assert response.sources[0].document == "Academic_Rules.pdf"
    assert response.sources[1].document == "College_Handbook_2026.pdf"
    assert response.sources[1].page == 2

    # Verify candidate retrieval requests a wider pool
    _, search_kwargs = mock_vs.search.call_args
    assert search_kwargs.get("top_k", 0) >= 6


def test_rag_service_q5_grading_criteria_retrieval_and_citation():
    """Verify Q5 (A+ percentage) retrieves page 2 grading chunk despite duplicate doc chunks."""
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 15
    mock_vs.search.return_value = [
        SearchResult(
            chunk_id="test_doc_p1",
            document_id="test_doc",
            text="Minimum passing grade for undergraduate courses is C minus.",
            source="Academic_Rules.pdf",
            page=1,
            score=0.58,
        ),
        SearchResult(
            chunk_id="test_doc_p1_dup",
            document_id="test_doc_2",
            text="Minimum passing grade for undergraduate courses is C minus.",
            source="Academic_Rules.pdf",
            page=1,
            score=0.58,
        ),
        SearchResult(
            chunk_id="handbook_p2",
            document_id="doc_handbook",
            text="Section 4.2: Grading Criteria - Grade A+ (95% - 100%): Exceptional mastery (10.0 grade points)",
            source="College_Handbook_2026.pdf",
            page=2,
            score=0.485,
        ),
    ]

    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = "Grade A+ is awarded for 95% - 100% (10.0 grade points)."

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama, similarity_threshold=0.25, top_k=3)
    response = service.answer_question("What percentage is required to receive an A+ grade?")

    assert "95%" in response.answer
    assert any(s.document == "College_Handbook_2026.pdf" and s.page == 2 for s in response.sources)


def test_rag_service_q9_library_checkout_retrieval_and_citation():
    """Verify Q9 (library checkout limits) retrieves page 3 library chunk despite page 1 chunks."""
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 15
    mock_vs.search.return_value = [
        SearchResult(
            chunk_id="handbook_p1_dup1",
            document_id="doc1",
            text="Page 1: Welcome to the University Handbook. All students must attend 75% of classes.",
            source="College_Handbook.pdf",
            page=1,
            score=0.49,
        ),
        SearchResult(
            chunk_id="handbook_p1_dup2",
            document_id="doc2",
            text="Page 1: Welcome to the University Handbook. All students must attend 75% of classes.",
            source="College_Handbook.pdf",
            page=1,
            score=0.49,
        ),
        SearchResult(
            chunk_id="handbook_p3",
            document_id="doc_handbook",
            text="Section 7.0: Library Facilities. Undergraduate students may check out up to 5 books for a duration of 14 days.",
            source="College_Handbook_2026.pdf",
            page=3,
            score=0.486,
        ),
    ]

    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = "Undergraduate students may check out up to 5 books for a duration of 14 days."

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama, similarity_threshold=0.25, top_k=3)
    response = service.answer_question("How many books can an undergraduate student check out and for how long?")

    assert "5 books" in response.answer
    assert "14 days" in response.answer
    assert any(s.document == "College_Handbook_2026.pdf" and s.page == 3 for s in response.sources)




def test_rag_service_insufficient_evidence_when_scores_low():
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 1
    # Search score below similarity threshold
    mock_vs.search.return_value = [
        SearchResult(
            chunk_id="doc1_page1_chunk1",
            document_id="doc1",
            text="Library is open from 8am to 8pm.",
            source="Library_Guide.pdf",
            page=1,
            score=0.10,  # Below threshold 0.25
        )
    ]
    mock_ollama = MagicMock()

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama, similarity_threshold=0.25)
    response = service.answer_question("What is the attendance policy?")

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.sources == []
    # Ollama should not be called when evidence is insufficient
    mock_ollama.generate.assert_not_called()


def test_rag_service_empty_index_handled():
    mock_vs = MagicMock()
    mock_vs.index.ntotal = 0
    mock_ollama = MagicMock()

    service = RAGService(vector_store=mock_vs, ollama_client=mock_ollama)
    response = service.answer_question("Any question?")

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.sources == []
    mock_ollama.generate.assert_not_called()


# ==============================================================================
# 3. /chat Endpoint API Tests
# ==============================================================================

def test_api_chat_empty_question_rejected():
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


def test_api_chat_valid_question_with_mocked_ollama(monkeypatch):
    rag_service = get_rag_service()

    # Mock the answer_question method
    def mock_answer_question(q):
        return ChatResponse(
            answer="The minimum attendance requirement is 75%.",
            sources=[{"document": "College_Handbook_2026.pdf", "page": 1}],
        )

    monkeypatch.setattr(rag_service, "answer_question", mock_answer_question)

    response = client.post("/chat", json={"question": "What is the minimum attendance requirement?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "The minimum attendance requirement is 75%."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["document"] == "College_Handbook_2026.pdf"
    assert data["sources"][0]["page"] == 1


def test_api_chat_ollama_connection_failure(monkeypatch):
    rag_service = get_rag_service()

    def mock_fail(q):
        raise OllamaConnectionError("Cannot connect to local Ollama server at http://localhost:11434")

    monkeypatch.setattr(rag_service, "answer_question", mock_fail)

    response = client.post("/chat", json={"question": "What is the attendance policy?"})
    assert response.status_code == 503
    assert "cannot connect" in response.json()["detail"].lower()


def test_api_chat_ollama_timeout(monkeypatch):
    rag_service = get_rag_service()

    def mock_timeout(q):
        raise OllamaTimeoutError("Ollama model timed out after 60 seconds.")

    monkeypatch.setattr(rag_service, "answer_question", mock_timeout)

    response = client.post("/chat", json={"question": "What is the attendance policy?"})
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
