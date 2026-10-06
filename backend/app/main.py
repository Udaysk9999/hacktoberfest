from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.documents import router as documents_router

app = FastAPI(
    title="LocalDoc AI API",
    description="Local-first private document intelligence agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)


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
