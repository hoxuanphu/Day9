# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| ___ | Supervisor Owner | ___ |
| Đào Danh Đăng Phụng | Worker Owner | phung352100@gmail.com |
| ___ | MCP Owner | ___ |
| ___ | Trace & Docs Owner | ___ |

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

Nhóm xây dựng pipeline multi-agent theo pattern Supervisor -> Worker -> Synthesis, gồm 3 worker chính: `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`. Supervisor chịu trách nhiệm route theo keyword/risk signal, worker xử lý domain, và synthesis tạo câu trả lời cuối có citation. Trong quá trình hoàn thiện, nhóm đã chuyển graph từ placeholder sang gọi worker thật và lưu trace theo từng lần chạy để debug.

Về dữ liệu, retrieval dùng ChromaDB collection `day09_docs`; policy worker xử lý exception theo rule và gọi MCP khi cần; synthesis dùng LLM (OpenAI) để tổng hợp grounded answer. Kết quả chạy gần nhất cho thấy hệ thống hoạt động ổn định với đầy đủ route retrieval/policy và có HITL cho case lỗi không rõ.

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

Nhóm dùng routing rule-based theo keyword:
- refund/access/emergency -> `policy_tool_worker`
- ticket/P1/escalation -> `retrieval_worker`
- mã lỗi không rõ (ERR-...) -> `human_review`
- default -> `retrieval_worker`

Ngoài route, supervisor set thêm `risk_high`, `needs_tool`, và `retrieval_top_k` động (3 hoặc 4) để cải thiện evidence quality cho câu hỏi khó.

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: ___________________
- `get_ticket_info`: Dùng cho case liên quan ticket/P1 trong `policy_tool_worker` để bổ sung thông tin ticket mock.
- `check_access_permission`: Dùng cho case access/admin/emergency để trả `can_grant`, `required_approvers`, `emergency_override`.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Chuẩn hóa điểm retrieval + thêm light rerank/filter trước synthesis.

**Bối cảnh vấn đề:**

Vấn đề ban đầu là retrieval có score âm với công thức cũ (`1 - distance`) và một số chunk nhiễu vẫn lọt vào synthesis, làm confidence dao động thấp hoặc không ổn định. Điều này ảnh hưởng trực tiếp đến chất lượng answer và khả năng giải thích trace.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Giữ nguyên `score = 1 - distance` | Đơn giản, dễ tính | Có thể âm, vi phạm contract [0,1] |
| Clamp trực tiếp `1 - distance` | Đúng miền [0,1] | Dễ dồn nhiều kết quả về 0 |
| `score = clamp(1 - distance/2, 0, 1)` + rerank overlap nhẹ | Đúng contract, giữ phân tách tốt hơn, chunk vào synthesis liên quan hơn | Cần thêm bước xử lý và metadata trace |

**Phương án đã chọn và lý do:**

Nhóm chọn phương án thứ ba vì cân bằng giữa tính đúng contract và chất lượng retrieval thực tế. Ngoài score mapping, retrieval query lấy `candidate_k` lớn hơn rồi rerank theo overlap query-chunk và lọc chunk nhiễu trước khi trả về `top_k`. Cách làm này giúp synthesis nhận evidence sạch hơn nên confidence ổn định hơn.

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

```
# workers/retrieval.py
raw_score = 1.0 - (raw_distance / 2.0)
score = max(0.0, min(1.0, raw_score))
rerank_score = (0.8 * base_score) + (0.2 * overlap_ratio)

# Trace Analysis (run gần nhất)
avg_confidence: 0.623
avg_latency_ms: 10062
mcp_usage_rate: 21/79 (26%)
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** ___ / 96 (chờ nhóm đối chiếu rubric chấm tay)

**Câu pipeline xử lý tốt nhất:**
- ID: ___ — Lý do tốt: ___________________

**Câu pipeline fail hoặc partial:**
- ID: ___ — Fail ở đâu: ___________________  
  Root cause: ___________________

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

Synthesis có guard abstain khi `retrieved_chunks=[]`, trả câu "Không đủ thông tin..." và hạ confidence thấp; đồng thời set `hitl_triggered=True` khi confidence dưới ngưỡng.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

Có. Với case multi-hop, trace thể hiện ít nhất retrieval + policy/synthesis và có log worker_io rõ. Riêng case lỗi không rõ (ERR-...) có trigger HITL trước khi quay về retrieval.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

Sau khi tinh chỉnh worker và bật OpenAI ổn định, `avg_confidence` tăng lên mức ~0.623 ở tập trace hiện tại, `avg_latency_ms` khoảng 10062ms. Điều này phản ánh pipeline đã có grounding tốt hơn dù vẫn còn dư địa tối ưu MCP usage.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Khả năng debug tốt hơn rõ rệt nhờ tách worker và có `worker_io_logs`: nhóm xác định nhanh lỗi nằm ở retrieval score mapping, policy exception hay synthesis fallback.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với câu hỏi đơn giản chỉ cần một fact, multi-agent có overhead route + worker chaining nên latency cao hơn cách single-pass. Ngoài ra nếu retrieval trả chunk nhiễu, nhiều node hơn không tự động cải thiện answer nếu không có rerank/filter.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| ___ | ___________________ | ___ |
| Đào Danh Đăng Phụng | Worker Owner: chỉnh `retrieval.py`, `policy_tool.py`, `synthesis.py`; chuẩn hóa score, thêm rerank/filter, MCP call logic, abstain/citation/HITL | 2, 3 |
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |

**Điều nhóm làm tốt:**

_________________

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

_________________

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

_________________

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

_________________

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
