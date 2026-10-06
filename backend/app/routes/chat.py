from fastapi import APIRouter, HTTPException, status

from app.models.chat import ChatRequest, ChatResponse
from app.services.ollama_client import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from app.services.rag_service import get_rag_service

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question grounded in uploaded documents",
)
def chat_with_documents(request: ChatRequest):
    """
    RAG Chat endpoint:
    1. Embeds user question.
    2. Searches local FAISS index for relevant chunks.
    3. If evidence is insufficient, returns grounded refusal without hallucinations.
    4. Otherwise, generates grounded answer via local Gemma 4 through Ollama.
    5. Returns answer along with deterministic source citations.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    rag_service = get_rag_service()

    try:
        response = rag_service.answer_question(question)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except OllamaConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except OllamaTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except OllamaModelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating answer: {str(e)}",
        )
