from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.search import router as search_router

__all__ = ["documents_router", "search_router", "chat_router"]
