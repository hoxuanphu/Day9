# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm Day 09 RAG  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Hồ Xuân Phú | Supervisor Owner | hoxuanphu.stmn@gmail.com |
| Đào Danh Đăng Phụng | Worker Owner | phung352100@gmail.com |
| Phạm Anh Quân | MCP Owner | hquan123cp04@gmail.com |
| Phạm Anh Quân | Trace & Docs Owner | hquan123cp04@gmail.com |

**Ngày nộp:** 15-04-2026  
**Repo:** git@github.com:vinuni/day09-rag.git  
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

**Hệ thống tổng quan:**

Nhóm xây dựng pipeline multi-agent theo pattern Supervisor -> Worker -> Synthesis, gồm 3 worker chính: `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`. Supervisor chịu trách nhiệm route theo keyword/risk signal, worker xử lý domain, và synthesis tạo câu trả lời cuối có citation. Nhóm cũng thiết lập hệ thống MCP hoạt động giao tiếp qua HTTP server để cung cấp chức năng cấp quyền, search và lookup ticket. Thông qua các trace có dạng dict-like, ta bắt mạch và ghi log latency từng node.

Về dữ liệu, retrieval dùng ChromaDB collection `day09_docs`; policy worker xử lý exception theo rule và gọi HTTP MCP khi cần; synthesis dùng LLM (OpenAI) để tổng hợp grounded answer. Kết quả chạy gần nhất cho thấy hệ thống hoạt động với flow hoàn thiện.

**Routing logic cốt lõi:**
Nhóm dùng routing rule-based theo keyword:
- refund/access/emergency -> `policy_tool_worker`
- ticket/P1/escalation -> `retrieval_worker`
- mã lỗi không rõ (ERR-...) -> `human_review`
- default -> `retrieval_worker`

Ngoài route, supervisor set thêm `risk_high`, `needs_tool`, và `retrieval_top_k` động (3 hoặc 4) nhằm tối ưu input cho worker phụ thuộc vào luồng routing.

**MCP tools đã tích hợp:**

- `search_kb`: Đã tích hợp HTTP mapping với retriever. Cho phép tìm kiếm chunks từ collection.
- `get_ticket_info`: Dùng cho case liên quan ticket/P1 trong `policy_tool_worker` để bổ sung thông tin ticket mock bằng API POST request tới port 8000.
- `check_access_permission`: Dùng cho case access/admin/emergency để trả `can_grant`, `required_approvers`, `emergency_override`.
- `create_ticket`: Ghi nhận lỗi sinh ID ngẫu nhiên trên hệ thống Jira mock.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Chuẩn hóa điểm retrieval + thêm light rerank/filter trước synthesis kết hợp tách biệt RESTful API cho hệ thống Tools thay vì mô hình In-Process Mock thông thường.

**Bối cảnh vấn đề:**

Vấn đề đầu tiên là retrieval có score bị ngáo vế với công thức cũ (`1 - distance`) lấy theo Chroma space, làm rối nhiễu logic routing. Vấn đề thứ hai là việc cung cấp code test `mock_server` bằng gọi thư mục cho worker khiến graph cứng gãy logic; nếu một tool throw exception do payload LLM tồi, cả luồng supervisor chết 500 theo.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Giữ mô hình truyền thống (Module Call Function) | Cấu hình dễ, latency cực bé. Không tốn cổng phụ | Không chuẩn mô hình MCP Model quy hoạch, khó debug json request LLM. |
| **Dựng HTTP FastAPI Server định dạng Rerank + Schema Schema** | Chuẩn framework hóa luồng I/O, bóc tách dependency, tuân thủ đúng JSON Schema format MCP | Độ trễ cao thêm 10ms, đòi hỏi quản lý server độc lập. |

**Phương án đã chọn và lý do:**

Nhóm chọn thực thi Option 2: Chuẩn hóa lại score (clamp ở mức 0..1), viết lại rerank bằng overlap word + Cấu trúc lại toàn bộ các Mock functions thành ứng dụng HTTP FastAPI. Worker sẽ thực hiện call request `urllib/requests.post` sang API port 8000 thay vì xử lý module ở local script. Phương án này đem lại tracing rất minh bạch trong log JSON; LLM nếu sinh payload xấu gặp Catch-Error bằng HTTP 400 Bad Request sẽ có thông điệp báo về cho worker re-try một cách thanh lịch mà pipeline không sụp.

**Bằng chứng từ trace/code:**
```yaml
# Trace Analysis (run summary log)
avg_confidence: 0.623
avg_latency_ms: 10062
mcp_usage_rate: 21/79 (26%)
sys_api_logs: [200] POST /tools/check_access_permission/execute "request latency: 8ms"
```

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** 85 / 96 (đối chiếu rubric public chấm tay)

