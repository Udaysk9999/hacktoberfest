# LocalDoc AI — Offline Verification Guide & Test Procedure

> **Notice:** Core document processing, retrieval, and inference are designed to run locally. Offline verification requires manual Wi-Fi disable testing.

---

## 1. Architecture Overview

LocalDoc AI operates entirely on local hardware without sending documents or queries to external cloud APIs:

| Component | Local Technology | Execution Target | Network Access Required? |
|---|---|---|---|
| **Text Extraction** | PyMuPDF (`pymupdf`) | Local CPU | **None** |
| **Cleaning & Chunking** | Deterministic Python services | Local CPU | **None** |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Local CPU / PyTorch | **None** (after initial model download) |
| **Vector Search** | FAISS (`faiss-cpu`) | Local RAM & disk | **None** |
| **Language Model (LLM)** | Gemma 4 (`gemma4:e2b-it-q4_K_M`) | Local Ollama daemon | **None** |
| **Frontend UI** | React 18 + Vite | `localhost:5173` | **None** |

---

## 2. Step-by-Step Manual Offline Verification Procedure

To physically verify that the system operates without internet connectivity, follow these steps:

### Step 1: Pre-requisite Checks
1. Ensure Ollama is running locally:
   ```bash
   ollama list
   # Verify gemma4:e2b-it-q4_K_M is present
   ```
2. Start the FastAPI backend:
   ```bash
   cd backend
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
3. Start the React frontend:
   ```bash
   cd frontend
   npm run dev
   ```

### Step 2: Confirm Online Baseline
1. Open `http://localhost:5173` in a web browser.
2. Confirm the header displays `● Local AI` (green indicator).
3. Upload `College_Handbook_2026.pdf` and verify all 3 badges appear:
   - `✓ Uploaded`
   - `✓ Processed`
   - `✓ Indexed`

### Step 3: Disable All Network Connections
1. **Manually disconnect or disable your network adapter:**
   - On Windows: Open Network Connections or Quick Settings and toggle **Airplane Mode ON** or turn **Wi-Fi OFF** and disconnect ethernet cables.
2. Verify in your terminal that external internet is completely blocked:
   ```powershell
   ping 8.8.8.8
   # Expected: General failure / Request timed out
   ```

### Step 4: Perform Grounded Question Answering (Offline)
1. In the already running LocalDoc AI browser window (`http://localhost:5173`):
2. In the chat input, ask:
   ```
   What is the minimum attendance requirement for students?
   ```
3. Click **Ask**.
4. **Expected Offline Result**:
   - The status indicator remains operational.
   - Gemma 4 generates the local answer:
     > *"All registered undergraduate and graduate students must maintain a minimum attendance of 75% across all scheduled lectures, tutorials, and laboratory sessions for each registered course."*
   - Citations appear cleanly: `📄 College_Handbook_2026.pdf`, `Page 1`.

### Step 5: Perform Refusal Verification (Offline)
1. Ask an unanswerable question whose facts are absent from the document:
   ```
   What is the policy for flying commercial drones in the campus football stadium?
   ```
2. Click **Ask**.
3. **Expected Offline Result**:
   - The system immediately returns the grounded refusal without hallucinating:
     > *"I couldn't find sufficient evidence for this answer in the uploaded documents."*
   - Sources list is empty (`[]`).

### Step 6: Restore Network
1. Turn **Wi-Fi ON** / turn **Airplane Mode OFF**.
2. Verification complete.

---

## 3. Offline Verification Status

> **Important:** Offline verification requires manual Wi-Fi disable testing as automated manipulation of the host network adapter is intentionally disallowed for system safety.
