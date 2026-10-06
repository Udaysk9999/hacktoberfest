from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.search import router as search_router
from app.services.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload vector store and existing index on startup
    get_vector_store()
    try:
        from app.services.storage import deduplicate_and_migrate_existing_documents
        deduplicate_and_migrate_existing_documents()
    except Exception as e:
        pass
    yield


app = FastAPI(
    title="LocalDoc AI API",
    description="Local-first private document intelligence agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)


@app.get("/")
def read_root():
    return {
        "message": "Welcome to LocalDoc AI API",
        "docs_url": "/docs",
        "health_check": "/health",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": "LocalDoc AI",
        "version": "0.1.0",
    }
