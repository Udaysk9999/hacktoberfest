# LocalDoc AI

> **A local-first, privacy-preserving AI document agent and knowledge assistant running entirely on your machine.**

---

## 1. Project Overview

**LocalDoc AI** is an offline-capable, local-first document question-answering assistant developed for a hackathon. It allows users to ingest local documents (**PDF** format), extract their text with page attribution, generate dense semantic embeddings on device, store them in a local vector index, and query them using a local open-weight language model (**Google Gemma 4** via Ollama).

Crucially, LocalDoc AI is designed with an **evidence-first grounding paradigm**: answers are synthesized strictly from retrieved context with explicit document and page citations, and the system explicitly refuses to answer when sufficient supporting evidence is absent from the indexed documents.

---

## 2. Problem Statement

Modern cloud-based AI services require users to transmit private, proprietary, or sensitive files over the public internet to third-party servers. In many environments—including legal analysis, proprietary engineering, financial auditing, healthcare documentation, and confidential coursework—cloud transmission violates privacy guidelines, organizational policies, or regulatory compliance.

Furthermore:
- **General-purpose LLMs lack access to private local context:** They cannot reliably reason over local, non-public documents without ingestion.
- **Cloud dependency creates vulnerability:** Network latency, outages, API rate limits, and subscription costs impede seamless productivity.
- **Unconstrained generation causes hallucinations:** Typical chat applications guess or invent plausible-sounding answers when private documents do not contain the answer.

There is a critical need for an AI assistant that runs 100% locally, guarantees complete document confidentiality, enforces strict citation grounding, and operates seamlessly even when offline.

---

## 3. Solution

LocalDoc AI addresses these challenges through a modular, local-first architecture:
- **Zero Cloud Leakage:** Ingestion, parsing, embedding generation, vector similarity indexing, and LLM inference execute entirely on `localhost`.
- **Structured PDF Text Extraction:** PyMuPDF extracts text while preserving structural boundaries and exact page numbers.
- **Dense Local Retrieval:** Semantic chunks are indexed in a local FAISS index, ensuring fast vector search without external vector databases.
- **Strict Grounding & Hallucination Mitigation:** The prompt boundary instructs the local Gemma model to only generate statements backed by retrieved chunks and to refuse unsupported queries.
- **Deterministic Citations:** Answers include exact source filenames and page numbers referencing the retrieved chunks.

---

## 4. Key Features

- **Local PDF Processing:** Ingests and parses `.pdf` files locally via PyMuPDF (`pymupdf`).
- **Page-Aware Chunking:** Deterministic text chunking that retains document source metadata and page numbers.
- **Local Dense Embeddings:** Generates 384-dimensional dense vectors locally via Sentence-Transformers (`all-MiniLM-L6-v2`) without cloud API calls.
- **Local Vector Search:** Fast cosine similarity search powered by FAISS (`IndexFlatIP`).
- **Local Open-Weight LLM:** Runs open-weight models (**Google Gemma 4**) locally using the Ollama runtime.
- **Evidence-Grounded Answers:** Responses cite exact document names and page numbers.
- **Explicit "Insufficient Evidence" Refusal:** Directly admits when documents do not contain the facts requested rather than hallucinating.
- **Modern Responsive Web UI:** React + Vite single-page application styled with Vanilla CSS design tokens.
- **Offline-First Design:** Engineered to function completely without an internet connection once models and dependencies are downloaded.

---

## 5. Why This Is Different

LocalDoc AI is **not** simply another generic cloud-based document chat wrapper:

| Differentiator | Generic Cloud Wrappers | LocalDoc AI |
|---|---|---|
| **Data Privacy** | Sends files and questions to external cloud APIs | 100% of data and embeddings remain on the local machine |
| **Offline Operation** | Requires continuous internet access | Fully functional offline after initial setup |
| **Model Transparency** | Closed-source, remote proprietary APIs | Open-weight model (Gemma 4) running via local Ollama runtime |
| **Grounding Discipline** | Prone to ungrounded speculation when facts are missing | Explicit refusal policy if similarity thresholds are not met |
| **Citation Granularity** | Often vague or absent | Direct attribution to specific document names and page numbers |

*Note: LocalDoc AI does not claim superiority over frontier cloud models in broad general knowledge reasoning; rather, it offers a specialized, privacy-preserving, and verifiable architecture tailored specifically for private local documents.*

