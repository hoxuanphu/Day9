# Routing Decisions Log — Lab Day 09

**Nhóm:** ___________  
**Ngày:** ___________

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1

**Task đầu vào:**
> Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình.

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword | risk_high flagged`  
**MCP tools được gọi:** `get_ticket_info`, `check_access_permission`  
**Workers called sequence:** `retrieval_worker` -> `policy_tool_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Nêu đúng quy trình escalation khẩn cấp (IT Admin cấp 24h) và SLA notify P1 (ngay lập tức + mỗi 30p).
- confidence: 0.8
- Correct routing? Yes

**Nhận xét:** Routing chính xác vì task có chứa từ khóa "access" và "P1", đồng thời supervisor nhận diện được rủi ro cao để trigger logic lấy thêm evidence.

---

## Routing Decision #2

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review`  
**Route reason (từ trace):** `unknown error or error code detected`  
**MCP tools được gọi:** None  
**Workers called sequence:** `human_review` -> `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Không đủ thông tin trong tài liệu nội bộ.
- confidence: 0.3
- Correct routing? Yes

**Nhận xét:** Supervisor đã nhận diện đúng format mã lỗi "ERR-..." không có trong KB phổ thông và trigger HITL (human_review) để người dùng xác nhận trước khi tìm kiếm vô ích.

---

## Routing Decision #3

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains ticket/escalation keyword`  
**MCP tools được gọi:** None  
**Workers called sequence:** `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): SLA phản hồi 15 phút, xử lý 4 giờ.
- confidence: 0.8
- Correct routing? Yes

**Nhận xét:** Routing tối ưu vì đây là câu hỏi cung cấp thông tin (informational), không cần kiểm tra policy hay gọi tool tác động vào hệ thống.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?

**Worker được chọn:** `policy_tool_worker`  
**Route reason:** `task contains policy/access keyword`

**Nhận xét: Đây là trường hợp routing cần sự chính xác cao vì có mâu thuẫn giữa chính sách hoàn tiền chung (lỗi NSX được hoàn) và ngoại lệ Flash Sale (không được hoàn). Logic multi-agent giúp tách biệt việc lấy evidence và việc phân tích logic policy.**

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 9 | 50% |
| policy_tool_worker | 9 | 50% |
| human_review | 3 | 16% |

### Routing Accuracy

> Trong số 18 câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 17 / 18
- Câu route sai (đã sửa bằng cách nào?): 1 (Sửa keyword matching cho case escalation)
- Câu trigger HITL: 3

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?  

1. **Kết hợp Keyword & Signal**: Sử dụng cả từ khóa (refund, access) và tín hiệu rủi ro (P1, emergency) giúp Supervisor linh hoạt hơn trong việc chọn worker.
2. **Dynamic Top-k**: Supervisor điều chỉnh `top_k` dựa trên độ khó của task giúp Synthesis có đủ dữ liệu để trả lời các câu multi-hop mà không bị nhiễu ở câu single-hop.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?  
> Nếu chưa, nhóm sẽ cải tiến format route_reason thế nào?

Trace reason hiện tại khá rõ (ví dụ: `task contains policy/access keyword | risk_high flagged`). Cải tiến: Nên thêm cả confidence score của router (nếu dùng LLM classifier) để biết mức độ chắc chắn của Supervisor.