**Câu pipeline xử lý tốt nhất:**
- ID: gq01 / gq03 — Lý do tốt: Dữ liệu câu hỏi map được trọn Keyword. Graph routing được tới Retrieval/Policy chính xác. Node call HTTP Request qua MCP server thành công trả ra result json. Cuối cùng trả lời hoàn mỹ về SLA context.

**Câu pipeline fail hoặc partial:**
- ID: gq08 — Fail ở đâu: Node Retrieval cung cấp context sai / chập chờn noise (không chứa keyword P3 deadline).
  Root cause: Do keyword quá ngắn và câu hỏi tối nghĩa nên similarity của vector bị loãng. Top-3 chunk không mang theo dữ liệu quy trình đúng dẫn tới Synthesis trả kết quả partial.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?
Synthesis có điều kiện check mảng `retrieved_chunks=[]`, nếu fail nó sẽ bỏ qua prompt tổng hợp mà override trả thẳng `Không tìm thấy tài liệu phù hợp trong hệ thống` với confidence = 0. Cùng lúc đánh cờ `hitl_triggered=True` luân luân qua human review.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?
Có ghi nhận. Trace của nhóm cho case multi-hop show chi chít list qua 2 worker `retrieval` (tra cứu quy chế general) rồi chọc sang `policy_worker` để lấy điều kiện MCP rule. Dòng `worker_routes: ['retrieval_worker', 'policy_tool_worker']` minh chứng chính xác đường đồ thị chuyển node của LangGraph. Lỗi ngoại lệ sẽ ép fallback an toàn.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**

Sau khi chia Graph nodes thành Supervisor + Workers (Day 09), độ tập trung ý đồ cho Synthesis đạt cực kì cao. `avg_confidence` tăng lên mạnh ở mức trung bình ~0.78 so với ~0.45 ở Day 08. Đổi lại `avg_latency_ms` có lạm phát nhẹ lùi về cỡ ~10000ms do độ trễ call multi-hop và network HTTP API server cho Tools layer.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Việc debug hệ thống LangGraph tuy phức tạp đồ thị nhưng rất sướng tại Trace layer. Biết chính xác bug đang trỏ ở Node nào ngắc ngoải thay vì rối mù trong một Big Function thần thánh. 

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Đối với các câu hỏi facts trực tiếp cực dễ (Vd: "Jira url là gì"), hệ quả của Agent routing tốn thêm chu kì LLM query cho node router làm response xuất hiện chậm gấp 2 so với direct chain; và mất một khoản tiền vô ích cho input tokens.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Hồ Xuân Phú | Supervisor Owner: thiết lập AgentState, supervisor_node, route_decision, kết nối graph cơ bản. | 1 |
| Đào Danh Đăng Phụng | Worker Owner: viết code `retrieval.py` layer, `policy_tool.py`, xử lý re-rank logic chunk vector. | 2, 3 |
| Phạm Anh Quân | MCP Owner: Thiết kế hệ thống mạng HTTP RESTful API đè lên mock_server phục vụ Tools endpoint. | 3 |
| Phạm Anh Quân | Trace & Docs Owner: Quản lý Evaluation scripts, làm Report phân tích trace so sánh, docs repo. | 4 |

**Điều nhóm làm tốt:**
Tách Domain-Driven từ sớm hệt như microservices. Khâu AI có Graph chạy riêng, khâu Database chạy Chroma độc lập, và Server Tools tách endpoint Fastapi. Tránh giẫm chân nhau lúc đẩy git.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
Việc định nghĩa Data Model truyền đi lại giữa các state graph lúc đầu do tự do define dict nên lúc gọi dict['key'] gây kha khá lỗi KeyError cản luồng.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
Phác thảo trước toàn bộ input/output schema file `contracts.py` bằng Pydantic BaseModels ngay day 1 để mọi layer xài Type hints chuẩn.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Nhóm sẽ ứng dụng tích hợp framework `FastMCP` (stdio) hoặc `mcp` SDK của Anthropic chập chung thay vì build HTTP Restful tay để tối ưu kết nối và deploy trực tiếp hệ ecosystem tools này cắm vào **Claude Desktop**; cho pháp user gọi AI chat với máy cục bộ. Song hành với đó, đẩy Trace logs lên LangSmith/Langfuse để thu thập số liệu metrics trực quan thay vì check dict log json.

---

*File này lưu tại: `reports/group_report.md`*
