# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** ___________  
**Ngày:** ___________

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

> Điền vào bảng sau. Lấy số liệu từ:
> - Day 08: chạy `python eval.py` từ Day 08 lab
> - Day 09: chạy `python eval_trace.py` từ lab này

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.0 | 0.658 | +0.658 | Day 08 không dùng score |
| Avg latency (ms) | ~2500 | 10291 | +7791 | Multi-agent tốn thêm LLM calls |
| Abstain rate (%) | 20% | 16% | -4% | Multi-agent giảm hallucination |
| Multi-hop accuracy | 40% | 85% | +45% | Nhờ tách worker xử lý domain |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Dễ debug logic |
| Debug time (estimate) | 15 phút | 5 phút | -10 phút | Thời gian tìm ra 1 bug |

> **Lưu ý:** Nếu không có Day 08 kết quả thực tế, ghi "N/A" và giải thích.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | High | High |
| Latency | Low (~2s) | Medium (~7-9s) |
| Observation | Nhanh và hiệu quả. | Chậm hơn do overhead routing. |

**Kết luận:** Multi-agent có cải thiện không? Không rõ rệt về accuracy, nhưng làm chậm hệ thống.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Medium | High |
| Routing visible? | ✗ | ✓ |
| Observation | Dễ sót thông tin chéo. | Supervisor điều hướng lấy đủ evidence. |

**Kết luận:** Multi-agent cải thiện vượt trội ở các task cần kết hợp nhiều nguồn tài liệu hoặc kiểm tra điều kiện phức tạp.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 20% | 16% |
| Hallucination cases | 1-2 cases | 0 cases |
| Observation | Đôi khi cố trả lời khi thiếu info. | HITL giúp chặn câu trả lời sai. |

**Kết luận:** Multi-agent an toàn hơn nhờ cơ chế HITL và Synthesis grounding nghiêm ngặt.

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ___ phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ___ phút
```

**Câu cụ thể nhóm đã debug:** _(Mô tả 1 lần debug thực tế trong lab)_

Sửa lỗi routing cho case "escalation". Ban đầu supervisor chỉ dùng keyword "access", sau đó nhờ xem `route_reason` trong trace, nhóm phát hiện case escalation bị route nhầm sang retrieval worker đơn thuần thay vì policy worker để check quyền admin.

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:** Kiến trúc Multi-agent là lựa chọn tối ưu cho hệ thống cần độ bền vững (robustness) và khả năng mở rộng nhanh (scalability).

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 2 LLM calls |
| Complex query | 1 LLM call | 3-4 LLM calls |
| MCP tool call | N/A | 2 calls |

**Nhận xét về cost-benefit:** Đánh đổi cost (token) lấy độ tin cậy và khả năng kiểm soát quy trình. Rất đáng giá cho các tác vụ quan trọng như Policy/Access.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Khả năng quan sát (Observability)**: Biết rõ tại sao hệ thống đưa ra quyết định qua `route_reason`.
2. **Khả năng kiểm soát (Control)**: Dễ dàng can thiệp bằng HITL hoặc tách logic xử lý cho từng worker.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency**: Tốn nhiều thời gian phản hồi hơn đáng kể do chaining.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi task quá đơn giản, yêu cầu độ trễ thấp (real-time) và không có rủi ro về policy.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm bộ nhớ hội thoại (Conversation Memory) và Dynamic Worker Discovery để Supervisor tự tìm worker mà không cần hard-code keyword.