---

## 6. Architecture

```mermaid
flowchart TD
    User([User]) <--> Frontend[React + Vite Frontend (Vanilla CSS)]
    Frontend <--> Backend[FastAPI Backend Server]
    
    subgraph Document Ingestion Pipeline
        Upload[PDF Document Upload]
        Parser[PDF Parser: PyMuPDF]
        Cleaner[Text Normalizer & Cleaner]
        Chunker[Page-Aware Semantic Chunking]
        EmbedModel[Local Embeddings: all-MiniLM-L6-v2]
        VectorStore[(Local FAISS Vector Index)]
        
        Upload --> Parser
        Parser --> Cleaner
        Cleaner --> Chunker
        Chunker --> EmbedModel
        EmbedModel --> VectorStore
    end

    subgraph Retrieval & Inference Pipeline
        Query[User Question]
        QEmbed[Question Embedding]
        Search[Cosine Similarity Search: FAISS]
        Dedup[Candidate Deduplication & Threshold Filter]
        Context[Top-K Grounded Context Chunks]
        Prompt[Prompt Assembly with Grounding Boundary]
        Ollama[Ollama Runtime / Local Gemma 4 Model]
        Decision{Sufficient Evidence?}
        Answer[Grounded Answer + Page Citations]
        Refusal[Explicit Refusal: Insufficient Evidence]

        Query --> QEmbed
        QEmbed --> Search
        Search --> Dedup
        Dedup --> Context
        Context --> Prompt
        Prompt --> Ollama
        Ollama --> Decision
        Decision -- Yes --> Answer
        Decision -- No --> Refusal
    end

    Backend --> Upload
    Backend --> Query
    Answer --> Backend
    Refusal --> Backend
```

### Pipeline Flow
```
React / Vite
    ↓
FastAPI
    ↓
PyMuPDF
    ↓
MiniLM Embeddings
    ↓
FAISS
    ↓
Retrieved Evidence (Threshold >= 0.25)
    ↓
Ollama (Local)
    ↓
Google Gemma 4 (gemma4:e2b-it-q4_K_M)
    ↓
Grounded Answer + Deterministic Citations / Refusal
```

---

## 7. How It Works

The complete lifecycle operates through eight transparent steps:

1. **Upload:** User provides a `.pdf` file via the React UI or the `POST /documents/upload` REST endpoint.
2. **Text Extraction:** PyMuPDF (`pymupdf`) extracts raw text page-by-page while preserving exact page numbers.
3. **Cleaning & Chunking:** Text is cleaned and partitioned into deterministic, overlapping chunks (default 600 characters, 100 character overlap) tagged with document ID and page number.
4. **Embedding Generation:** Each chunk is converted into a normalized 384-dimensional dense vector using `sentence-transformers/all-MiniLM-L6-v2`.
5. **Vector Storage:** Embeddings are added to a FAISS `IndexFlatIP` index, and metadata is persisted in `data/metadata/chunks_metadata.json`.
6. **Question Embedding & Retrieval:** When a user asks a question, the query is embedded and searched against the FAISS index. Candidates are deduplicated and filtered against the similarity threshold (`SIMILARITY_THRESHOLD = 0.25`).
7. **Local LLM Inference:** The retrieved context and question are assembled into a strictly grounded prompt passed to Gemma 4 via Ollama with low temperature (`0.1`).
8. **Evidence Display:** The frontend renders the response with corresponding document name and page number citations. If evidence is insufficient, an explicit refusal is returned without hallucinating.

---

## 8. Offline Architecture & Verification Status

LocalDoc AI is designed with an explicit offline-first boundary:

### Local Components (Offline)
- **Document Processing:** PyMuPDF runs directly on host CPU.
- **Embedding Generation:** Sentence-Transformers runs on host CPU with locally cached weights.
- **Vector Search:** FAISS index operates entirely in host memory and local disk.
- **LLM Inference:** Ollama server communicates over localhost socket (`127.0.0.1:11434`).
- **Web Interface:** Local development/production server serving assets to local browser.

### When Internet Access is Required
- Initial installation of Python packages (`pip`) and Node dependencies (`npm`).
- Initial download of the Ollama executable and pulling of target model weights (`ollama pull gemma4:e2b-it-q4_K_M`).

