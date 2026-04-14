# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đào Danh Đăng Phụng  
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `workers/policy_tool.py`
- Functions tôi implement: `retrieve_dense()`, `run()` (retrieval), `analyze_policy()`, `run()` (policy tool)

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi phụ trách tầng worker nên công việc của tôi nằm giữa supervisor và synthesis. Supervisor route task sang retrieval/policy, sau đó tôi trả về `retrieved_chunks`, `policy_result`, `mcp_tools_used`, và `worker_io_logs` để synthesis tạo câu trả lời có căn cứ. Nếu worker output sai contract thì synthesis dễ hallucinate hoặc confidence sai.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Evidence chính là output test worker trước/sau khi sửa.  
- Retrieval trước khi sửa có score âm (ví dụ `-0.223`) và sau khi sửa nằm trong [0,1] (`0.5404`, `0.3887`, `0.3676`).  
- Policy worker detect đúng 3 nhóm exception cho refund (flash sale, digital product, activated).  
- Với access case có `needs_tool=True`, worker gọi MCP tools và trả thêm `access_decision`.
- Synthesis worker sau khi sửa có 2 hành vi đúng contract: (1) không có chunks thì abstain + `confidence=0.1` + `hitl_triggered=True`; (2) có chunks thì trả lời có citation và `hitl_triggered=False` khi confidence cao.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi chuẩn hóa score của retrieval worker bằng công thức `score = clamp(1 - distance/2, 0, 1)` để đáp ứng contract và giữ khả năng phân tách kết quả.

**Ví dụ:**
> "Tôi chọn dùng keyword-based routing trong supervisor_node thay vì gọi LLM để classify.
>  Lý do: keyword routing nhanh hơn (~5ms vs ~800ms) và đủ chính xác cho 5 categories.
>  Bằng chứng: trace gq01 route_reason='task contains P1 SLA keyword', latency=45ms."

**Lý do:**

Trong quá trình test retrieval worker, tôi thấy có score âm khi dùng cách cũ `1 - distance` (ví dụ -0.223). Điều này không khớp với contract vì `score` bắt buộc thuộc [0,1]. Tôi cân nhắc 3 cách: giữ nguyên công thức cũ, clamp trực tiếp `1 - distance`, hoặc đổi sang `1 - distance/2` rồi clamp.  

Tôi chọn cách thứ ba vì vẫn đảm bảo miền [0,1] nhưng không làm score bị dồn về 0 quá nhiều như clamp trực tiếp từ công thức cũ. Tôi cũng lưu thêm `raw_distance`, `raw_score`, và `score_mapping` trong metadata để đối chiếu khi debug trace.

**Trade-off đã chấp nhận:**

Trade-off tôi chấp nhận là công thức này dựa trên giả định distance nằm trong khoảng [0,2] (thường gặp với cosine distance). Cách này không phải là ground-truth probability, mà là điểm chuẩn hóa phục vụ ranking và tuân thủ contract. Đổi lại, pipeline dễ kiểm thử hơn và dữ liệu trace rõ ràng hơn.

**Bằng chứng từ trace/code:**

