"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os
from dotenv import load_dotenv
from dotenv import dotenv_values

WORKER_NAME = "synthesis_worker"
LAB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(LAB_ROOT, ".env")
load_dotenv(dotenv_path=ENV_PATH)

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""


def _call_llm(messages: list) -> tuple[str, str]:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    openai_last_error = ""

    # Option A: OpenAI (primary)
    try:
        from openai import OpenAI
        openai_key = os.getenv("OPENAI_API_KEY") or dotenv_values(ENV_PATH).get("OPENAI_API_KEY", "")
        openai_key = (openai_key or "").strip().strip('"').strip("'")
        if openai_key:
            model_candidates = [
                os.getenv("OPENAI_MODEL", "").strip(),
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4.1-mini",
            ]
            model_candidates = [m for m in model_candidates if m]
            client = OpenAI(api_key=openai_key)
            for model_name in model_candidates:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=0.1,  # Low temperature để grounded
                        max_tokens=500,
                    )
                    return response.choices[0].message.content, f"openai:{model_name}"
                except Exception as e:
                    openai_last_error = f"{type(e).__name__}: {str(e)[:140]}"
                    continue
    except Exception:
        pass

    # Option B: Gemini
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        combined = "\n".join([m["content"] for m in messages])
        response = model.generate_content(combined)
        return response.text, "gemini:gemini-1.5-flash"
    except Exception:
        pass

    # Fallback: trả về message báo lỗi (không hallucinate)
    if openai_last_error:
        return f"[SYNTHESIS ERROR] OpenAI call failed. {openai_last_error}", "none"
    return "[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra OPENAI_API_KEY trong .env.", "none"


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _ensure_citations(answer: str, sources: list) -> str:
    """
    Đảm bảo answer có citation khi có evidence.
    Nếu model quên cite, thêm block nguồn ở cuối câu trả lời.
    """
    if not sources:
        return answer
    if answer.startswith("[SYNTHESIS ERROR]"):
        return answer
    if "[" in answer and "]" in answer:
        return answer
    citation_tail = " ".join([f"[{s}]" for s in sources])
    return f"{answer}\n\nNguồn: {citation_tail}"


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Số lượng và quality của chunks
    - Có exceptions không
    - Answer có abstain không

    TODO Sprint 2: Có thể dùng LLM-as-Judge để tính confidence chính xác hơn.
    """
    if not chunks:
        return 0.1  # Không có evidence → low confidence

    if answer.startswith("[SYNTHESIS ERROR]"):
        return 0.15

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3  # Abstain → moderate-low

    avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    chunk_coverage = min(len(chunks), 4) / 4  # 0..1
    unique_sources = len({c.get("source") for c in chunks if c.get("source")})
    source_diversity = min(unique_sources, 3) / 3  # 0..1

    # Base score thiên về evidence quality + coverage
    base = 0.25 + (0.45 * avg_score) + (0.2 * chunk_coverage) + (0.1 * source_diversity)

    # Penalize nếu có exception nhưng câu trả lời không phản ánh rõ
    exceptions = policy_result.get("exceptions_found", [])
    if exceptions:
        answer_lower = answer.lower()
        mentions_exception = any(
            kw in answer_lower for kw in ["ngoại lệ", "exception", "không được", "không thể", "không hoàn tiền"]
        )
        base -= 0.03 if mentions_exception else 0.1

    return round(max(0.1, min(0.95, base)), 2)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    # Contract guard: không có evidence thì phải abstain, không gọi LLM để tránh hallucination
    if not chunks:
        abstain = "Không đủ thông tin trong tài liệu nội bộ để trả lời chính xác câu hỏi này."
        return {
            "answer": abstain,
            "sources": [],
            "confidence": 0.1,
            "llm_provider": "none",
        }

    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên."""
        }
    ]

    answer, llm_provider = _call_llm(messages)
    sources = list({
        c.get("source")
        for c in chunks
        if c.get("source") and c.get("source") != "unknown"
    })
    answer = _ensure_citations(answer, sources)
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "llm_provider": llm_provider,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]
        state["llm_provider"] = result.get("llm_provider", "unknown")
        state["hitl_triggered"] = result["confidence"] < 0.4

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
            "llm_provider": state["llm_provider"],
            "hitl_triggered": state["hitl_triggered"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"llm={state['llm_provider']}, sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["hitl_triggered"] = True
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