> **Offline Verification Status:** *The core architecture is fully designed for local execution without cloud APIs. Final physical Wi-Fi-off verification is documented in [docs/offline-test.md](docs/offline-test.md) as a manual test procedure to be performed by toggling network adapters.*

---

## 9. Technology Stack

| Technology | Purpose | Why It Is Used | Official Resource |
|---|---|---|---|
| **React 18** | Frontend UI Framework | Component-driven, responsive UI for document management and chat | [https://react.dev](https://react.dev) |
| **Vite** | Frontend Build Tool | High-speed local dev server and optimized production bundler | [https://vitejs.dev](https://vitejs.dev) |
| **Vanilla CSS** | Frontend Styling | High-performance, tailored glassmorphic design tokens without framework bloat | Standard Web CSS |
| **FastAPI** | Backend API Framework | High performance, native async support, automatic OpenAPI docs | [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| **Uvicorn** | ASGI Web Server | Production-grade ASGI server to run FastAPI locally | [https://www.uvicorn.org](https://www.uvicorn.org) |
| **PyMuPDF (`pymupdf`)** | PDF Text Extraction | Exceptionally fast, low-overhead PDF parsing with page-level tracking | [https://pymupdf.readthedocs.io](https://pymupdf.readthedocs.io) |
| **FAISS (`faiss-cpu`)** | Vector Index & Retrieval | Highly optimized dense vector search engine developed by Meta Research | [https://github.com/facebookresearch/faiss](https://github.com/facebookresearch/faiss) |
| **Sentence-Transformers** | Local Dense Embeddings | Efficient local embedding generation (`all-MiniLM-L6-v2`) | [https://sbert.net](https://sbert.net) |
| **Ollama** | Local LLM Runtime | Lightweight local runner for quantized open-weight language models | [https://ollama.com](https://ollama.com) |
| **Pydantic v2** | Schema Validation | Type-safe request/response models and schema enforcement | [https://docs.pydantic.dev](https://docs.pydantic.dev) |

---

## 10. AI Models

| Attribute | Verified Specification |
|---|---|
| **Target Model Family** | Google Gemma |
| **Target Runtime** | Ollama (`http://localhost:11434`) |
| **Model Candidate** | `gemma4:e2b-it-q4_K_M` |
| **Quantization** | 4-bit / Q4_K_M |
| **Model Source** | Official Google Gemma distribution via Ollama |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) |
| **Temperature** | `0.1` (strict factual grounding) |

---

## 11. Installation

### Prerequisites
1. **Python 3.10+**
2. **Node.js 18+** and **npm**
3. **Ollama** installed and running on your system ([Download Ollama](https://ollama.com))

### Setup Steps
```bash
# 1. Clone the repository
git clone https://github.com/Udaysk9999/hacktoberfest.git
cd hacktoberfest

# 2. Set up Backend Python Virtual Environment
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Pull target Ollama Model
ollama pull gemma4:e2b-it-q4_K_M

# 4. Set up Frontend
cd ../frontend
npm install
```

---

## 12. Running Locally

### Step 1: Start Ollama Runtime
Ensure the Ollama background daemon is running:
```bash
ollama serve
```

### Step 2: Start Backend Server
From the `backend` directory with the virtual environment activated:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
FastAPI interactive documentation: `http://127.0.0.1:8000/docs`

### Step 3: Start Frontend Development Server
From the `frontend` directory:
```bash
npm run dev
```
The application interface will be accessible at: `http://localhost:5173`

---

## 13. Environment Variables

Configuration parameters can be set in a `.env` file or passed as environment variables. Below are the actual settings supported by `backend/app/config.py`:

```bash
# Storage & Directory Paths
UPLOAD_DIR=uploads
PROCESSED_DATA_DIR=data/processed
FAISS_DIR=data/faiss
METADATA_DIR=data/metadata

# Upload Constraints
MAX_FILE_SIZE_MB=25

# Chunking Configuration
CHUNK_SIZE=600
CHUNK_OVERLAP=100

# Embedding & Vector Store
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
DEFAULT_TOP_K=5

# Ollama & Local RAG Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e2b-it-q4_K_M
OLLAMA_TIMEOUT=120.0
SIMILARITY_THRESHOLD=0.25
RAG_TOP_K=4
```

Frontend environment variables (in `frontend/.env`):
```bash
VITE_API_BASE=http://127.0.0.1:8000
```

---

## 14. Project Status

- [x] Project initialized & Git configured
- [x] Architecture design & documentation completed
- [x] `.gitignore` and security rules established
- [x] Backend API skeleton (FastAPI)
- [x] Document upload & validation (`.pdf`)
- [x] PDF text extraction (PyMuPDF)
- [x] Semantic chunking engine with page tracking
- [x] Local dense embeddings (`all-MiniLM-L6-v2`)
- [x] Local vector search (FAISS IndexFlatIP)
- [x] Ollama local Gemma 4 integration (`gemma4:e2b-it-q4_K_M`)
- [x] Evidence citation & strict refusal handling
- [x] Frontend user interface (React + Vite + Vanilla CSS)
- [x] Performance benchmarking & evaluation suite
- [ ] DOCX extraction (`python-docx`) *(Future Work)*
- [ ] PPTX extraction (`python-pptx`) *(Future Work)*
- [ ] Controlled document modification engine *(Future Work)*
- [ ] Physical offline Wi-Fi-off verification *(Manual procedure documented in docs/offline-test.md)*

---

## 15. Benchmark & Evaluation Results

The pipeline was benchmarked using an automated offline test suite (`evaluation/run_evaluation.py`) over 21 structured test questions evaluated against a multi-page college handbook:

| Metric | Result | Description |
|---|---|---|
| **Total Evaluation Questions** | **21** | Comprehensive test suite |
| **Answerable Questions** | **11** | Questions with factual backing in document |
| **Unanswerable Questions** | **10** | Out-of-scope questions (not in document) |
| **Correctly Answered** | **11 / 11 (100.0%)** | Answerable questions answering with correct facts |
| **Correctly Refused** | **10 / 10 (100.0%)** | Unanswerable questions successfully refused |
| **Refusal Accuracy** | **100.0%** | Zero hallucinations on unsupported queries |
| **Citation Accuracy** | **11 / 11 (100.0%)** | Correct document filename and exact page attribution |
| **Warm Inference Latency** | **~7.8s – 13.3s** | Typical response time per query |
| **Cold-Start Max Latency** | **~41.2s** | First-load model weight ingestion into GPU/VRAM |
| **Automated Test Suite** | **39 / 39 passed** | Unit and integration test coverage across all services |

*These metrics reflect the empirical benchmark recorded in `evaluation/results/evaluation_results.json`.*

---

## 16. Security & Privacy

- **Strict Local Data Boundary:** No uploaded documents, extracted paragraphs, vector coordinates, or queries are ever sent outside `localhost`.
- **Exclusion of Secrets & User Documents:** Rigorous `.gitignore` rules prevent accidentally committing `.env`, user uploads, cache files, vector indexes, or model weights.
- **Path Sanitization:** File uploads are assigned randomized identifiers and confined to a dedicated data directory to prevent path traversal attacks.

---

## 17. Limitations & Future Work

### Current Limitations
- **PDF-Only Scope:** Current implementation supports digital `.pdf` documents; image-only scanned PDFs require an OCR engine.
- **Single-Turn Context:** Chat operates statelessly on a per-question basis without conversational multi-turn memory.

### Future Work
- Ingestion support for DOCX (`python-docx`) and PPTX (`python-pptx`) files.
- Local OCR integration (Tesseract / EasyOCR) for scanned PDFs.
- Controlled natural-language document modification engine.
- Token streaming via Server-Sent Events (SSE).
- Multi-turn conversation history.

---

## 18. AI Assistance Disclosure

In alignment with transparent hackathon standards:
- **Development Tools:** AI coding assistants were utilized during the project lifecycle for scaffolding, planning, test creation, and debugging.
- **Human Oversight:** All architectural decisions, data validation boundaries, refusal logic, and integration checkpoints were directed, tested, and verified directly.

---

## 19. Hackathon Information

- **Event:** Hacktoberfest 2026 Hackathon
- **Type:** Solo Project
- **Focus:** Open-Source AI, Local-First Architecture & Privacy
- **GitHub Repository:** [https://github.com/Udaysk9999/hacktoberfest](https://github.com/Udaysk9999/hacktoberfest)
