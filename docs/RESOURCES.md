# LocalDoc AI - External Resources Tracker

This document maintains a structured record of all external resources, libraries, models, tools, and technical references used during the planning, architecture, and development of LocalDoc AI.

| Resource | Type | Purpose | Official URL | License | Used In |
|---|---|---|---|---|---|
| **Gemma** | Model | Local open-weight LLM for text generation and structured reasoning | https://ai.google.dev/gemma | Gemma Terms of Use | Backend / LLM Service |
| **all-MiniLM-L6-v2** | Model | Generating dense semantic vector embeddings for chunks and queries | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | Backend / Embedding Service |
| **FastAPI** | Framework | High-performance Python web framework for REST API endpoints | https://fastapi.tiangolo.com | MIT | Backend API |
| **Uvicorn** | Library | Lightning-fast ASGI web server implementation for FastAPI | https://www.uvicorn.org | BSD-3-Clause | Backend Server |
| **Pydantic** | Library | Data validation, structured operation schemas, and settings management | https://docs.pydantic.dev | MIT | Backend Models & Schemas |
| **PyMuPDF** | Library | Fast PDF parsing and page-accurate text extraction | https://pymupdf.readthedocs.io | AGPL-3.0 / Commercial | Document Ingestion Service |
| **python-docx** | Library | Reading, parsing, and modifying Microsoft Word (.docx) files | https://python-docx.readthedocs.io | MIT | Document Ingestion & Editing |
| **python-pptx** | Library | Reading, parsing, and modifying PowerPoint (.pptx) presentations | https://python-pptx.readthedocs.io | MIT | Document Ingestion & Editing |
| **FAISS (faiss-cpu)** | Library | Dense vector similarity search and index clustering | https://github.com/facebookresearch/faiss | MIT | Vector Retrieval Service |
| **Sentence-Transformers** | Library | Computing dense sentence and passage embeddings locally | https://sbert.net | Apache-2.0 | Embedding Service |
| **React** | Framework | Component-based frontend user interface library | https://react.dev | MIT | Frontend UI |
| **Tailwind CSS** | Framework | Utility-first CSS framework for modern responsive UI styling | https://tailwindcss.com | MIT | Frontend Styling |
| **Ollama** | Tool | Local runtime and process manager for running open-weight LLMs | https://ollama.com | MIT | Model Inference Runtime |
| **Git** | Tool | Distributed version control system | https://git-scm.com | GPL-2.0 | Source Control |
| **Gemini CLI** | AI Assistant | Scaffolding, architectural design, documentation structuring, and development assistance | https://github.com/google-gemini/gemini-cli | Apache-2.0 | Development & Scaffolding |

*Note: All resource licenses and URLs have been verified against their official project repositories and release documentation.*