```
# workers/retrieval.py (đoạn tôi sửa)
raw_distance = float(dist)
raw_score = 1.0 - (raw_distance / 2.0)
score = max(0.0, min(1.0, raw_score))
metadata["raw_distance"] = round(raw_distance, 6)
metadata["raw_score"] = round(raw_score, 6)
metadata["score_mapping"] = "score = clamp(1 - distance/2, 0, 1)"

# output verify sau khi sửa
scores= [0.5404, 0.3887, 0.3676]
min_score= 0.3676
max_score= 0.5404
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Score retrieval âm, vi phạm contract output.

**Symptom (pipeline làm gì sai?):**

Symptom khi chạy test là retrieval vẫn trả về chunks nhưng có điểm âm (ví dụ `[-0.223]`). Điều này làm phần đánh giá confidence/synthesis khó ổn định và không đạt đúng yêu cầu contract.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Root cause nằm ở `workers/retrieval.py`: công thức cũ dùng trực tiếp `score = 1 - distance`. Với một số kết quả ChromaDB có distance > 1, score bị âm.

**Cách sửa:**

Tôi sửa công thức thành `score = clamp(1 - distance/2, 0, 1)` và bổ sung log metadata (`raw_distance`, `raw_score`, `score_mapping`) để đảm bảo vừa đúng contract vừa dễ trace.

Ngoài ra ở `workers/policy_tool.py`, tôi sửa logic để chỉ áp exception hoàn tiền khi đúng ngữ cảnh refund; đồng thời thêm MCP call `check_access_permission` cho câu hỏi access/admin/emergency và ghi rõ tool đã gọi vào log.

Ở `workers/synthesis.py`, tôi thêm guard để abstain ngay khi không có evidence (`retrieved_chunks=[]`), thêm hậu xử lý citation để tránh trường hợp model quên cite, làm sạch `sources` (bỏ `unknown`), và set `hitl_triggered` khi `confidence < 0.4`.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Trước khi sửa: có giá trị âm như `-0.223`, `-0.135`.  
Sau khi sửa: score nằm trong [0,1], ví dụ `0.5404`, `0.3887`, `0.3676`; min/max kiểm tra đều hợp lệ.

Với policy tool: trước khi sửa có nguy cơ gắn nhầm exception cho câu hỏi access; sau khi sửa access case không bị gắn exception sai và có thêm `access_decision` từ MCP tool.

Với synthesis: sau khi sửa, test có context trả `confidence=0.92`, `hitl=False`, answer có citation; test không có context trả `confidence=0.1`, `hitl=True`, `sources=[]` (đúng yêu cầu abstain).

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Điểm tôi làm tốt nhất là bám chặt contract khi sửa worker. Tôi không chỉ sửa để “chạy được” mà sửa theo đúng tiêu chí output của từng worker: retrieval phải có score trong [0,1], policy phải detect đúng exception và ghi mcp_tools_used, synthesis phải abstain khi thiếu evidence và có cơ chế citation. Tôi cũng chủ động kiểm thử trước/sau cho từng thay đổi nên dễ chứng minh kết quả bằng trace thay vì mô tả cảm tính. Nhờ đó khi tích hợp vào graph, pipeline ổn định hơn và confidence trung bình tăng so với giai đoạn đầu.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Điểm tôi còn yếu là tối ưu hiệu năng chưa sâu. Trong quá trình làm tôi tập trung vào tính đúng và tính tuân thủ contract, nên chưa tối ưu mạnh phần latency của retrieval + synthesis. Ngoài ra, lúc đầu tôi chưa tách rõ dữ liệu trace mới và trace cũ khi phân tích metrics, làm số liệu tổng hợp bị nhiễu (total_traces tăng cao). Sau đó tôi mới nhận ra và xử lý theo hướng phân tích theo từng lần chạy.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Nhóm phụ thuộc vào tôi ở phần worker output chuẩn hóa. Nếu retrieval/policy/synthesis chưa đúng contract thì supervisor có route đúng cũng không tạo được answer đáng tin. Đặc biệt, nếu tôi chưa hoàn tất retrieval score mapping và policy exception handling, phần synthesis sẽ bị nhiễu evidence và confidence thấp; đồng thời trace/report của nhóm thiếu bằng chứng kỹ thuật để giải thích quyết định routing.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào Supervisor Owner để tích hợp worker thật vào `graph.py` và đảm bảo state keys đồng nhất giữa các node. Tôi cũng phụ thuộc Trace & Docs Owner để tổng hợp đúng metrics theo từng run và đưa các số liệu đó vào báo cáo nhóm. Với MCP Owner, tôi cần schema/tool behavior ổn định để policy worker gọi tool không bị mismatch input-output.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Nếu có thêm 2 giờ, tôi sẽ thêm một bước “source-aware rerank” cho retrieval theo domain của câu hỏi (refund/access/ticket) trước khi đưa vào synthesis. Tôi chọn cải tiến này vì trace hiện cho thấy source coverage rộng nhưng vẫn còn nhiều câu confidence chỉ ở mức trung bình; tức là đã có evidence nhưng chưa luôn là evidence tốt nhất cho đúng câu hỏi. Cải tiến này có thể tăng độ liên quan của top chunks mà không phá vỡ contract hiện tại.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
