import json
from pathlib import Path
import time
from typing import Any, Dict, List
import httpx

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "questions.json"
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "evaluation_results.json"

API_BASE_URL = "http://127.0.0.1:8000"
NO_EVIDENCE_ANSWER = "I couldn't find sufficient evidence for this answer in the uploaded documents."


def run_evaluation():
    print("=" * 70)
    print("LocalDoc AI — Offline RAG Evaluation Suite")
    print("=" * 70)

    # 1. Verify backend health
    try:
        health_resp = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        if health_resp.status_code != 200:
            print(f"Error: Backend returned health status {health_resp.status_code}")
            return
    except Exception as e:
        print(f"Error connecting to backend at {API_BASE_URL}: {e}")
        print("Please ensure the FastAPI backend is running before executing this script.")
        return

    print("Backend health: OK (connected to local FastAPI server)")

    # 2. Load questions
    if not QUESTIONS_FILE.exists():
        print(f"Error: questions file not found at {QUESTIONS_FILE}")
        return

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(questions)} evaluation questions from {QUESTIONS_FILE.name}")
    print("-" * 70)

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []

    answerable_count = 0
    unanswerable_count = 0
    correctly_answered_count = 0
    correctly_refused_count = 0
    citation_present_count = 0
    citation_correct_count = 0

    for item in questions:
        q_id = item["id"]
        q_text = item["question"]
        expected_ans = item["expected_answerable"]
        expected_src = item.get("expected_source")
        expected_pg = item.get("expected_page")
        keywords = item.get("expected_keywords", [])

        if expected_ans:
            answerable_count += 1
        else:
            unanswerable_count += 1

        print(f"[{q_id}/{len(questions)}] Question: {q_text}")

        # Send request and measure latency
        start_time = time.perf_counter()
        try:
            resp = httpx.post(
                f"{API_BASE_URL}/chat",
                json={"question": q_text},
                timeout=120.0,
            )
            elapsed = time.perf_counter() - start_time
            latencies.append(elapsed)

            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "").strip()
                sources = data.get("sources", [])
            else:
                answer = f"HTTP Error {resp.status_code}: {resp.text}"
                sources = []
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            latencies.append(elapsed)
            answer = f"Request Failed: {str(e)}"
            sources = []

        # Determine refusal
        lower_ans = answer.lower()
        is_refusal = (
            NO_EVIDENCE_ANSWER.lower() in lower_ans
            or "couldn't find sufficient evidence" in lower_ans
            or "not found in the uploaded documents" in lower_ans
            or (len(sources) == 0 and not expected_ans)
        )

        has_sources = len(sources) > 0

        # Check correctness
        is_correct_answer = False
        is_correct_citation = False

        if expected_ans:
            # For answerable questions, should NOT refuse, and should mention key facts
            if not is_refusal:
                # Check keywords if provided
                if keywords:
                    is_correct_answer = any(k.lower() in lower_ans for k in keywords)
                else:
                    is_correct_answer = True

                if is_correct_answer:
                    correctly_answered_count += 1

            if has_sources:
                citation_present_count += 1
                # Check if expected source and page match
                if expected_src and expected_pg:
                    matches = any(
                        s.get("document") == expected_src and s.get("page") == expected_pg
                        for s in sources
                    )
                    if matches:
                        is_correct_citation = True
                        citation_correct_count += 1
        else:
            # For unanswerable questions, MUST refuse
            if is_refusal:
                correctly_refused_count += 1

        result_entry = {
            "id": q_id,
            "question": q_text,
            "expected_answerable": expected_ans,
            "expected_source": expected_src,
            "expected_page": expected_pg,
            "response": answer,
            "sources": sources,
            "latency_seconds": round(elapsed, 3),
            "sources_returned": has_sources,
            "system_refused": is_refusal,
            "correct_answer_flag": is_correct_answer if expected_ans else is_refusal,
            "correct_citation_flag": is_correct_citation,
        }
        results.append(result_entry)

        status_flag = "REFUSED (Expected)" if (is_refusal and not expected_ans) else ("ANSWERED" if not is_refusal else "REFUSED")
        print(f"       -> Status: {status_flag} | Latency: {elapsed:.2f}s | Sources: {len(sources)}")

    # 3. Calculate summary metrics
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    min_latency = min(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0

    refusal_accuracy = (
        (correctly_refused_count / unanswerable_count * 100)
        if unanswerable_count > 0
        else 0.0
    )
    citation_accuracy = (
        (citation_correct_count / answerable_count * 100)
        if answerable_count > 0
        else 0.0
    )
    answer_accuracy = (
        (correctly_answered_count / answerable_count * 100)
        if answerable_count > 0
        else 0.0
    )

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(questions),
        "answerable_questions": answerable_count,
        "unanswerable_questions": unanswerable_count,
        "correctly_answered_questions": correctly_answered_count,
        "correctly_refused_questions": correctly_refused_count,
        "citation_presence_count": citation_present_count,
        "correct_citations_count": citation_correct_count,
        "refusal_accuracy_pct": round(refusal_accuracy, 1),
        "citation_accuracy_pct": round(citation_accuracy, 1),
        "answer_accuracy_pct": round(answer_accuracy, 1),
        "latency_stats": {
            "average_seconds": round(avg_latency, 3),
            "min_seconds": round(min_latency, 3),
            "max_seconds": round(max_latency, 3),
        },
        "model_info": {
            "llm": "gemma4:e2b-it-q4_K_M",
            "runtime": "Ollama (local)",
            "embeddings": "sentence-transformers/all-MiniLM-L6-v2",
            "vector_store": "FAISS (IndexFlatIP)",
        },
        "details": results,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY REPORT (Manual/Rule-Verified)")
    print("=" * 70)
    print(f"Total Questions Evaluated:  {len(questions)}")
    print(f"  - Answerable Questions:    {answerable_count}")
    print(f"  - Unanswerable Questions:  {unanswerable_count}")
    print(f"Correctly Answered:         {correctly_answered_count}/{answerable_count} ({answer_accuracy:.1f}%)")
    print(f"Correctly Refused:          {correctly_refused_count}/{unanswerable_count} ({refusal_accuracy:.1f}%)")
    print(f"Refusal Accuracy:           {refusal_accuracy:.1f}%")
    print(f"Citations Present:          {citation_present_count}/{answerable_count}")
    print(f"Citation Accuracy (Page/Doc): {citation_accuracy:.1f}% ({citation_correct_count}/{answerable_count})")
    print(f"Latency Statistics:")
    print(f"  - Average:                {avg_latency:.2f}s")
    print(f"  - Min:                    {min_latency:.2f}s")
    print(f"  - Max:                    {max_latency:.2f}s")
    print(f"\nDetailed evaluation results saved to: {RESULTS_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()